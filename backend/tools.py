from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
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
from .web_research import WEB_APPROVAL_REQUIRED_TOOLS, WEB_TOOL_CATALOG, WEB_TOOL_NAMES, WEB_TOOLS
from .model_runtime import load_model, start_managed_instance, stop_managed_instance, unload_model


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


class CreateWorkspaceFileInput(WorkspacePathInput):
    content: str = Field(default="", max_length=MAX_FILE_CHARS)
    expected_absent: bool = True


class PatchWorkspaceFileInput(WorkspacePathInput):
    old_text: str = Field(min_length=1, max_length=MAX_FILE_CHARS)
    new_text: str = Field(default="", max_length=MAX_FILE_CHARS)
    replace_all: bool = False
    expected_sha256: str = Field(min_length=64, max_length=64)


class RenameWorkspaceFileInput(BaseModel):
    source_path: str = Field(min_length=1, max_length=500)
    destination_path: str = Field(min_length=1, max_length=500)
    expected_sha256: str = Field(min_length=64, max_length=64)


class DeleteWorkspaceFileInput(WorkspacePathInput):
    expected_sha256: str = Field(min_length=64, max_length=64)


class ManagedRuntimeInput(BaseModel):
    profile_id: str = Field(min_length=1, max_length=120)
    port: int = Field(default=11435, ge=1024, le=65535)


class ManagedRuntimeStopInput(BaseModel):
    profile_id: str = Field(min_length=1, max_length=120)


class ManagedModelInput(BaseModel):
    profile_id: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=300)
    keep_alive: str = Field(default="5m", max_length=32)


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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_text_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def preview_workspace_mutation(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "create_workspace_file":
        path = _safe_workspace_path(str(arguments.get("relative_path", "")))
        if path.exists():
            raise ValueError("destination already exists")
        content = str(arguments.get("content", ""))[:MAX_FILE_CHARS]
        diff = "".join(difflib.unified_diff([], content.splitlines(True), fromfile="/dev/null", tofile=_relative_workspace_path(path)))
        return {"operation": "create", "path": _relative_workspace_path(path), "expected_absent": True, "diff": diff[:MAX_OUTPUT_CHARS]}
    if name == "patch_workspace_file":
        path = _safe_workspace_path(str(arguments.get("relative_path", "")), require_file=True)
        before = path.read_text(encoding="utf-8")
        old = str(arguments.get("old_text", ""))
        count = before.count(old)
        if not old or count == 0:
            raise ValueError("old_text was not found")
        if count > 1 and not bool(arguments.get("replace_all")):
            raise ValueError("old_text is not unique; set replace_all explicitly")
        after = before.replace(old, str(arguments.get("new_text", "")), -1 if arguments.get("replace_all") else 1)
        diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=_relative_workspace_path(path), tofile=_relative_workspace_path(path)))
        return {"operation": "patch", "path": _relative_workspace_path(path), "expected_sha256": _file_sha256(path), "diff": diff[:MAX_OUTPUT_CHARS]}
    if name == "rename_workspace_file":
        source = _safe_workspace_path(str(arguments.get("source_path", "")), require_file=True)
        destination = _safe_workspace_path(str(arguments.get("destination_path", "")))
        if destination.exists():
            raise ValueError("destination already exists")
        return {"operation": "rename", "path": _relative_workspace_path(source), "destination": _relative_workspace_path(destination), "expected_sha256": _file_sha256(source), "diff": f"rename {_relative_workspace_path(source)} -> {_relative_workspace_path(destination)}"}
    if name == "delete_workspace_file":
        path = _safe_workspace_path(str(arguments.get("relative_path", "")), require_file=True)
        before = path.read_text(encoding="utf-8")
        diff = "".join(difflib.unified_diff(before.splitlines(True), [], fromfile=_relative_workspace_path(path), tofile="/dev/null"))
        return {"operation": "delete", "path": _relative_workspace_path(path), "expected_sha256": _file_sha256(path), "diff": diff[:MAX_OUTPUT_CHARS]}
    raise ValueError("unknown workspace mutation")


