from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


MAX_SKILL_CHARS = 24_000
MAX_SKILLS = 200
_SKILL_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,240}$")


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


@tool("list_hermes_skills", args_schema=HermesSkillInput)
def list_hermes_skills(skill_name: str = "") -> str:
    """List installed Hermes SKILL.md metadata without reading credentials or sessions."""
    del skill_name
    root = _skills_root()
    if not root.is_dir():
        return json.dumps({"skills": [], "configured": False}, ensure_ascii=False)
    skills: list[dict[str, Any]] = []
    for skill_file in sorted(root.rglob("SKILL.md"), key=lambda item: str(item).lower()):
        try:
            relative = skill_file.parent.relative_to(root).as_posix()
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            continue
        skills.append({"name": relative, "description": _description(text)})
        if len(skills) >= MAX_SKILLS:
            break
    return json.dumps({"skills": skills, "configured": True}, ensure_ascii=False)


@tool("read_hermes_skill", args_schema=HermesSkillInput)
def read_hermes_skill(skill_name: str) -> str:
    """Read one bounded Hermes SKILL.md; auth, memory, sessions, and config are excluded."""
    try:
        content = _safe_skill_file(skill_name).read_text(encoding="utf-8")
        if len(content) > MAX_SKILL_CHARS:
            content = f"{content[:MAX_SKILL_CHARS]}\n[skill content truncated]"
        return f"SKILL: {skill_name}\n{content}"
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Error: Hermes skill read rejected: {type(exc).__name__}: {exc}"


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
        return "Error: Hermes skill is not configured for dispatch."
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
        return f"Started configured Hermes skill adapter '{skill_name}' (pid {process.pid})."
    except (OSError, ValueError) as exc:
        return f"Error: Hermes skill dispatch failed: {type(exc).__name__}"


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
