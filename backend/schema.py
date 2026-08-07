from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field


NodeType = Literal["start", "buzz", "planner", "coder", "file", "task", "agent"]
NODE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,119}$"
EDGE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,159}$"


class AgentState(TypedDict):
    """Persistent state for the opt-in cyclic local agent loop."""

    # The reducer appends messages across agent/tool turns instead of overwriting history.
    messages: Annotated[Sequence[BaseMessage], operator.add]
    workspace_root: str
    project_id: str | None
    pending_approvals: list[str]
    active_hardware_lane: str
    approved_tools: NotRequired[list[str]]
    tool_outputs: NotRequired[list[str]]
    rejected_tools: NotRequired[list[str]]
    loop_count: NotRequired[int]
    max_loops: NotRequired[int]
    last_error: NotRequired[str | None]
    run_id: NotRequired[str]


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=120, pattern=NODE_ID_PATTERN)
    type: NodeType
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=160, pattern=EDGE_ID_PATTERN)
    source: str = Field(min_length=1, max_length=120, pattern=NODE_ID_PATTERN)
    target: str = Field(min_length=1, max_length=120, pattern=NODE_ID_PATTERN)


class GraphDocument(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list, max_length=80)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=160)


class ProjectPayload(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    canvas_state: GraphDocument


class RunPayload(BaseModel):
    graph: GraphDocument
    input_text: str = Field(default="", max_length=200_000)
    project_id: str | None = Field(default=None, max_length=64)


class ValidationPayload(BaseModel):
    graph: GraphDocument


class ChatStreamPayload(BaseModel):
    message: str = Field(min_length=1, max_length=200_000)
    project_id: str | None = Field(default=None, max_length=64)
    active_hardware_lane: str = Field(default="shared-rtx-2070-super", max_length=120)
    approved_tools: list[str] = Field(default_factory=list, max_length=32)
    max_loops: int = Field(default=4, ge=1, le=8)
