"""A very small local-model agent loop.

Dependencies: Python standard library only.

The harness intentionally owns only four concerns:
1. call an OpenAI-compatible local model;
2. expose a bounded MCP tool catalog;
3. execute read-only tools or pause for an approval receipt;
4. feed tool results back into the model.

Workspace policy remains in the existing MCP bridge. This module never imports
LangChain, LangGraph, FastAPI, or the workspace tool implementation.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_MODEL = "hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11435/v1"
DEFAULT_MCP_URL = "http://127.0.0.1:8100/mcp"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8110
DEFAULT_TIMEOUT = 180
DEFAULT_MAX_TURNS = 4

# Canonical approval-required tools are deliberately repeated as a small
# protocol boundary. MCP remains the authority and returns the preview receipt.
APPROVAL_REQUIRED_TOOLS = frozenset(
    {
        "create_workspace_file",
        "patch_workspace_file",
        "rename_workspace_file",
        "delete_workspace_file",
        "execute_python_sandbox",
    }
)

# Safe-by-default tools offered to a local model. Expensive/network tools and
# every mutating tool require an explicit per-run allowlist entry.
DEFAULT_SAFE_TOOLS = frozenset(
    {
        "list_workspace_files",
        "read_workspace_file",
        "inspect_python_ast",
        "list_hermes_skills",
        "read_hermes_skill",
        "search_web",
        "extract_web_page",
    }
)

_LOGGER = logging.getLogger("rws.local_harness")
if not _LOGGER.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(_handler)
    _LOGGER.propagate = False
_LOGGER.setLevel(os.getenv("RWS_HARNESS_LOG_LEVEL", "INFO").upper())


def _log(event: str, **fields: Any) -> None:
    safe = {"event": event, **fields}
    _LOGGER.info(json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str))


def _json_request(
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    method: str = "POST",
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed for {url}: {exc.reason}") from exc


def _text_from_mcp(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    chunks = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
    return "\n".join(chunk for chunk in chunks if chunk)


def _parse_json_text(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _normalize_ollama_url(value: str) -> str:
    value = (value or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value[:-4] if value.endswith("/v1/v1") else value


@dataclass(frozen=True)
class HarnessConfig:
    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    mcp_url: str = DEFAULT_MCP_URL
    request_timeout: float = DEFAULT_TIMEOUT
    max_turns: int = DEFAULT_MAX_TURNS
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @classmethod
    def from_env(cls) -> "HarnessConfig":
        return cls(
            model=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
            ollama_url=_normalize_ollama_url(
                os.getenv("RWS_HARNESS_OLLAMA_URL", os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL))
            ),
            mcp_url=os.getenv("RWS_HARNESS_MCP_URL", os.getenv("RWS_MCP_URL", DEFAULT_MCP_URL)).rstrip("/"),
            request_timeout=float(os.getenv("RWS_HARNESS_TIMEOUT", str(DEFAULT_TIMEOUT))),
            max_turns=max(1, min(int(os.getenv("RWS_HARNESS_MAX_TURNS", str(DEFAULT_MAX_TURNS))), 12)),
            host=os.getenv("RWS_HARNESS_HOST", DEFAULT_HOST),
            port=int(os.getenv("RWS_HARNESS_PORT", str(DEFAULT_PORT))),
        )


class McpClient:
    def __init__(self, url: str, timeout: float) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._request_id = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        response = _json_request(
            self.url,
            {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or {}},
            timeout=self.timeout,
        )
        if response.get("error"):
            raise RuntimeError(f"MCP {method} failed: {response['error']}")
        return response.get("result", response)

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.call("tools/list")
        tools = result.get("tools") or []
        return [item for item in tools if isinstance(item, dict) and item.get("name")]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.call("tools/call", {"name": name, "arguments": arguments})


@dataclass
class PendingApproval:
    run_id: str
    messages: list[dict[str, Any]]
    tool_call: dict[str, Any]
    preview: dict[str, Any]
    created_at: float = field(default_factory=time.time)


class LightweightHarness:
    """Bounded local model loop with MCP-backed tools."""

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig.from_env()
        self.mcp = McpClient(self.config.mcp_url, self.config.request_timeout)
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()

    def _model_url(self, suffix: str) -> str:
        return f"{self.config.ollama_url.rstrip('/')}/{suffix.lstrip('/')}"

    def _model_chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        _log("model.request", model=self.config.model, message_count=len(messages), tool_count=len(tools))
        result = _json_request(self._model_url("chat/completions"), payload, timeout=self.config.request_timeout)
        choices = result.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise RuntimeError("local model returned no choices")
        message = choices[0].get("message") or {}
        if not isinstance(message, dict):
            raise RuntimeError("local model returned an invalid message")
        _log(
            "model.response",
            model=result.get("model", self.config.model),
            content_chars=len(str(message.get("content") or "")),
            tool_calls=len(message.get("tool_calls") or []),
        )
        return message

    def _available_tools(self, approved_tools: set[str]) -> tuple[list[dict[str, Any]], set[str]]:
        catalog = self.mcp.list_tools()
        allowed = set(DEFAULT_SAFE_TOOLS) | set(APPROVAL_REQUIRED_TOOLS) | approved_tools
        selected = [item for item in catalog if item.get("name") in allowed]
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "parameters": item.get("inputSchema") or {"type": "object", "properties": {}},
                },
            }
            for item in selected
        ]
        return schemas, {str(item["name"]) for item in selected}

    @staticmethod
    def _tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for raw in message.get("tool_calls") or []:
            if not isinstance(raw, dict):
                continue
            function = raw.get("function") or {}
            name = str(function.get("name") or raw.get("name") or "").strip()
            if not name:
                continue
            arguments = function.get("arguments", raw.get("arguments", {}))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"tool {name} returned invalid JSON arguments: {exc}") from exc
            if not isinstance(arguments, dict):
                raise RuntimeError(f"tool {name} returned non-object arguments")
            calls.append(
                {
                    "id": str(raw.get("id") or f"call_{uuid.uuid4().hex[:12]}"),
                    "name": name,
                    "arguments": arguments,
                }
            )
        return calls

    def _store_pending(self, pending: PendingApproval) -> None:
        with self._lock:
            # Keep the process memory bounded even if a client abandons runs.
            self._pending[pending.run_id] = pending
            if len(self._pending) > 32:
                oldest = sorted(self._pending.values(), key=lambda item: item.created_at)[:8]
                for item in oldest:
                    self._pending.pop(item.run_id, None)

    def _pop_pending(self, run_id: str) -> PendingApproval | None:
        with self._lock:
            return self._pending.pop(run_id, None)

    def _invoke_tool(
        self,
        run_id: str,
        call: dict[str, Any],
        approved_tools: set[str],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        name = call["name"]
        if name not in approved_tools and name not in DEFAULT_SAFE_TOOLS and name not in APPROVAL_REQUIRED_TOOLS:
            return {"status": "tool_denied", "tool": name, "reason": "not approved for this run"}

        first = self.mcp.call_tool(name, call["arguments"])
        if name not in APPROVAL_REQUIRED_TOOLS:
            return {"status": "completed", "tool": name, "result": _text_from_mcp(first), "mcp": first}

        preview = _parse_json_text(_text_from_mcp(first)) or {"status": "approval_required", "raw": _text_from_mcp(first)}
        if (name in approved_tools or not preview.get("requires_approval")) and preview.get("next_call"):
            next_call = preview["next_call"]
            executed = self.mcp.call_tool(str(next_call.get("name", name)), dict(next_call.get("arguments") or {}))
            return {"status": "completed", "tool": name, "result": _text_from_mcp(executed), "mcp": executed}

        pending = PendingApproval(run_id=run_id, messages=messages, tool_call=call, preview=preview)
        self._store_pending(pending)
        _log("approval.required", run_id=run_id, tool=name, preview_id=preview.get("preview_id"))
        return {"status": "approval_required", "run_id": run_id, "tool": name, "preview": preview}

    def _continue_after_tool(self, messages: list[dict[str, Any]], call: dict[str, Any], result: dict[str, Any]) -> None:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            }
        )

    def run(
        self,
        message: str,
        *,
        approved_tools: list[str] | None = None,
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        approved = {str(item) for item in (approved_tools or [])}
        turns = max(1, min(int(max_turns or self.config.max_turns), 12))
        messages: list[dict[str, Any]] = [{"role": "user", "content": str(message)}]
        events: list[dict[str, Any]] = []
        _log("run.start", run_id=run_id, max_turns=turns, approved_tools=sorted(approved))
        try:
            tools, available = self._available_tools(approved)
            for turn in range(1, turns + 1):
                assistant = self._model_chat(messages, tools)
                calls = self._tool_calls(assistant)
                messages.append(assistant)
                if not calls:
                    result = {
                        "status": "completed",
                        "run_id": run_id,
                        "model": self.config.model,
                        "turns": turn,
                        "content": assistant.get("content") or "",
                        "events": events,
                    }
                    _log("run.complete", run_id=run_id, turns=turn, status="completed")
                    return result
                for call in calls:
                    if call["name"] not in available:
                        result = {"status": "tool_denied", "tool": call["name"], "reason": "tool not in harness catalog"}
                    else:
                        result = self._invoke_tool(run_id, call, approved, messages)
                    events.append({"tool": call["name"], "status": result.get("status")})
                    if result.get("status") == "approval_required":
                        return {
                            "status": "approval_required",
                            "run_id": run_id,
                            "model": self.config.model,
                            "turns": turn,
                            "approval": result,
                            "events": events,
                        }
                    self._continue_after_tool(messages, call, result)
            _log("run.limit", run_id=run_id, max_turns=turns)
            return {"status": "max_turns", "run_id": run_id, "model": self.config.model, "events": events}
        except Exception as exc:
            _log("run.error", run_id=run_id, error=type(exc).__name__, detail=str(exc)[:300])
            return {"status": "error", "run_id": run_id, "model": self.config.model, "error": str(exc), "events": events}

    def resume(self, run_id: str, *, approve: bool) -> dict[str, Any]:
        pending = self._pop_pending(run_id)
        if pending is None:
            return {"status": "error", "error": "unknown or expired run_id"}
        if not approve:
            _log("approval.rejected", run_id=run_id, tool=pending.tool_call["name"])
            return {"status": "rejected", "run_id": run_id, "tool": pending.tool_call["name"]}
        preview_id = str(pending.preview.get("preview_id") or "")
        if not preview_id:
            return {"status": "error", "run_id": run_id, "error": "approval preview did not include preview_id"}
        arguments = dict(pending.preview.get("arguments") or pending.tool_call["arguments"])
        arguments.update({"_preview_id": preview_id, "_approved": True})
        result = self.mcp.call_tool(pending.tool_call["name"], arguments)
        tool_result = {"status": "completed", "tool": pending.tool_call["name"], "result": _text_from_mcp(result), "mcp": result}
        self._continue_after_tool(pending.messages, pending.tool_call, tool_result)
        _log("approval.accepted", run_id=run_id, tool=pending.tool_call["name"], preview_id=preview_id)
        # Resume with the preserved conversation, but use a new run ID so the
        # receipt clearly distinguishes the resumed execution.
        resumed = self._run_messages(pending.messages, run_id=run_id, approved_tools={pending.tool_call["name"]})
        resumed["approval"] = {"status": "accepted", "tool": pending.tool_call["name"], "preview_id": preview_id}
        return resumed

    def _run_messages(self, messages: list[dict[str, Any]], *, run_id: str, approved_tools: set[str]) -> dict[str, Any]:
        tools, available = self._available_tools(approved_tools)
        events: list[dict[str, Any]] = []
        for turn in range(1, self.config.max_turns + 1):
            assistant = self._model_chat(messages, tools)
            calls = self._tool_calls(assistant)
            messages.append(assistant)
            if not calls:
                return {"status": "completed", "run_id": run_id, "model": self.config.model, "turns": turn, "content": assistant.get("content") or "", "events": events}
            for call in calls:
                if call["name"] not in available:
                    return {"status": "tool_denied", "run_id": run_id, "tool": call["name"], "events": events}
                result = self._invoke_tool(run_id, call, approved_tools, messages)
                events.append({"tool": call["name"], "status": result.get("status")})
                if result.get("status") == "approval_required":
                    return {"status": "approval_required", "run_id": run_id, "approval": result, "events": events}
                self._continue_after_tool(messages, call, result)
        return {"status": "max_turns", "run_id": run_id, "model": self.config.model, "events": events}

    def health(self) -> dict[str, Any]:
        model_probe: dict[str, Any]
        try:
            model_probe = _json_request(self._model_url("models"), None, timeout=8, method="GET")
            advertised = [str(item.get("id")) for item in model_probe.get("data", []) if isinstance(item, dict)]
            exact_advertised = self.config.model in advertised
        except Exception as exc:
            advertised = []
            exact_advertised = False
            model_probe = {"error": str(exc)}
        try:
            tool_count = len(self.mcp.list_tools())
            mcp_status = "ready"
        except Exception as exc:
            tool_count = 0
            mcp_status = f"error: {exc}"
        return {
            "status": "ready" if exact_advertised and mcp_status == "ready" else "degraded",
            "model": self.config.model,
            "ollama_url": self.config.ollama_url,
            "model_advertised": exact_advertised,
            "advertised_models": advertised,
            "mcp_url": self.config.mcp_url,
            "mcp_status": mcp_status,
            "tool_count": tool_count,
            "dependencies": "python-stdlib-only",
            "pending_approvals": len(self._pending),
            "model_probe_error": model_probe.get("error"),
        }

    def tools(self) -> list[dict[str, Any]]:
        catalog = self.mcp.list_tools()
        result = []
        for item in catalog:
            name = str(item.get("name"))
            result.append({
                "name": name,
                "approval_required": name in APPROVAL_REQUIRED_TOOLS,
                "safe_by_default": name in DEFAULT_SAFE_TOOLS,
                "description": item.get("description", ""),
                "inputSchema": item.get("inputSchema", {}),
            })
        return result


def serve(config: HarnessConfig | None = None) -> None:
    config = config or HarnessConfig.from_env()
    harness = LightweightHarness(config)

    class Handler(BaseHTTPRequestHandler):
        server_version = "RWS-Lightweight-Harness/0.1"

        def _write(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write(200, harness.health())
            elif self.path == "/tools":
                try:
                    self._write(200, {"tools": harness.tools()})
                except Exception as exc:
                    self._write(502, {"status": "error", "error": str(exc)})
            elif self.path == "/v1/models":
                self._write(200, {"object": "list", "data": [{"id": config.model, "object": "model", "owned_by": "local"}]})
            else:
                self._write(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                if self.path == "/run":
                    result = harness.run(
                        str(payload.get("message", "")),
                        approved_tools=list(payload.get("approved_tools") or []),
                        max_turns=payload.get("max_turns"),
                    )
                    self._write(200 if result.get("status") != "error" else 502, result)
                elif self.path == "/resume":
                    result = harness.resume(str(payload.get("run_id", "")), approve=bool(payload.get("approve", False)))
                    self._write(200 if result.get("status") != "error" else 404, result)
                else:
                    self._write(404, {"error": "not found"})
            except Exception as exc:
                _log("http.error", path=self.path, error=type(exc).__name__, detail=str(exc)[:300])
                self._write(400, {"status": "error", "error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            _log("http.access", method=self.command, path=self.path, detail=format % args)

    _log("server.start", host=config.host, port=config.port, model=config.model, mcp_url=config.mcp_url)
    server = ThreadingHTTPServer((config.host, config.port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        _log("server.stop")


if __name__ == "__main__":
    serve()
