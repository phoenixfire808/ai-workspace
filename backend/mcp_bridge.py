"""Lightweight Model Context Protocol (MCP) bridge.

Exposes the existing workspace mutation tools through a small JSON-RPC
shaped HTTP surface so MCP-aware clients (Claude Code, Codex, custom
agents) can drive the workspace from outside the UI. This is intentionally
a thin layer over the existing tool implementations — it does not
re-implement any policy.

The MCP wire shape is simple by design:

    POST /mcp
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "list_workspace_files", "arguments": {}}}

Supported methods:

    tools/list                 -> {"tools": [ToolSpec, ...]}
    tools/call                 -> {"content": [...], "isError": false}
    resources/list             -> {"resources": [ResourceSpec, ...]}
    resources/read             -> {"contents": [...]}
    prompts/list               -> {"prompts": [PromptSpec, ...]}
    prompts/get                -> {"messages": [...]}

The full MCP spec is at https://modelcontextprotocol.io — this module
implements a small, focused subset that maps directly to our existing
workspace + template tools. It is NOT a substitute for the official SDK;
clients should treat this as a stable v0 surface.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from .tools import APPROVAL_REQUIRED_TOOLS, WORKSPACE_ROOT, WORKSPACE_TOOLS
from .observability import log_event, log_exception


_TOOL_NAMES_APPROVAL_REQUIRED = set(APPROVAL_REQUIRED_TOOLS)

# ---------------------------------------------------------------------------
# Tool and resource catalogs
# ---------------------------------------------------------------------------

_TOOL_NAMES_READ_ONLY = {
    "list_workspace_files",
    "read_workspace_file",
    "inspect_python_ast",
    "list_hermes_skills",
    "read_hermes_skill",
    "search_web",
    "build_research_context",
    "execute_python_sandbox",
}

# Capabilities that are exposed over MCP. Anything requiring local network
# egress, cloud model fallback, or model dispatch is intentionally omitted
# so the MCP surface stays "workspace + templates" only.
_TOOL_NAMES_EXPOSED = sorted(
    {
        *_TOOL_NAMES_READ_ONLY,
        "create_workspace_file",
        "patch_workspace_file",
        "rename_workspace_file",
        "delete_workspace_file",
        "extract_web_page",
        "deep_research",
    }
)


def _tool_spec(name: str) -> dict[str, Any]:
    tool = WORKSPACE_TOOLS_BY_NAME[name]
    schema = tool.args_schema
    properties = (schema.model_json_schema().get("properties") or {})
    required = schema.model_json_schema().get("required", [])
    return {
        "name": name,
        "description": (tool.description or "").strip(),
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


WORKSPACE_TOOLS_BY_NAME = {str(t.name): t for t in WORKSPACE_TOOLS}


def list_tools() -> list[dict[str, Any]]:
    return [_tool_spec(name) for name in _TOOL_NAMES_EXPOSED]


def list_resources() -> list[dict[str, Any]]:
    """Surface workspace metadata as MCP resources."""
    return [
        {
            "uri": "workspace://templates",
            "name": "Workflow templates",
            "description": "All built-in workflow templates. Read via resources/read with the same uri.",
            "mimeType": "application/json",
        },
        {
            "uri": "workspace://library",
            "name": "Library catalog",
            "description": "Tools, models, agents, runtimes, and templates exposed to the canvas.",
            "mimeType": "application/json",
        },
        {
            "uri": "workspace://health",
            "name": "Workspace health",
            "description": "Current health, exact-model lock, and loaded Ollama models.",
            "mimeType": "application/json",
        },
    ]


def list_prompts() -> list[dict[str, Any]]:
    return [
        {
            "name": "search-and-summarize",
            "description": "Run a SearXNG research query, fetch the top page, summarize with the exact local model.",
            "arguments": [
                {"name": "topic", "description": "Research topic", "required": True},
            ],
        },
        {
            "name": "code-and-prove",
            "description": "Ask the local model to write code, then run a bounded Python sandbox that proves the result.",
            "arguments": [
                {"name": "task", "description": "What the local model should write", "required": True},
            ],
        },
    ]


def get_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search-and-summarize":
        topic = str(arguments.get("topic", "")).strip() or "(unset)"
        return {
            "description": f"SearXNG research + local summarization for: {topic}",
            "messages": [
                {"role": "user", "content": f"Search the local SearXNG instance for '{topic}', fetch the top result page, and summarize it with the exact local model."},
            ],
        }
    if name == "code-and-prove":
        task = str(arguments.get("task", "")).strip() or "(unset)"
        return {
            "description": f"Code + prove for: {task}",
            "messages": [
                {"role": "user", "content": f"Write code that solves this task: {task}. Then run a bounded Python sandbox that proves the result."},
            ],
        }
    raise KeyError(f"unknown prompt: {name}")


# ---------------------------------------------------------------------------
# Tool execution (delegates to the real tools)
# ---------------------------------------------------------------------------

def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke an MCP tool while preserving the workspace approval contract.

    Read-only tools execute directly. Approval-required tools use a
    two-step MCP extension: the first call returns a preview id + normalized
    arguments; the caller repeats the same tool with ``_preview_id`` and
    ``_approved: true`` to commit the action. This prevents an external MCP
    agent from bypassing the UI's existing approval, diff, and preimage gates.
    """
    if name not in _TOOL_NAMES_EXPOSED:
        log_event("mcp.tool.rejected", tool=name, reason="not_exposed")
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}
    tool = WORKSPACE_TOOLS_BY_NAME[name]
    raw_arguments = dict(arguments or {})
    log_event("mcp.tool.start", tool=name, approval_required=name in _TOOL_NAMES_APPROVAL_REQUIRED)
    try:
        if name in _TOOL_NAMES_APPROVAL_REQUIRED:
            preview_id = str(raw_arguments.pop("_preview_id", "") or "")
            approved = bool(raw_arguments.pop("_approved", False))
            from .library import ActionPreviewPayload, ActionRunPayload, preview_action, run_action

            resource_id = f"tool:{name}"
            if not preview_id:
                preview = preview_action(ActionPreviewPayload(resource_id=resource_id, arguments=raw_arguments))
                next_arguments = dict(preview["arguments"])
                next_arguments.update({"_preview_id": preview["preview_id"], "_approved": True})
                body = {
                    "status": "approval_required" if preview["requires_approval"] else "ready_to_run",
                    "requires_approval": preview["requires_approval"],
                    "preview_id": preview["preview_id"],
                    "arguments": preview["arguments"],
                    "impact_preview": preview.get("impact_preview", ""),
                    "next_call": {"name": name, "arguments": next_arguments},
                }
                log_event("mcp.tool.preview", tool=name, preview_id=preview["preview_id"], requires_approval=preview["requires_approval"])
                return {"content": [{"type": "text", "text": _stringify(body)}], "isError": False}
            result = run_action(
                ActionRunPayload(
                    resource_id=resource_id,
                    arguments=raw_arguments,
                    preview_id=preview_id,
                    approved=approved,
                ),
                WORKSPACE_ROOT,
            )
            log_event("mcp.tool.completed", tool=name, preview_id=preview_id, status=str(result.get("status", "completed")))
            return {"content": [{"type": "text", "text": _stringify(result)}], "isError": False}

        # LangChain StructuredTool uses invoke(); calling .run with a
        # tool_input keyword is not portable across installed versions.
        result = tool.invoke(raw_arguments)
        log_event("mcp.tool.completed", tool=name, status="completed")
        return {"content": [{"type": "text", "text": _stringify(result)}], "isError": False}
    except PermissionError as exc:
        log_exception("mcp.tool.approval_error", exc, tool=name)
        return {"content": [{"type": "text", "text": f"approval required: {exc}"}], "isError": True}
    except Exception as exc:  # tool-level error becomes an MCP isError result
        log_exception("mcp.tool.error", exc, tool=name)
        return {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}


