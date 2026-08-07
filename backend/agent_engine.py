from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .schema import AgentState
from .tools import APPROVAL_REQUIRED_TOOLS, WORKSPACE_TOOL_NAMES, WORKSPACE_TOOLS


DEFAULT_LFM_MODEL = "LFM2.5-2.6B"
DEFAULT_LFM_BASE_URL = "http://127.0.0.1:8082/v1"
DEFAULT_LFM_HARDWARE_LANE = "shared-rtx-2070-super"
MAX_AGENT_LOOPS = 8


class AgentEngineError(RuntimeError):
    def __init__(self, detail: str, failure_class: str):
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


def _lfm_base_url() -> str:
    raw = os.getenv("LFM_BASE_URL", DEFAULT_LFM_BASE_URL).strip().rstrip("/")
    match = re.fullmatch(r"http://127\.0\.0\.1:(\d+)/v1", raw)
    if not match:
        raise AgentEngineError(
            "LFM_BASE_URL must be an unauthenticated loopback HTTP /v1 URL",
            "lfm_endpoint_invalid",
        )
    return raw


def _lfm_model() -> str:
    model = os.getenv("LFM_MODEL", DEFAULT_LFM_MODEL).strip()
    if model != DEFAULT_LFM_MODEL:
        raise AgentEngineError(
            "LFM_MODEL must match the approved LiquidAI model identity",
            "lfm_model_policy_rejected",
        )
    return model


@lru_cache(maxsize=1)
def get_lfm_llm() -> ChatOpenAI:
    """Create the opt-in LFM client without touching the active Nanbeige route."""
    try:
        return ChatOpenAI(
            base_url=_lfm_base_url(),
            api_key="not-needed",
            model=_lfm_model(),
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


def _preflight_lfm() -> None:
    """Require the exact opt-in model before every agent generation."""
    base_url = _lfm_base_url()
    model = _lfm_model()
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


@lru_cache(maxsize=1)
def get_lfm_workflow():
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


async def stream_lfm_events(state: AgentState) -> AsyncIterator[dict[str, Any]]:
    """Yield safe chat/tool progress events from LangGraph's async event stream."""
    visible_filter = VisibleAnswerFilter()
    streamed_model_runs: set[str] = set()
    async for event in get_lfm_workflow().astream_events(state, version="v2"):
        kind = event.get("event")
        name = str(event.get("name") or "")
        run_id = str(event.get("run_id") or "")
        data = event.get("data") or {}
        if kind == "on_chat_model_stream":
            streamed_model_runs.add(run_id)
            chunk = data.get("chunk")
            text = visible_filter.feed(_chunk_text(chunk))
            if text:
                yield {"type": "token", "content": text}
        elif kind == "on_chat_model_end" and run_id not in streamed_model_runs:
            output = data.get("output")
            text = visible_filter.feed(_chunk_text(output), final=True)
            if text:
                yield {"type": "token", "content": text}
        elif kind == "on_tool_start":
            yield {"type": "tool_start", "tool": name[:120]}
        elif kind == "on_tool_end":
            output = data.get("output")
            output_text = str(getattr(output, "content", output) or "")
            yield {"type": "tool_end", "tool": name[:120], "output_chars": len(output_text)}
        elif kind == "on_chain_end" and name == "approval_required":
            output = data.get("output") or {}
            yield {
                "type": "approval_required",
                "tools": [str(item)[:120] for item in output.get("pending_approvals", [])]
                if isinstance(output, dict)
                else [],
            }
        elif kind == "on_chain_end" and name == "tool_not_allowlisted":
            output = data.get("output") or {}
            yield {
                "type": "tool_not_allowlisted",
                "tools": [str(item)[:120] for item in output.get("rejected_tools", [])]
                if isinstance(output, dict)
                else [],
            }
        elif kind == "on_chain_end" and name == "loop_limit":
            yield {"type": "loop_limit"}
    tail = visible_filter.feed("", final=True)
    if tail:
        yield {"type": "token", "content": tail}