def preview_workspace_write(relative_path: str, content: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    path = _safe_workspace_path(relative_path)
    if not path.exists():
        arguments: dict[str, Any] = {"relative_path": relative_path, "content": content}
        impact = preview_workspace_mutation("create_workspace_file", arguments)
        arguments["expected_absent"] = True
        return "create_workspace_file", arguments, impact
    if not path.is_file():
        raise ValueError("workspace write target must be a regular file")
    try:
        old_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("workspace write target must be UTF-8 text") from exc
    arguments = {"relative_path": relative_path, "old_text": old_text, "new_text": content, "replace_all": False}
    impact = preview_workspace_mutation("patch_workspace_file", arguments)
    arguments["expected_sha256"] = impact["expected_sha256"]
    return "patch_workspace_file", arguments, impact


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


@tool("create_workspace_file", args_schema=CreateWorkspaceFileInput)
def create_workspace_file(relative_path: str, content: str = "", expected_absent: bool = True) -> str:
    """Create a bounded text file after exact approval review."""
    path = _safe_workspace_path(relative_path)
    if not expected_absent or path.exists():
        raise ValueError("destination existence changed after preview")
    _atomic_text_write(path, content[:MAX_FILE_CHARS])
    return f"Created {_relative_workspace_path(path)}"


@tool("patch_workspace_file", args_schema=PatchWorkspaceFileInput)
def patch_workspace_file(relative_path: str, old_text: str, new_text: str = "", replace_all: bool = False, expected_sha256: str = "") -> str:
    """Patch exact text in a workspace file after hash-bound approval."""
    path = _safe_workspace_path(relative_path, require_file=True)
    if _file_sha256(path) != expected_sha256:
        raise ValueError("workspace file changed after preview")
    before = path.read_text(encoding="utf-8")
    count = before.count(old_text)
    if count == 0 or (count > 1 and not replace_all):
        raise ValueError("approved patch no longer matches uniquely")
    _atomic_text_write(path, before.replace(old_text, new_text, -1 if replace_all else 1))
    return f"Patched {_relative_workspace_path(path)}"


@tool("rename_workspace_file", args_schema=RenameWorkspaceFileInput)
def rename_workspace_file(source_path: str, destination_path: str, expected_sha256: str) -> str:
    """Rename a workspace file after hash-bound approval."""
    source = _safe_workspace_path(source_path, require_file=True)
    destination = _safe_workspace_path(destination_path)
    if _file_sha256(source) != expected_sha256 or destination.exists():
        raise ValueError("workspace state changed after preview")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
    return f"Renamed {_relative_workspace_path(source)} to {_relative_workspace_path(destination)}"


@tool("delete_workspace_file", args_schema=DeleteWorkspaceFileInput)
def delete_workspace_file(relative_path: str, expected_sha256: str) -> str:
    """Delete a workspace file after hash-bound approval."""
    path = _safe_workspace_path(relative_path, require_file=True)
    if _file_sha256(path) != expected_sha256:
        raise ValueError("workspace file changed after preview")
    path.unlink()
    return f"Deleted {_relative_workspace_path(path)}"


@tool("start_managed_ollama", args_schema=ManagedRuntimeInput)
def start_managed_ollama(profile_id: str, port: int = 11435) -> str:
    """Start one explicitly selected app-owned loopback Ollama instance after approval."""
    return json.dumps(start_managed_instance(profile_id, port=port), ensure_ascii=False)


@tool("stop_managed_ollama", args_schema=ManagedRuntimeStopInput)
def stop_managed_ollama(profile_id: str) -> str:
    """Stop only the app-owned managed Ollama instance for the selected profile."""
    return json.dumps(stop_managed_instance(profile_id), ensure_ascii=False)


@tool("preload_managed_model", args_schema=ManagedModelInput)
def preload_managed_model(profile_id: str, model: str, keep_alive: str = "5m") -> str:
    """Load an exact model into an app-owned managed Ollama instance after approval."""
    return json.dumps(load_model(profile_id, model, keep_alive=keep_alive), ensure_ascii=False)


@tool("unload_managed_model", args_schema=ManagedModelInput)
def unload_managed_model(profile_id: str, model: str, keep_alive: str = "0") -> str:
    """Unload an exact model from an app-owned managed Ollama instance after approval."""
    del keep_alive
    return json.dumps(unload_model(profile_id, model), ensure_ascii=False)


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
    {"name": "create_workspace_file", "description": "Create a text file with exact diff review.", "requires_approval": True, "scope": "workspace-write"},
    {"name": "patch_workspace_file", "description": "Patch exact text with diff and stale-preimage protection.", "requires_approval": True, "scope": "workspace-write"},
    {"name": "rename_workspace_file", "description": "Rename a file with source hash and destination checks.", "requires_approval": True, "scope": "workspace-write"},
    {"name": "delete_workspace_file", "description": "Delete a text file with exact diff and stale-preimage protection.", "requires_approval": True, "scope": "workspace-write"},
    {"name": "start_managed_ollama", "description": "Start one selected app-owned loopback Ollama instance.", "requires_approval": True, "scope": "managed-runtime"},
    {"name": "stop_managed_ollama", "description": "Stop only one app-owned managed Ollama instance.", "requires_approval": True, "scope": "managed-runtime"},
    {"name": "preload_managed_model", "description": "Load an exact model into an approved managed runtime.", "requires_approval": True, "scope": "managed-runtime"},
    {"name": "unload_managed_model", "description": "Unload an exact model from an approved managed runtime.", "requires_approval": True, "scope": "managed-runtime"},
]
WORKSPACE_TOOL_CATALOG.extend(HERMES_TOOL_CATALOG)
WORKSPACE_TOOL_CATALOG.extend(WEB_TOOL_CATALOG)
WORKSPACE_TOOL_NAMES = {item["name"] for item in WORKSPACE_TOOL_CATALOG} | HERMES_TOOL_NAMES | WEB_TOOL_NAMES
APPROVAL_REQUIRED_TOOLS = {
    item["name"] for item in WORKSPACE_TOOL_CATALOG if item["requires_approval"]
} | HERMES_APPROVAL_REQUIRED_TOOLS | WEB_APPROVAL_REQUIRED_TOOLS
WORKSPACE_TOOLS = [
    list_workspace_files,
    read_workspace_file,
    inspect_python_ast,
    execute_python_sandbox,
    create_workspace_file,
    patch_workspace_file,
    rename_workspace_file,
    delete_workspace_file,
    start_managed_ollama,
    stop_managed_ollama,
    preload_managed_model,
    unload_managed_model,
    *HERMES_TOOLS,
    *WEB_TOOLS,
]
