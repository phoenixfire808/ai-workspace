from __future__ import annotations

import os
import asyncio
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .schema import AgentState
from .tools import APPROVAL_REQUIRED_TOOLS, WORKSPACE_TOOL_NAMES, WORKSPACE_TOOLS
from .model_settings import get_workspace_model_setting
from .ollama_control import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, preflight_ollama_model, safe_ollama_base_url
from .observability import log_event, log_exception


DEFAULT_LFM_MODEL = DEFAULT_OLLAMA_MODEL
DEFAULT_LFM_BASE_URL = f"{DEFAULT_OLLAMA_BASE_URL}/v1"
DEFAULT_LFM_HARDWARE_LANE = "ollama-auto"
MAX_AGENT_LOOPS = 8


class AgentEngineError(RuntimeError):
    def __init__(self, detail: str, failure_class: str):
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


def _lfm_base_url() -> str:
    try:
        return f"{safe_ollama_base_url()}/v1"
    except ValueError as exc:
        raise AgentEngineError(
            "OLLAMA_BASE_URL must be an unauthenticated loopback HTTP URL",
            "lfm_endpoint_invalid",
        ) from exc


def _lfm_model() -> str:
    setting = get_workspace_model_setting()
    model = str(setting.get("model") or DEFAULT_LFM_MODEL).strip()
    preflight = preflight_ollama_model(model)
    if preflight.get("status") != "ready" or preflight.get("exact_model") is not True:
        log_event("model.selection.rejected", model=model, failure_class=str(preflight.get("failure_class") or "ollama_model_mismatch"))
        raise AgentEngineError("The selected workspace model is not installed in Ollama", str(preflight.get("failure_class") or "ollama_model_mismatch"))
    log_event("model.selection.ready", model=model)
    return model


@lru_cache(maxsize=8)
def _cached_lfm_llm(base_url: str, model: str) -> ChatOpenAI:
    try:
        return ChatOpenAI(
            base_url=base_url,
            api_key="not-needed",
            model=model,
            max_tokens=4096,
            temperature=0.1,
            streaming=True,
            timeout=min(max(float(os.getenv("LFM_TIMEOUT_SECONDS", "120")), 1.0), 300.0),
            max_retries=0,
        )
    except AgentEngineError:
        raise
    except Exception as exc:
        raise AgentEngineError("LFM client could not be configured", "lfm_configuration_failed") from exc


def get_lfm_llm() -> ChatOpenAI:
    """Create an exact-model local client from the saved Refactor Workflow Studio Ollama selection."""
    return _cached_lfm_llm(_lfm_base_url(), _lfm_model())


