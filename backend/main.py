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

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from .database import FeedbackItem, Project, SessionLocal, get_db, list_projects, utc_now
from .agent_engine import (
    DEFAULT_LFM_MODEL,
    AgentEngineError,
    initial_agent_state,
    stream_lfm_events,
)
from .graph import (
    DEFAULT_MINIMAX_MODEL,
    GraphValidationError,
    configured_agents,
    run_graph,
    stream_graph,
    transcribe_audio,
    validate_graph,
)
from .schema import ChatStreamPayload, FeedbackPayload, FeedbackPublishPayload, ProjectPayload, RunChatPayload, RunDecisionPayload, RunPayload, ValidationPayload
from .execution_runtime import (
    cancel_run,
    create_run,
    decide_run,
    delete_run,
    events_after,
    get_run,
    list_runs,
)
from .runtime_control import list_runtime_profiles, preflight_runtime_profile
from .plugins import plugin_catalog
from .terminal_control import TerminalPreviewRequest, preview_terminal_command
from .upgrade_control import upgrade_inventory, upgrade_preflight
from .ollama_control import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaPreflightPayload, list_ollama_models, preflight_ollama_model
from .model_settings import WorkspaceModelPayload, get_workspace_model_setting, save_workspace_model_setting
from .model_profiles import (
    EndpointProfilePayload,
    HardwareProfilePayload,
    delete_endpoint_profile,
    gpu_inventory,
    gpu_process_inventory,
    list_endpoint_profiles,
    list_hardware_profiles,
    managed_ollama_launch_spec,
    preflight_endpoint,
    save_endpoint_profile,
    save_hardware_profile,
)
from .library import (
    ActionPreviewPayload,
    ActionRunPayload,
    GraphApprovalPayload,
    TemplateInstantiatePayload,
    capability_audit,
    consume_graph_preview,
    get_resource,
    instantiate_template,
    preview_action,
    preview_graph,
    query_library,
    run_action,
)
from .tools import WORKSPACE_TOOL_CATALOG, WORKSPACE_TOOL_NAMES
from .hermes_adapter import hermes_capability_audit
from .capability_matrix import build_capability_matrix, capability_matrix_markdown
from .feedback import FeedbackPublishError, github_publish_preview, publish_feedback_to_github
from .options_registry import option_inventory, option_inventory_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", str(PROJECT_ROOT))).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
MAX_CAPTURE_BYTES = 50 * 1024 * 1024
MAX_CAPTURE_DURATION_MS = 5 * 60 * 1000