def read_resource(uri: str) -> dict[str, Any]:
    if uri == "workspace://templates":
        # Late import keeps the module free of circular references.
        from .library import _templates
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(_templates(), ensure_ascii=False, indent=2)}]}
    if uri == "workspace://library":
        from .library import query_library
        catalog = query_library(limit=500)
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(catalog, ensure_ascii=False, indent=2)}]}
    if uri == "workspace://health":
        # Late import — same reason.
        from . import main as _main  # noqa: F401  (provides the FastAPI app instance)
        try:
            from .ollama_control import list_ollama_running_models
            ps = list_ollama_running_models()
        except Exception as exc:
            ps = {"status": "error", "detail": str(exc)}
        try:
            from .ollama_control import list_ollama_models
            models = list_ollama_models()
        except Exception as exc:
            models = {"status": "error", "detail": str(exc)}
        body = {"loaded_models": ps, "installed_models": models, "request_id": uuid.uuid4().hex[:8]}
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(body, ensure_ascii=False, indent=2)}]}
    return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"unknown resource: {uri}"}], "isError": True}


# ---------------------------------------------------------------------------
# JSON-RPC dispatcher
# ---------------------------------------------------------------------------

def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(value)


def handle_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Single JSON-RPC 2.0 request handler. Returns the result envelope."""
    request_id = payload.get("id")
    method = str(payload.get("method", ""))
    params = payload.get("params") or {}
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "refactor-workflow-studio", "version": "0.1.0"},
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            }
        elif method == "tools/list":
            result = {"tools": list_tools()}
        elif method == "tools/call":
            name = str(params.get("name", ""))
            arguments = params.get("arguments") or {}
            result = call_tool(name, arguments)
        elif method == "resources/list":
            result = {"resources": list_resources()}
        elif method == "resources/read":
            uri = str(params.get("uri", ""))
            result = read_resource(uri)
        elif method == "prompts/list":
            result = {"prompts": list_prompts()}
        elif method == "prompts/get":
            name = str(params.get("name", ""))
            arguments = params.get("arguments") or {}
            result = get_prompt(name, arguments)
        elif method == "ping":
            result = {"ok": True}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
    except Exception as exc:  # server-side errors become JSON-RPC errors
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}