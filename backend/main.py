from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from .database import Project, SessionLocal, get_db, list_projects
from .agent_engine import (
    DEFAULT_LFM_BASE_URL,
    DEFAULT_LFM_MODEL,
    AgentEngineError,
    initial_agent_state,
    stream_lfm_events,
)
from .graph import (
    DEFAULT_MINIMAX_MODEL,
    DEFAULT_NANBEIGE_BASE_URL,
    DEFAULT_NANBEIGE_MODEL,
    DEFAULT_OLLAMA_MODEL,
    GraphValidationError,
    configured_agents,
    run_graph,
    stream_graph,
    validate_graph,
)
from .schema import ChatStreamPayload, ProjectPayload, RunPayload, ValidationPayload
from .tools import WORKSPACE_TOOL_CATALOG, WORKSPACE_TOOL_NAMES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", str(PROJECT_ROOT))).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def _cors_origins() -> list[str]:
    raw = os.getenv("WORKSPACE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="M⊕ AI Visual Workspace API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _project_response(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "canvas_state": project.canvas_state or {"nodes": [], "edges": []},
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def _execution_error(exc: Exception) -> dict[str, str]:
    return {
        "detail": str(getattr(exc, "detail", "Workflow execution failed")),
        "failure_class": str(getattr(exc, "failure_class", type(exc).__name__.lower())),
    }


def _nanbeige_ready(provider: str) -> bool:
    if provider != "nanbeige":
        return False
    base_url = os.getenv("NANBEIGE_BASE_URL", DEFAULT_NANBEIGE_BASE_URL).strip().rstrip("/")
    if base_url != DEFAULT_NANBEIGE_BASE_URL:
        return False
    try:
        with httpx.Client(timeout=0.75, trust_env=False) as client:
            response = client.get(f"{base_url}/models")
            response.raise_for_status()
            payload = response.json()
        return isinstance(payload, dict) and any(
            isinstance(item, dict) and item.get("id") == DEFAULT_NANBEIGE_MODEL
            for item in payload.get("data", [])
        )
    except (httpx.HTTPError, TypeError, ValueError):
        return False


def _lfm_ready() -> bool:
    base_url = os.getenv("LFM_BASE_URL", DEFAULT_LFM_BASE_URL).strip().rstrip("/")
    model = os.getenv("LFM_MODEL", DEFAULT_LFM_MODEL).strip()
    if base_url != DEFAULT_LFM_BASE_URL or model != DEFAULT_LFM_MODEL:
        return False
    try:
        with httpx.Client(timeout=0.75, trust_env=False) as client:
            response = client.get(f"{base_url}/models")
            response.raise_for_status()
            payload = response.json()
        return isinstance(payload, dict) and any(
            isinstance(item, dict) and item.get("id") == DEFAULT_LFM_MODEL
            for item in payload.get("data", [])
        )
    except (httpx.HTTPError, TypeError, ValueError):
        return False


@app.get("/api/health")
def health() -> dict[str, Any]:
    model_provider = os.getenv("WORKSPACE_MODEL_PROVIDER", "nanbeige").strip().lower()
    return {
        "status": "ok",
        "workspace_root": str(WORKSPACE_ROOT),
        "model_provider": model_provider,
        "nanbeige_base_url": os.getenv("NANBEIGE_BASE_URL", DEFAULT_NANBEIGE_BASE_URL),
        "nanbeige_model": os.getenv("NANBEIGE_MODEL", DEFAULT_NANBEIGE_MODEL),
        "nanbeige_ready": _nanbeige_ready(model_provider),
        "lfm_base_url": os.getenv("LFM_BASE_URL", DEFAULT_LFM_BASE_URL),
        "lfm_model": os.getenv("LFM_MODEL", DEFAULT_LFM_MODEL),
        "lfm_ready": _lfm_ready(),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        "minimax_model": os.getenv("MINIMAX_MODEL", DEFAULT_MINIMAX_MODEL),
        "buzz_on_path": shutil.which(os.getenv("BUZZ_EXECUTABLE", "buzz")) is not None,
        "configured_agents": configured_agents(),
    }


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {"agents": [{"id": name, "configured": True} for name in configured_agents()]}


@app.get("/api/chat/tools")
def chat_tools() -> dict[str, Any]:
    """Expose the governed chat tool catalog without provider credentials or commands."""
    return {"tools": WORKSPACE_TOOL_CATALOG}


@app.get("/api/projects")
def get_projects(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_project_response(project) for project in list_projects(db)]


@app.post("/api/projects")
def save_project(payload: ProjectPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    project_id = payload.id or str(uuid.uuid4())
    project = db.get(Project, project_id)
    if project is None:
        project = Project(id=project_id, name=payload.name, canvas_state=payload.canvas_state.model_dump(mode="json"))
        db.add(project)
    else:
        project.name = payload.name
        project.canvas_state = payload.canvas_state.model_dump(mode="json")
    db.commit()
    db.refresh(project)
    return _project_response(project)


@app.get("/api/projects/{project_id}")
def load_project(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_response(project)


@app.post("/api/workflows/validate")
def validate_workflow(payload: ValidationPayload) -> dict[str, Any]:
    try:
        return validate_graph(payload.graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc


@app.post("/api/workflows/run")
def run_workflow(payload: RunPayload) -> dict[str, Any]:
    try:
        output, events = run_graph(
            payload.graph,
            input_text=payload.input_text,
            workspace_root=WORKSPACE_ROOT,
            project_id=payload.project_id,
        )
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_execution_error(exc)) from exc
    return {
        "run_id": str(uuid.uuid4()),
        "status": "completed",
        "output": output,
        "events": events,
    }


@app.post("/api/execute")
async def execute_workflow(payload: RunPayload) -> EventSourceResponse:
    """Execute a canvas graph and stream metadata-only LangGraph node events."""
    try:
        validate_graph(payload.graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc

    run_id = str(uuid.uuid4())
    events: list[dict[str, Any]] = []
    results: Queue[tuple[str, Any]] = Queue()

    def worker() -> None:
        try:
            result: dict[str, Any] = {}
            for _update in stream_graph(
                payload.graph,
                input_text=payload.input_text,
                workspace_root=WORKSPACE_ROOT,
                project_id=payload.project_id,
                events=events,
                result=result,
            ):
                pass
            results.put(("complete", {"output": str(result.get("last_output", payload.input_text))}))
        except Exception as exc:  # The stream exposes a bounded failure class/detail only.
            results.put(("error", _execution_error(exc)))

    Thread(target=worker, name=f"workspace-run-{run_id[:8]}", daemon=True).start()

    async def event_stream():
        yield {"id": f"{run_id}:0", "event": "run_started", "data": json.dumps({"run_id": run_id})}
        emitted = 0
        while True:
            while emitted < len(events):
                event_number = emitted + 1
                yield {
                    "id": f"{run_id}:{event_number}",
                    "event": "node",
                    "data": json.dumps({"run_id": run_id, **events[emitted]}),
                }
                emitted += 1
            if not results.empty() and emitted >= len(events):
                break
            await asyncio.sleep(0.05)
        kind, result = results.get()
        if kind == "error":
            yield {
                "id": f"{run_id}:error",
                "event": "error",
                "data": json.dumps({"run_id": run_id, **result}),
            }
            return
        yield {
            "id": f"{run_id}:complete",
            "event": "complete",
            "data": json.dumps({"run_id": run_id, "status": "completed", "output": result["output"]}),
        }

    return EventSourceResponse(
        event_stream(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatStreamPayload) -> EventSourceResponse:
    """Stream the opt-in LFM agent/tool loop without altering canvas execution."""
    run_id = str(uuid.uuid4())
    approved_tools = [
        tool_name
        for tool_name in payload.approved_tools
        if tool_name in WORKSPACE_TOOL_NAMES
    ]
    state = initial_agent_state(
        HumanMessage(content=payload.message),
        workspace_root=str(WORKSPACE_ROOT),
        project_id=payload.project_id,
        active_hardware_lane=payload.active_hardware_lane,
        approved_tools=approved_tools,
        max_loops=payload.max_loops,
        run_id=run_id,
    )

    async def event_stream():
        sequence = 0
        approval_required = False
        loop_limit = False
        tool_not_allowlisted = False
        yield {
            "id": f"{run_id}:0",
            "event": "run_started",
            "data": json.dumps({"run_id": run_id, "model": DEFAULT_LFM_MODEL}),
        }
        try:
            async for event in stream_lfm_events(state):
                sequence += 1
                if event.get("type") == "approval_required":
                    approval_required = True
                elif event.get("type") == "tool_not_allowlisted":
                    tool_not_allowlisted = True
                elif event.get("type") == "loop_limit":
                    loop_limit = True
                yield {
                    "id": f"{run_id}:{sequence}",
                    "event": str(event.get("type", "message")),
                    "data": json.dumps({"run_id": run_id, **event}),
                }
            sequence += 1
            yield {
                "id": f"{run_id}:{sequence}",
                "event": "complete",
                "data": json.dumps(
                    {
                        "run_id": run_id,
                        "status": "awaiting_approval"
                        if approval_required
                        else "blocked"
                        if tool_not_allowlisted
                        else "loop_limit"
                        if loop_limit
                        else "completed",
                    }
                ),
            }
        except Exception as exc:  # Keep failures bounded and model-content-free.
            sequence += 1
            error = _execution_error(exc)
            yield {
                "id": f"{run_id}:error",
                "event": "error",
                "data": json.dumps({"run_id": run_id, **error}),
            }

    return EventSourceResponse(
        event_stream(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/tasks")
def get_tasks(project_id: str | None = None) -> list[dict[str, Any]]:
    # Task browsing is intentionally kept small in the first slice. Task nodes write
    # to SQLite; a later UI can add full task editing without changing graph execution.
    from .database import TaskItem
    from sqlalchemy import select

    with SessionLocal() as db:
        statement = select(TaskItem).order_by(TaskItem.updated_at.desc())
        if project_id:
            statement = statement.where(TaskItem.project_id == project_id)
        tasks = db.scalars(statement).all()
        return [
            {
                "id": task.id,
                "project_id": task.project_id,
                "title": task.title,
                "status": task.status,
                "notes": task.notes,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]