def _preflight_lfm() -> None:
    """Require the exact opt-in model before every agent generation."""
    base_url = _lfm_base_url()
    model = _lfm_model()
    log_event("model.preflight.start", model=model, base_url=base_url)
    try:
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            response = client.get(f"{base_url}/models")
            response.raise_for_status()
            payload = response.json()
        model_ids = {
            item.get("id")
            for item in payload.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
    except httpx.TimeoutException as exc:
        raise AgentEngineError("LFM model preflight timed out", "lfm_preflight_timeout") from exc
    except httpx.ConnectError as exc:
        raise AgentEngineError("The local LFM endpoint is unavailable", "lfm_unavailable") from exc
    except (httpx.HTTPError, TypeError, ValueError, AttributeError) as exc:
        raise AgentEngineError("The local LFM model inventory was invalid", "lfm_preflight_failed") from exc
    log_event("model.preflight.inventory", model=model, advertised_count=len(model_ids), exact_advertised=model in model_ids)
    if model not in model_ids:
        raise AgentEngineError(
            "The configured LFM endpoint does not advertise the exact approved model",
            "lfm_model_mismatch",
        )


def _tool_names(state: AgentState) -> list[str]:
    messages = list(state.get("messages", []))
    if not messages:
        return []
    last = messages[-1]
    calls = getattr(last, "tool_calls", []) or []
    return [str(call.get("name")) for call in calls if isinstance(call, dict) and call.get("name")]


def agent_node(state: AgentState) -> dict[str, Any]:
    loop_count = int(state.get("loop_count", 0)) + 1
    max_loops = min(max(int(state.get("max_loops", 4)), 1), MAX_AGENT_LOOPS)
    if loop_count > max_loops:
        raise AgentEngineError("agent loop limit reached", "agent_loop_limit")
    try:
        _preflight_lfm()
        response = get_lfm_llm().bind_tools(WORKSPACE_TOOLS).invoke(list(state["messages"]))
    except AgentEngineError:
        raise
    except Exception as exc:
        raise AgentEngineError("LFM local endpoint is unavailable or rejected the request", "lfm_unavailable") from exc
    return {"messages": [response], "loop_count": loop_count}


def should_continue(state: AgentState) -> str:
    tool_names = _tool_names(state)
    if not tool_names:
        return "end"
    unknown = set(tool_names) - WORKSPACE_TOOL_NAMES
    if unknown:
        return "invalid"
    approved = {str(name) for name in state.get("approved_tools", [])}
    if any(name in APPROVAL_REQUIRED_TOOLS and name not in approved for name in tool_names):
        return "approval"
    if int(state.get("loop_count", 0)) >= min(max(int(state.get("max_loops", 4)), 1), MAX_AGENT_LOOPS):
        return "limit"
    return "continue"


def approval_node(state: AgentState) -> dict[str, Any]:
    requested = [
        name
        for name in _tool_names(state)
        if name not in APPROVAL_REQUIRED_TOOLS or name not in {str(item) for item in state.get("approved_tools", [])}
    ]
    return {
        "pending_approvals": requested,
        "last_error": "approval_required",
    }


def invalid_tool_node(state: AgentState) -> dict[str, Any]:
    return {
        "pending_approvals": [],
        "rejected_tools": sorted(set(_tool_names(state))),
        "last_error": "tool_not_allowlisted",
    }


def loop_limit_node(state: AgentState) -> dict[str, Any]:
    return {"pending_approvals": [], "last_error": "agent_loop_limit"}


def capture_tool_outputs(state: AgentState) -> dict[str, Any]:
    outputs: list[str] = []
    for message in list(state.get("messages", [])):
        if getattr(message, "type", "") == "tool":
            content = getattr(message, "content", "")
            outputs.append(str(content)[:24_000])
    return {"tool_outputs": outputs[-8:]}


def get_lfm_workflow():
    """Build (not cache) the HITL agent/tool loop — compiled fresh every call.

    The @lru_cache on this function was binding the LLM instance at compile time,
    so model changes between requests were not picked up. Compilation is ~50 ms
    and idempotent; caching the compiled graph buys nothing and causes stale model
    binding. Removed.
    """
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(WORKSPACE_TOOLS))
    workflow.add_node("capture_tool_outputs", capture_tool_outputs)
    workflow.add_node("approval_required", approval_node)
    workflow.add_node("tool_not_allowlisted", invalid_tool_node)
    workflow.add_node("loop_limit", loop_limit_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "approval": "approval_required",
            "invalid": "tool_not_allowlisted",
            "limit": "loop_limit",
            "end": END,
        },
    )
    workflow.add_edge("tools", "capture_tool_outputs")
    workflow.add_edge("capture_tool_outputs", "agent")
    workflow.add_edge("approval_required", END)
    workflow.add_edge("tool_not_allowlisted", END)
    workflow.add_edge("loop_limit", END)
    return workflow.compile()


def initial_agent_state(
    message: BaseMessage,
    *,
    workspace_root: str,
    project_id: str | None,
    active_hardware_lane: str = DEFAULT_LFM_HARDWARE_LANE,
    approved_tools: list[str] | None = None,
    max_loops: int = 4,
    run_id: str | None = None,
) -> AgentState:
    return {
        "messages": [message],
        "workspace_root": workspace_root,
        "project_id": project_id,
        "pending_approvals": [],
        "active_hardware_lane": active_hardware_lane[:120],
        "approved_tools": list(approved_tools or []),
        "tool_outputs": [],
        "loop_count": 0,
        "max_loops": min(max(int(max_loops), 1), MAX_AGENT_LOOPS),
        "last_error": None,
        "run_id": run_id or "",
    }


def _chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


class VisibleAnswerFilter:
    """Suppress model reasoning tags while preserving final-answer token deltas."""

    def __init__(self) -> None:
        self.in_thinking = False
        self.buffer = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self.buffer += text
        visible: list[str] = []
        while self.buffer:
            if self.in_thinking:
                end = self.buffer.find("</think>")
                if end < 0:
                    if final:
                        self.buffer = ""
                    break
                self.buffer = self.buffer[end + len("</think>"):]
                self.in_thinking = False
                continue
            start = self.buffer.find("<think>")
            if start >= 0:
                visible.append(self.buffer[:start])
                self.buffer = self.buffer[start + len("<think>"):]
                self.in_thinking = True
                continue
            if final:
                visible.append(self.buffer)
                self.buffer = ""
            else:
                keep = max(len("<think>") - 1, 0)
                if len(self.buffer) <= keep:
                    break
                visible.append(self.buffer[:-keep])
                self.buffer = self.buffer[-keep:]
        return "".join(visible)


