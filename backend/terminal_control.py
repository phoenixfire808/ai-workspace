from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


MAX_COMMAND_CHARS = 2_000
_WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "")).expanduser() if os.getenv("WORKSPACE_ROOT") else Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = _WORKSPACE_ROOT.resolve()


class TerminalPreviewRequest(BaseModel):
    command: str = Field(min_length=1, max_length=MAX_COMMAND_CHARS)
    cwd: str = Field(default="", max_length=500)


def _relative_cwd(raw_cwd: str) -> tuple[Path | None, str | None]:
    candidate = Path(raw_cwd).expanduser() if raw_cwd.strip() else _WORKSPACE_ROOT
    if not candidate.is_absolute():
        candidate = _WORKSPACE_ROOT / candidate
    try:
        resolved = candidate.resolve(strict=False)
        relative = resolved.relative_to(_WORKSPACE_ROOT)
    except ValueError:
        return None, "cwd is outside the configured workspace root"
    return resolved, "." if str(relative) == "." else relative.as_posix()


def _first_token(command: str) -> str:
    match = re.match(r"\s*([^\s]+)", command)
    return match.group(1).strip('"\'').lower() if match else ""


def preview_terminal_command(request: TerminalPreviewRequest) -> dict[str, Any]:
    command = request.command.strip()
    cwd, relative_cwd = _relative_cwd(request.cwd)
    metadata = {
        "command_chars": len(command),
        "executable": _first_token(command),
        "cwd": relative_cwd,
        "mutation": "none",
    }
    if cwd is None:
        return {**metadata, "status": "rejected", "reason": relative_cwd, "requires_approval": False}

    lowered = command.lower()
    if any(token in lowered for token in ("api_key", "token", "password", "secret", ".env", "auth.json", "credentials")):
        return {**metadata, "status": "rejected", "reason": "credential or secret access is not allowed", "requires_approval": False}
    if any(token in command for token in ("\n", "\r", "&&", "||", ";", "|", ">", "<", "`", "$((", "${")):
        return {**metadata, "status": "rejected", "reason": "shell chaining, redirection, or interpolation is not allowed", "requires_approval": False}
    if re.search(r"(?i)\b(powershell|pwsh|cmd(?:\.exe)?|bash|sh|zsh|curl|wget|invoke-webrequest|start-process|rm|del|format|shutdown|reg|sc|taskkill)\b", command):
        return {**metadata, "status": "rejected", "reason": "shell, network, destructive, or process-control commands are not allowed", "requires_approval": False}

    safe_prefixes = (
        "python --version",
        "python -m py_compile ",
        "python.exe --version",
        "python.exe -m py_compile ",
        "git status",
        "git diff",
        "git branch --show-current",
        "node --version",
        "npm --version",
    )
    if lowered.startswith(safe_prefixes):
        return {**metadata, "status": "preview-allowed", "reason": "bounded inspection command; execution is not exposed by this endpoint", "requires_approval": False}
    return {**metadata, "status": "approval-required", "reason": "command is outside the default inspection allowlist", "requires_approval": True}


__all__ = ["TerminalPreviewRequest", "preview_terminal_command"]