def _cors_origins() -> list[str]:
    raw = os.getenv("WORKSPACE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="M⊕ AI Visual Workspace API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.post("/api/audio/transcribe")
async def transcribe_local_capture(request: Request, model_size: str = "small", consent: bool = False, duration_ms: int = 0) -> dict[str, Any]:
    if not consent:
        raise HTTPException(status_code=403, detail="explicit microphone capture consent is required")
    if duration_ms < 0 or duration_ms > MAX_CAPTURE_DURATION_MS:
        raise HTTPException(status_code=400, detail="capture duration exceeds the five-minute limit")
    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail="captured audio exceeds the 50 MiB limit")
    audio = await request.body()
    if not audio or len(audio) > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=400 if not audio else 413, detail="captured audio is empty or exceeds the size limit")
    content_type = request.headers.get("content-type", "audio/webm").split(";", 1)[0].strip().lower()
    suffix = {"audio/webm": ".webm", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a"}.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=415, detail="captured audio content type is unsupported")
    capture_id = uuid.uuid4().hex
    relative = Path(".runtime") / "audio" / f"capture-{capture_id}{suffix}"
    audio_path = (WORKSPACE_ROOT / relative).resolve()
    transcript_path = audio_path.with_suffix(".txt")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        audio_path.write_bytes(audio)
        transcript = transcribe_audio(relative.as_posix(), model_size, WORKSPACE_ROOT)
        return {"transcript": transcript, "provenance": {"capture_id": capture_id, "source_kind": "explicit_microphone_capture", "provider": "buzz-whispercpp-local", "model_size": model_size, "duration_ms": duration_ms, "audio_bytes": len(audio), "temporary_audio_deleted": True}}
    except Exception as exc:
        failure_class = str(getattr(exc, "failure_class", type(exc).__name__.lower()))
        detail = str(getattr(exc, "detail", exc))
        raise HTTPException(status_code=503, detail=f"{failure_class}: {detail}") from exc
    finally:
        for artifact in (transcript_path, audio_path):
            try:
                artifact.unlink(missing_ok=True)
            except OSError:
                pass


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


@app.get("/api/health")
def health() -> dict[str, Any]:
    setting = get_workspace_model_setting()
    preflight = preflight_ollama_model(str(setting["model"]))
    return {
        "status": "ok",
        "workspace_root": str(WORKSPACE_ROOT),
        "model_provider": setting["provider"],
        "model": setting["model"],
        "model_ready": preflight.get("status") == "ready" and preflight.get("exact_model") is True,
        "model_persisted": setting["persisted"],
        "hardware_profile_id": setting["hardware_profile_id"],
        "fallback_policy": "explicit_only",
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        "ollama_model": setting["model"],
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


@app.get("/api/library")
def library(category: str | None = None, query: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    """Return the normalized local tool, agent, skill, model, runtime, and template registry."""
    return query_library(category=category, query=query, limit=limit, offset=offset)


@app.get("/api/library/capability-audit")
def library_capability_audit() -> dict[str, Any]:
    return capability_audit()


@app.get("/api/hermes/capability-audit")
def get_hermes_capability_audit() -> dict[str, Any]:
    return hermes_capability_audit()


@app.get("/api/capabilities/matrix")
def get_capability_matrix() -> dict[str, Any]:
    return build_capability_matrix(app.routes)


@app.get("/api/capabilities/export.md", response_class=PlainTextResponse)
def export_capability_matrix() -> PlainTextResponse:
    return PlainTextResponse(capability_matrix_markdown(build_capability_matrix(app.routes)), media_type="text/markdown")


@app.get("/api/options")
def get_option_inventory() -> dict[str, Any]:
    """Return the Phase 0 read-only option contract; no setting is applied here."""
    return option_inventory()


@app.get("/api/options/export.md", response_class=PlainTextResponse)
def export_option_inventory() -> PlainTextResponse:
    return PlainTextResponse(option_inventory_markdown(option_inventory()), media_type="text/markdown")


@app.get("/api/plugins")
def plugins() -> dict[str, Any]:
    return {"plugins": plugin_catalog(), "mutation": "none"}


@app.get("/api/library/{resource_id:path}")
def library_resource(resource_id: str) -> dict[str, Any]:
    try:
        return get_resource(resource_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Library resource not found") from exc


@app.post("/api/actions/preview")
def action_preview(payload: ActionPreviewPayload) -> dict[str, Any]:
    try:
        return preview_action(payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/actions/run")
def action_run(payload: ActionRunPayload) -> dict[str, Any]:
    try:
        return run_action(payload, WORKSPACE_ROOT)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/templates")
def templates() -> dict[str, Any]:
    return query_library(category="template", limit=200)


@app.post("/api/templates/{template_id}/instantiate")
def template_instantiate(template_id: str, payload: TemplateInstantiatePayload) -> dict[str, Any]:
    try:
        return instantiate_template(template_id, payload.options)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workflow template not found") from exc


@app.post("/api/templates/preview-run")
def template_preview_run(payload: GraphApprovalPayload) -> dict[str, Any]:
    try:
        validate_graph(payload.graph)
        return preview_graph(payload.graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc


@app.get("/api/ollama/models")
def ollama_models() -> dict[str, Any]:
    """Discover exact locally installed Ollama model IDs without pulling or mutating models."""
    return list_ollama_models()


@app.post("/api/ollama/preflight")
def ollama_preflight(payload: OllamaPreflightPayload) -> dict[str, Any]:
    """Require an exact installed Ollama model before a workflow can invoke it."""
    return preflight_ollama_model(payload.model)


@app.get("/api/settings/model")
def workspace_model_setting() -> dict[str, Any]:
    """Return the persistent global M⊕ model selection without mutating it."""
    return get_workspace_model_setting()


@app.put("/api/settings/model")
def workspace_model_setting_save(payload: WorkspaceModelPayload) -> dict[str, Any]:
    """Persist one exact installed Ollama model as the global M⊕ default."""
    try:
        return save_workspace_model_setting(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runtime/profiles")
def runtime_profiles() -> dict[str, Any]:
    """Return named, data-only GPU/model profiles; this route never activates a listener."""
    return {"profiles": list_runtime_profiles(), "mutation": "none"}


@app.get("/api/runtime/profiles/{profile_id}/preflight")
def runtime_profile_preflight(profile_id: str) -> dict[str, Any]:
    """Check a named profile's exact local model identity without changing runtime state."""
    return preflight_runtime_profile(profile_id)


@app.get("/api/model-endpoints")
def model_endpoint_profiles(readiness: bool = False) -> dict[str, Any]:
    return {"profiles": list_endpoint_profiles(include_readiness=readiness)}


@app.post("/api/model-endpoints")
def model_endpoint_save(payload: EndpointProfilePayload) -> dict[str, Any]:
    try:
        return save_endpoint_profile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/model-endpoints/{profile_id}/preflight")
def model_endpoint_preflight(profile_id: str) -> dict[str, Any]:
    try:
        return preflight_endpoint(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Endpoint profile not found") from exc


@app.delete("/api/model-endpoints/{profile_id}")
def model_endpoint_delete(profile_id: str) -> dict[str, str]:
    try:
        delete_endpoint_profile(profile_id)
        return {"status": "deleted", "profile_id": profile_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Endpoint profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/hardware/gpus")
def hardware_gpus() -> dict[str, Any]:
    return {"devices": gpu_inventory(), "processes": gpu_process_inventory(), "mutation": "none", "process_fields": ["pid", "gpu_uuid", "process_name", "used_memory_mb"]}


@app.get("/api/hardware/profiles")
def hardware_profiles() -> dict[str, Any]:
    return {"profiles": list_hardware_profiles()}


@app.post("/api/hardware/profiles")
def hardware_profile_save(payload: HardwareProfilePayload) -> dict[str, Any]:
    try:
        return save_hardware_profile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/hardware/profiles/{profile_id}/ollama-launch-preview")
def hardware_profile_launch_preview(profile_id: str, port: int) -> dict[str, Any]:
    try:
        return managed_ollama_launch_spec(profile_id, port)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Hardware profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/terminal/preview")
def terminal_preview(payload: TerminalPreviewRequest) -> dict[str, Any]:
    """Classify a bounded terminal request; no command execution is exposed here."""
    return preview_terminal_command(payload)


@app.get("/api/upgrades/inventory")
def upgrades_inventory() -> dict[str, Any]:
    return upgrade_inventory()


@app.get("/api/upgrades/preflight")
def upgrades_preflight() -> dict[str, Any]:
    return upgrade_preflight()


def _feedback_response(item: FeedbackItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "description": item.description,
        "steps": item.steps,
        "project_id": item.project_id,
        "run_id": item.run_id,
        "context_receipt": item.context_receipt or {},
        "status": item.status,
        "github_issue_number": item.github_issue_number,
        "github_url": item.github_url,
        "failure_class": item.failure_class,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@app.get("/api/feedback")
def feedback_list(limit: int = 100, db: Session = Depends(get_db)) -> dict[str, Any]:
    bounded_limit = min(max(int(limit), 1), 200)
    items = db.query(FeedbackItem).order_by(FeedbackItem.updated_at.desc()).limit(bounded_limit).all()
    return {"items": [_feedback_response(item) for item in items], "mutation": "none"}


@app.post("/api/feedback")
def feedback_create(payload: FeedbackPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = FeedbackItem(
        id=f"feedback-{uuid.uuid4().hex[:16]}",
        kind=payload.kind,
        title=payload.title.strip(),
        description=payload.description.strip(),
        steps=payload.steps.strip(),
        project_id=payload.project_id,
        run_id=payload.run_id,
        context_receipt={"source": "local-ui", "created_at": utc_now().isoformat(), "raw_content_logged": False},
        status="draft",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _feedback_response(item)


@app.get("/api/feedback/{feedback_id}/publish-preview")
def feedback_publish_preview(feedback_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(FeedbackItem, feedback_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback draft not found")
    return {"feedback_id": feedback_id, **github_publish_preview(item)}


@app.post("/api/feedback/{feedback_id}/publish")
def feedback_publish(feedback_id: str, payload: FeedbackPublishPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(FeedbackItem, feedback_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback draft not found")
    if item.status == "published" and item.github_url:
        return _feedback_response(item)
    try:
        receipt = publish_feedback_to_github(item)
    except FeedbackPublishError as exc:
        item.status = "publish_failed"
        item.failure_class = exc.failure_class
        item.updated_at = utc_now()
        db.commit()
        raise HTTPException(status_code=503, detail=exc.detail) from exc
    item.status = "published"
    item.failure_class = ""
    item.github_issue_number = int(receipt["number"])
    item.github_url = str(receipt["url"])
    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)
    return {**_feedback_response(item), "publish_receipt": {"repository": receipt["repository"], "number": receipt["number"], "url": receipt["url"]}}


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


@app.post("/api/runs")
def create_durable_run(payload: RunPayload) -> dict[str, Any]:
    try:
        approved_resources = consume_graph_preview(payload.approval_preview_id, payload.graph) if payload.approval_policy == "preflight" else set()
        return create_run(payload, WORKSPACE_ROOT, approved_resources)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs")
def durable_runs(project_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    return {"runs": list_runs(project_id=project_id, limit=limit)}


@app.get("/api/runs/{run_id}")
def durable_run(run_id: str) -> dict[str, Any]:
    try:
        return get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/events")
def durable_run_events(run_id: str, after: int = 0) -> dict[str, Any]:
    try:
        return {"events": events_after(run_id, after)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/stream")
async def durable_run_stream(run_id: str, after: int = 0) -> EventSourceResponse:
    try:
        get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    async def event_stream():
        cursor = max(after, 0)
        while True:
            batch = events_after(run_id, cursor)
            for item in batch:
                cursor = int(item["sequence"])
                yield {"id": f"{run_id}:{cursor}", "event": item["event_type"], "data": json.dumps({"run_id": run_id, **item["payload"]})}
            snapshot = get_run(run_id)
            if snapshot["status"] in {"completed", "error", "cancelled", "denied"} and not batch:
                return
            await asyncio.sleep(0.2)

    return EventSourceResponse(event_stream())


@app.post("/api/runs/{run_id}/approvals/{approval_id}")
def durable_run_decision(run_id: str, approval_id: str, payload: RunDecisionPayload) -> dict[str, Any]:
    try:
        return decide_run(
            run_id,
            approval_id,
            payload.decision,
            arguments=payload.arguments,
            note=payload.note,
            approve_identical=payload.approve_identical,
            workspace_root=WORKSPACE_ROOT,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run or approval not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/input")
def durable_run_input(run_id: str, payload: RunChatPayload) -> dict[str, Any]:
    try:
        snapshot = get_run(run_id)
        pending = next((item for item in snapshot["approvals"] if item["status"] == "pending" and item["action_type"] == "chat_input"), None)
        if pending is None:
            raise ValueError("run is not waiting for chat input")
        return decide_run(run_id, pending["id"], "approve", arguments={"content": payload.content}, workspace_root=WORKSPACE_ROOT)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/cancel")
def durable_run_cancel(run_id: str) -> dict[str, Any]:
    try:
        return cancel_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/runs/{run_id}")
def durable_run_delete(run_id: str) -> dict[str, str]:
    try:
        delete_run(run_id)
        return {"status": "deleted", "run_id": run_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/workflows/run")
def run_workflow(payload: RunPayload) -> dict[str, Any]:
    try:
        approved_resources = consume_graph_preview(payload.approval_preview_id, payload.graph)
        output, events = run_graph(
            payload.graph,
            input_text=payload.input_text,
            workspace_root=WORKSPACE_ROOT,
            project_id=payload.project_id,
            approved_resources=approved_resources,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
        approved_resources = consume_graph_preview(payload.approval_preview_id, payload.graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

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
                approved_resources=approved_resources,
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
            "data": json.dumps({"run_id": run_id, "model": _lfm_model()}),
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