def iter_lfm_events(state: AgentState) -> Iterator[dict[str, Any]]:
    """Synchronous HITL agent — pure iterator, no async.

    The LLM call blocks but takes only ~2 s; this is acceptable for the HITL loop.
    Runs entirely in a ThreadPoolExecutor to avoid blocking the FastAPI async loop.
    """
    from concurrent.futures import ThreadPoolExecutor

    visible_filter = VisibleAnswerFilter()
    loop_count = 0
    max_loops = min(max(int(state.get("max_loops", 4)), 1), MAX_AGENT_LOOPS)
    approved_tools_set = set(state.get("approved_tools", []))

    while True:
        loop_count += 1
        if loop_count > max_loops:
            yield {"type": "loop_limit"}
            break

        # Preflight check
        try:
            _preflight_lfm()
        except AgentEngineError:
            raise

        messages = list(state.get("messages", []))
        if not messages:
            break

        # Run LLM in thread pool — httpx sync client inside a real OS thread
        def _call_llm():
            llm = get_lfm_llm().bind_tools(WORKSPACE_TOOLS)
            return llm.invoke(messages)

        log_event("agent.model.invoke", run_id=str(state.get("run_id", "")), loop=loop_count, message_count=len(messages), bound_tool_count=len(WORKSPACE_TOOLS))
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(_call_llm).result()
        except Exception as exc:
            log_exception("agent.model.error", exc, run_id=str(state.get("run_id", "")), loop=loop_count)
            yield {"type": "error", "failure_class": "lfm_generation_failed", "error": str(exc)[:500]}
            return

        # Stream visible text; structured tool calls are handled below.
        if hasattr(response, "content") and response.content:
            text = visible_filter.feed(response.content if isinstance(response.content, str) else str(response.content))
            if text:
                yield {"type": "token", "content": text}

        tool_calls = getattr(response, "tool_calls", []) or []
        tool_names = [str(tc.get("name", "")) for tc in tool_calls if isinstance(tc, dict)]
        log_event("agent.model.response", run_id=str(state.get("run_id", "")), loop=loop_count, content_chars=len(str(getattr(response, "content", "") or "")), tool_calls=tool_names)
        if not tool_calls:
            tail = visible_filter.feed("", final=True)
            if tail:
                yield {"type": "token", "content": tail}
            break

        # Check gate before invoking any tool.
        pending_approvals: list[str] = []
        for tc in tool_calls:
            tc_name = str(tc.get("name", "")) if isinstance(tc, dict) else str(getattr(tc, "name", ""))
            if tc_name not in WORKSPACE_TOOL_NAMES:
                log_event("agent.tool.rejected", run_id=str(state.get("run_id", "")), tool=tc_name, reason="not_allowlisted")
                yield {"type": "tool_not_allowlisted", "tools": [tc_name]}
                return
            if tc_name in APPROVAL_REQUIRED_TOOLS and tc_name not in approved_tools_set:
                pending_approvals.append(tc_name)

        if pending_approvals:
            log_event("agent.approval.required", run_id=str(state.get("run_id", "")), tools=pending_approvals)
            yield {"type": "approval_required", "tools": pending_approvals}
            state["messages"] = state.get("messages", []) + [response]
            return

        # Invoke ToolNode exactly once; it executes all structured calls and
        # returns actual ToolMessage objects for the next model turn.
        tool_node = ToolNode(WORKSPACE_TOOLS)
        try:
            tool_result = tool_node.invoke({"messages": [response]})
            emitted_messages = list(tool_result.get("messages", [])) if isinstance(tool_result, dict) else []
            tool_messages: list[Any] = emitted_messages
            total_output_chars = sum(len(str(getattr(message, "content", ""))) for message in emitted_messages)
            for tc_name in tool_names:
                log_event("agent.tool.completed", run_id=str(state.get("run_id", "")), tool=tc_name, output_chars=total_output_chars)
                yield {"type": "tool_start", "tool": tc_name}
                yield {"type": "tool_end", "tool": tc_name, "output_chars": total_output_chars}
        except Exception as exc:
            log_exception("agent.tool.error", exc, run_id=str(state.get("run_id", "")), tools=tool_names)
            yield {"type": "error", "failure_class": "tool_execution_failed", "error": str(exc)[:500]}
            return

        # Append the assistant response and actual ToolMessages, then loop.
        state = dict(state)
        state["messages"] = state.get("messages", []) + [response] + tool_messages
        state["loop_count"] = loop_count
        tail = visible_filter.feed("", final=True)
        if tail:
            yield {"type": "token", "content": tail}


# Keep async alias for backward compat while migrating callers
async def stream_lfm_events(state: AgentState) -> AsyncIterator[dict[str, Any]]:
    """Async wrapper — consumes the sync iterator and yields async."""
    for event in iter_lfm_events(state):
        yield event
