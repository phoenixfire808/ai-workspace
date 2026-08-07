from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .hermes_adapter import (
    HERMES_APPROVAL_REQUIRED_TOOLS,
    HERMES_TOOL_CATALOG,
    HERMES_TOOL_NAMES,
    HERMES_TOOLS,
)


MAX_SCRIPT_CHARS = 12_000
MAX_OUTPUT_CHARS = 24_000
MAX_FILE_CHARS = 40_000
MAX_LIST_ENTRIES = 120
SCRIPT_TIMEOUT_SECONDS = 45
WORKSPACE_ROOT = Path(
    os.getenv("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[1]))
).expanduser().resolve()

_ALLOWED_IMPORT_ROOTS = {
    "collections",
    "dataclasses",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "re",
    "statistics",
    "typing",
}
_BLOCKED_PATH_PARTS = {
    ".aws",
    ".azure",
    ".env",
    ".git",
    ".hermes",
    "auth.json",
    "credentials",
    "secrets",
    "tokens",
}
_BLOCKED_IMPORT_ROOTS = {
    "asyncio",
    "ctypes",
    "ftplib",
    "http",
    "httpx",
    "multiprocessing",
    "requests",
    "socket",
    "subprocess",
    "telnetlib",
    "urllib",
    "winreg",
}
_BLOCKED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "input",
    "open",
    "setattr",
    "vars",
}
_BLOCKED_ATTRIBUTES = {
    "check_call",
    "check_output",
    "connect",
    "popen",
    "read_bytes",
    "read_text",
    "replace",
    "rmdir",
    "run",
    "system",
    "unlink",
    "urlopen",
    "write_bytes",
    "write_text",
}

_TEXT_SUFFIXES = {
    ".cmd",
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


class SandboxInput(BaseModel):
    script_content: str = Field(
        min_length=1,
        max_length=MAX_SCRIPT_CHARS,
        description="The exact Python script content to execute inside the workspace sandbox.",
    )


class WorkspacePathInput(BaseModel):
    relative_path: str = Field(
        default="",
        max_length=500,
        description="A workspace-relative path. Absolute paths and sensitive files are rejected.",
    )


class ReadWorkspaceFileInput(WorkspacePathInput):
    max_chars: int = Field(default=MAX_FILE_CHARS, ge=1_000, le=MAX_FILE_CHARS)


class AstInspectInput(WorkspacePathInput):
    pass


def _is_sensitive_path(path: Path) -> bool:
    for part in path.parts:
        lowered = part.lower()
        if lowered in _BLOCKED_PATH_PARTS or lowered.startswith(".env"):
            return True
    return path.name.lower() in {"id_rsa", "id_ed25519", "known_hosts"}


def _safe_workspace_path(relative_path: str, *, require_file: bool = False, require_directory: bool = False) -> Path:
    configured = str(relative_path or "").strip()
    candidate = Path(configured).expanduser() if configured else WORKSPACE_ROOT
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError("path is outside the configured workspace root") from exc
    if _is_sensitive_path(resolved):
        raise ValueError("sensitive workspace paths are not available to this tool")
    if require_file and not resolved.is_file():
        raise ValueError("workspace file was not found")
    if require_directory and not resolved.is_dir():
        raise ValueError("workspace directory was not found")
    return resolved


def _relative_workspace_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE_ROOT)) or "."
    except ValueError:
        return "."


def _bounded(value: Any) -> str:
    text = str(value or "")
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_CHARS]}\n[output truncated]"


