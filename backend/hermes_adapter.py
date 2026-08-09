from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


MAX_SKILL_CHARS = 24_000
MAX_SKILLS = 200
_SKILL_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,240}$")
_DISPATCH_PROCESSES: dict[int, subprocess.Popen[str]] = {}
_DISPATCH_LOCK = threading.Lock()


def _skills_root() -> Path:
    configured = os.getenv("HERMES_SKILLS_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return Path("__hermes_skills_unconfigured__")
    return (Path(local_app_data) / "hermes" / "profiles" / "personal" / "skills").resolve()


def _safe_skill_file(skill_name: str) -> Path:
    name = str(skill_name or "").strip().strip("/")
    if not _SKILL_NAME.fullmatch(name) or ".." in Path(name).parts:
        raise ValueError("invalid Hermes skill name")
    root = _skills_root()
    candidate = (root / Path(*name.split("/")) / "SKILL.md").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Hermes skill path is outside the configured skills root") from exc
    if not candidate.is_file():
        raise ValueError("Hermes skill was not found")
    return candidate


def _description(text: str) -> str:
    for line in text.splitlines()[:30]:
        if line.lower().startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"\'')[:300]
    return ""


class HermesSkillInput(BaseModel):
    skill_name: str = Field(default="", max_length=240)


class HermesDispatchInput(HermesSkillInput):
    prompt: str = Field(min_length=1, max_length=40_000)


def _receipt_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def take_dispatch_process(process_id: int) -> subprocess.Popen[str] | None:
    with _DISPATCH_LOCK:
        return _DISPATCH_PROCESSES.pop(process_id, None)


def hermes_capability_audit() -> dict[str, Any]:
    root = _skills_root()
    configured_targets = sorted(_configured_skill_commands())
    inventory = json.loads(list_hermes_skills.invoke({"skill_name": ""}))
    inventory_ready = inventory.get("status") == "completed"
    with _DISPATCH_LOCK:
        active_processes = sorted(_DISPATCH_PROCESSES)
    capabilities = [
        {"capability": "inventory", "ready": inventory_ready, "disabled_reason": None if inventory_ready else str(inventory.get("failure_class") or "hermes_skills_unavailable")},
        {"capability": "read_skill", "ready": inventory_ready, "disabled_reason": None if inventory_ready else str(inventory.get("failure_class") or "hermes_skills_unavailable")},
        {"capability": "dispatch_skill", "ready": bool(configured_targets), "disabled_reason": None if configured_targets else "hermes_dispatch_targets_not_configured", "requires_approval": True},
        {"capability": "profile_mutation", "ready": False, "disabled_reason": "hermes_profile_mutation_not_supported"},
    ]
    return {"status": "ready" if inventory_ready else "disabled", "audit_id": _receipt_id(str(root), str(inventory.get("inventory_id")), json.dumps(configured_targets)), "skills_root": str(root), "inventory_id": inventory.get("inventory_id"), "skill_count": int(inventory.get("skill_count") or 0), "configured_dispatch_targets": configured_targets, "active_dispatch_process_ids": active_processes, "profile_mutation_supported": False, "capabilities": capabilities}


@tool("list_hermes_skills", args_schema=HermesSkillInput)
def list_hermes_skills(skill_name: str = "") -> str:
    """List installed Hermes SKILL.md metadata without reading credentials or sessions."""
    del skill_name
    root = _skills_root()
    if not root.is_dir():
        return json.dumps({"status": "disabled", "configured": False, "failure_class": "hermes_skills_root_missing", "detail": "the configured Hermes skills root is unavailable", "inventory_id": None, "skills": []}, ensure_ascii=False)
    skills: list[dict[str, Any]] = []
    skipped = 0
    for skill_file in sorted(root.rglob("SKILL.md"), key=lambda item: str(item).lower()):
        try:
            relative = skill_file.parent.relative_to(root).as_posix()
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            skipped += 1
            continue
        skills.append({"name": relative, "description": _description(text)})
        if len(skills) >= MAX_SKILLS:
            break
    inventory_id = _receipt_id(str(root), json.dumps(skills, ensure_ascii=False, sort_keys=True))
    return json.dumps({"status": "completed", "configured": True, "failure_class": "hermes_skill_entries_skipped" if skipped else None, "detail": f"{skipped} skill entries were skipped" if skipped else None, "inventory_id": inventory_id, "skill_count": len(skills), "skills": skills}, ensure_ascii=False)


@tool("read_hermes_skill", args_schema=HermesSkillInput)
def read_hermes_skill(skill_name: str) -> str:
    """Read one bounded Hermes SKILL.md; auth, memory, sessions, and config are excluded."""
    try:
        full_content = _safe_skill_file(skill_name).read_text(encoding="utf-8")
        truncated = len(full_content) > MAX_SKILL_CHARS
        content = f"{full_content[:MAX_SKILL_CHARS]}\n[skill content truncated]" if truncated else full_content
        return json.dumps({"status": "completed", "skill_name": skill_name, "skill_sha256": hashlib.sha256(full_content.encode("utf-8")).hexdigest(), "char_count": len(content), "truncated": truncated, "content": content}, ensure_ascii=False)
    except (OSError, UnicodeError, ValueError) as exc:
        return json.dumps({"status": "error", "skill_name": skill_name, "failure_class": "hermes_skill_read_rejected", "detail": str(exc)[:500]}, ensure_ascii=False)


def _configured_skill_commands() -> dict[str, list[str]]:
    raw = os.getenv("HERMES_SKILL_COMMANDS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(name): command
        for name, command in parsed.items()
        if isinstance(name, str)
        and _SKILL_NAME.fullmatch(name)
        and isinstance(command, list)
        and command
        and all(isinstance(part, str) and part for part in command)
    }


def _workspace_root() -> Path:
    configured = os.getenv("WORKSPACE_ROOT", "").strip()
    return (Path(configured).expanduser() if configured else Path(__file__).resolve().parents[1]).resolve()


@tool("dispatch_hermes_skill", args_schema=HermesDispatchInput)
def dispatch_hermes_skill(skill_name: str, prompt: str) -> str:
    """Start an explicitly configured Hermes skill adapter; prompt travels via stdin, not argv."""
    commands = _configured_skill_commands()
    command = commands.get(skill_name)
    if not command:
        return json.dumps({"status": "error", "skill_name": skill_name, "failure_class": "hermes_skill_not_configured", "detail": "Hermes skill is not configured for dispatch."}, ensure_ascii=False)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(_workspace_root()),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.stdin is not None:
            process.stdin.write(prompt[:40_000])
            process.stdin.close()
            process.stdin = None
        process_id = int(process.pid)
        with _DISPATCH_LOCK:
            _DISPATCH_PROCESSES[process_id] = process
        return json.dumps({"status": "queued", "skill_name": skill_name, "process_id": process_id, "receipt_id": _receipt_id(skill_name, str(process_id)), "prompt_chars": min(len(prompt), 40_000), "capture": "metadata_only"}, ensure_ascii=False)
    except (OSError, ValueError) as exc:
        return json.dumps({"status": "error", "skill_name": skill_name, "failure_class": "hermes_skill_dispatch_failed", "detail": type(exc).__name__}, ensure_ascii=False)


HERMES_TOOLS = [list_hermes_skills, read_hermes_skill, dispatch_hermes_skill]
HERMES_TOOL_CATALOG = [
    {
        "name": "list_hermes_skills",
        "description": "List local SKILL.md metadata without credentials or session data.",
        "requires_approval": False,
        "scope": "hermes-skills-readonly",
    },
    {
        "name": "read_hermes_skill",
        "description": "Read one bounded local SKILL.md for workflow guidance.",
        "requires_approval": False,
        "scope": "hermes-skills-readonly",
    },
    {
        "name": "dispatch_hermes_skill",
        "description": "Start only a configured Hermes skill adapter with prompt on stdin.",
        "requires_approval": True,
        "scope": "hermes-dispatch",
    },
]
HERMES_TOOL_NAMES = {item["name"] for item in HERMES_TOOL_CATALOG}
HERMES_APPROVAL_REQUIRED_TOOLS = {
    item["name"] for item in HERMES_TOOL_CATALOG if item["requires_approval"]
}