def _validate_script(script_content: str) -> None:
    try:
        tree = ast.parse(script_content, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"script syntax is invalid: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            names = []
        for name in names:
            root = name.split(".", 1)[0].lower()
            if root in _BLOCKED_IMPORT_ROOTS or root not in _ALLOWED_IMPORT_ROOTS:
                raise ValueError(f"sandbox import is not allowlisted: {root}")
        if isinstance(node, ast.Name) and node.id in {"__builtins__", "__loader__", "__spec__"}:
            raise ValueError(f"sandbox name is blocked: {node.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _BLOCKED_CALLS:
                raise ValueError(f"sandbox call is blocked: {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRIBUTES:
            raise ValueError(f"sandbox attribute is blocked: {node.attr}")


def _sandbox_environment() -> dict[str, str]:
    # Do not inherit provider keys, Hermes credentials, PYTHONPATH, or arbitrary
    # service configuration into model-requested code.
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONIOENCODING", "PYTHONUTF8"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


@tool("list_workspace_files", args_schema=WorkspacePathInput)
def list_workspace_files(relative_path: str = "") -> str:
    """List bounded metadata for non-sensitive files under the workspace root."""
    try:
        directory = _safe_workspace_path(relative_path, require_directory=True)
        ignored_directories = {".git", ".next", ".venv", "__pycache__", "node_modules"}
        entries: list[dict[str, Any]] = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if child.name.lower() in ignored_directories or _is_sensitive_path(child):
                continue
            entries.append(
                {
                    "path": _relative_workspace_path(child),
                    "kind": "directory" if child.is_dir() else "file",
                    "suffix": child.suffix.lower() if child.is_file() else "",
                }
            )
            if len(entries) >= MAX_LIST_ENTRIES:
                break
        return json.dumps(
            {
                "root": _relative_workspace_path(directory),
                "entries": entries,
                "truncated": len(entries) >= MAX_LIST_ENTRIES,
            },
            ensure_ascii=False,
        )
    except (OSError, ValueError) as exc:
        return f"Error: workspace listing rejected: {type(exc).__name__}: {exc}"


@tool("read_workspace_file", args_schema=ReadWorkspaceFileInput)
def read_workspace_file(relative_path: str, max_chars: int = MAX_FILE_CHARS) -> str:
    """Read a bounded text file under the workspace root, excluding secret-bearing paths."""
    try:
        path = _safe_workspace_path(relative_path, require_file=True)
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            return "Error: file type is not allowlisted for workspace reading."
        text = path.read_text(encoding="utf-8")
        bounded = text[: min(max(int(max_chars), 1_000), MAX_FILE_CHARS)]
        suffix = "\n[file content truncated]" if len(text) > len(bounded) else ""
        return f"PATH: {_relative_workspace_path(path)}\n{bounded}{suffix}"
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Error: workspace read rejected: {type(exc).__name__}: {exc}"


@tool("inspect_python_ast", args_schema=AstInspectInput)
def inspect_python_ast(relative_path: str) -> str:
    """Return bounded Python symbols/imports without returning source contents."""
    try:
        path = _safe_workspace_path(relative_path, require_file=True)
        if path.suffix.lower() != ".py":
            return "Error: AST inspection only accepts Python files."
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: list[str] = []
        symbols: list[dict[str, Any]] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(
                    {
                        "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                        "name": node.name,
                        "line": node.lineno,
                        "async": isinstance(node, ast.AsyncFunctionDef),
                    }
                )
        return json.dumps(
            {
                "path": _relative_workspace_path(path),
                "imports": imports[:MAX_LIST_ENTRIES],
                "symbols": symbols[:MAX_LIST_ENTRIES],
            },
            ensure_ascii=False,
        )
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        return f"Error: AST inspection rejected: {type(exc).__name__}: {exc}"


@tool("execute_python_sandbox", args_schema=SandboxInput)
def execute_python_sandbox(script_content: str) -> str:
    """Execute bounded Python in the local workspace after the graph approval gate."""
    try:
        _validate_script(script_content)
        completed = subprocess.run(
            [sys.executable, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT_SECONDS,
            shell=False,
            cwd=str(WORKSPACE_ROOT),
            env=_sandbox_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        output = f"STDOUT:\n{_bounded(completed.stdout)}\nSTDERR:\n{_bounded(completed.stderr)}"
        if completed.returncode:
            output = f"Exit code: {completed.returncode}\n{output}"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Error: Script execution exceeded the {SCRIPT_TIMEOUT_SECONDS}-second timeout limit."
    except ValueError as exc:
        return f"Error: Sandbox policy rejected the script: {exc}"
    except Exception as exc:  # Tool failures are returned as bounded model-visible results.
        return f"System Error: Failed to execute script natively: {type(exc).__name__}"


WORKSPACE_TOOL_CATALOG = [
    {
        "name": "list_workspace_files",
        "description": "List non-sensitive workspace file metadata; paths remain workspace-relative.",
        "requires_approval": False,
        "scope": "workspace",
    },
    {
        "name": "read_workspace_file",
        "description": "Read a bounded, non-sensitive text file inside the workspace.",
        "requires_approval": False,
        "scope": "workspace",
    },
    {
        "name": "inspect_python_ast",
        "description": "Inspect Python imports and top-level symbols without returning source text.",
        "requires_approval": False,
        "scope": "workspace",
    },
    {
        "name": "execute_python_sandbox",
        "description": "Run a bounded allowlisted Python computation in the workspace process environment.",
        "requires_approval": True,
        "scope": "workspace",
    },
]
WORKSPACE_TOOL_CATALOG.extend(HERMES_TOOL_CATALOG)
WORKSPACE_TOOL_NAMES = {item["name"] for item in WORKSPACE_TOOL_CATALOG} | HERMES_TOOL_NAMES
APPROVAL_REQUIRED_TOOLS = {
    item["name"] for item in WORKSPACE_TOOL_CATALOG if item["requires_approval"]
} | HERMES_APPROVAL_REQUIRED_TOOLS
WORKSPACE_TOOLS = [
    list_workspace_files,
    read_workspace_file,
    inspect_python_ast,
    execute_python_sandbox,
    *HERMES_TOOLS,
]
