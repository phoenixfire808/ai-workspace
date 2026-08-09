from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from .database import ApprovalRequest, DelegateChild, RunEvent, RunStep, SessionLocal, WorkflowRun, utc_now
from .graph import ExecutionContext, NodeExecutionError, _execute_node, take_agent_process, validate_graph
from .hermes_adapter import take_dispatch_process
from .schema import GraphDocument, GraphNode, RunPayload
from .tools import APPROVAL_REQUIRED_TOOLS, WORKSPACE_TOOL_CATALOG, preview_workspace_mutation, preview_workspace_write
from .plugins import PluginError, execute_plugin

MAX_CONTEXT_CHARS = 200_000
MAX_DIFF_CHARS = 24_000
MAX_CHUNKS = 256
_MUTATION_TOOLS = {"create_workspace_file", "patch_workspace_file", "rename_workspace_file", "delete_workspace_file"}
_WEB_NODE_TO_TOOL = {"search": "search_web", "research": "deep_research", "source_context": "build_research_context"}
_workers: set[str] = set()
_workers_lock = threading.Lock()


def _bounded(value: Any, limit: int = MAX_CONTEXT_CHARS) -> str:
    text = str(value or "")
    return text if len(text) <= limit else f"{text[:limit]}\n[truncated]"


def _web_provenance(output: str) -> dict[str, Any]:
    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or not any(key in payload for key in ("backend", "sources", "context_id", "source_id", "failure_class")):
        return {}
    sources: list[dict[str, Any]] = []
    for item in payload.get("sources", [])[:24] if isinstance(payload.get("sources"), list) else []:
        if not isinstance(item, dict):
            continue
        sources.append({key: item.get(key) for key in ("source_id", "title", "url", "domain", "rank", "extraction_status", "failure_class") if item.get(key) not in (None, "")})
    return {
        key: payload.get(key)
        for key in ("status", "backend", "query", "query_count", "result_count", "selected_count", "domain_count", "context_id", "packet_sha256", "char_count", "truncated", "citations", "failure_class", "detail")
        if payload.get(key) not in (None, "")
    } | ({"sources": sources} if sources else {})


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _topological_order(document: GraphDocument) -> list[str]:
    incoming = {node.id: 0 for node in document.nodes}
    outgoing = {node.id: [] for node in document.nodes}
    for edge in document.edges:
        incoming[edge.target] += 1
        outgoing[edge.source].append(edge.target)
    queue = sorted((node_id for node_id, degree in incoming.items() if degree == 0))
    result: list[str] = []
    while queue:
        node_id = queue.pop(0)
        result.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
                queue.sort()
    return result


def _emit(db: Any, run_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    sequence = int(db.scalar(select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)) or 0) + 1
    event = RunEvent(run_id=run_id, sequence=sequence, event_type=event_type, payload=payload)
    db.add(event)
    return {"sequence": sequence, "event_type": event_type, "payload": payload}


def _step_payload(step: RunStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "node_id": step.node_id,
        "node_type": step.node_type,
        "branch_key": step.branch_key,
        "chunk_index": step.chunk_index,
        "status": step.status,
        "input_context": step.input_context or {},
        "arguments": step.arguments or {},
        "output": step.output,
        "provenance": _web_provenance(step.output),
        "failure_class": step.failure_class,
        "error_detail": step.error_detail,
        "duration_ms": step.duration_ms,
        "created_at": step.created_at.isoformat() if step.created_at else None,
        "updated_at": step.updated_at.isoformat() if step.updated_at else None,
    }


def _approval_payload(item: ApprovalRequest) -> dict[str, Any]:
    return {
        "id": item.id,
        "step_id": item.step_id,
        "action_type": item.action_type,
        "subject_hash": item.subject_hash,
        "status": item.status,
        "arguments": item.arguments or {},
        "impact_preview": item.impact_preview,
        "note": item.note,
        "approve_identical": item.approve_identical,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "decided_at": item.decided_at.isoformat() if item.decided_at else None,
    }


def _child_payload(item: DelegateChild) -> dict[str, Any]:
    return {"id": item.id, "child_run_id": item.id, "parent_run_id": item.parent_run_id, "subtask_id": item.subtask_id, "parent_step_id": item.parent_step_id, "worker_target": item.worker_target, "assignment": item.assignment, "status": item.status, "process_id": item.process_id, "receipt": item.receipt or {}, "output": item.output, "failure_class": item.failure_class, "created_at": item.created_at.isoformat() if item.created_at else None, "updated_at": item.updated_at.isoformat() if item.updated_at else None}


def _monitor_delegate_child(child_id: str, process: Any) -> None:
    started = time.perf_counter()
    try:
        stdout, _stderr = process.communicate(timeout=3600)
        status = "completed" if process.returncode == 0 else "error"
        output = _bounded(stdout, 200_000) if status == "completed" else ""
        failure_class = "" if status == "completed" else "worker_exit_nonzero"
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        status, output, failure_class = "error", "", "worker_timeout"
    except Exception:
        status, output, failure_class = "error", "", "worker_monitor_failed"
    with SessionLocal() as child_db:
        item = child_db.get(DelegateChild, child_id)
        if item is None:
            return
        item.status = status
        item.output = output
        item.failure_class = failure_class
        completion = {"status": status, "failure_class": failure_class, "duration_ms": round((time.perf_counter() - started) * 1000)}
        item.receipt = {**(item.receipt if isinstance(item.receipt, dict) else {}), "completion": completion}
        item.updated_at = utc_now()
        parent = child_db.get(WorkflowRun, item.parent_run_id)
        if parent is not None:
            parent.updated_at = utc_now()
        _emit(child_db, item.parent_run_id, "delegate_child_completed", {"run_id": item.parent_run_id, "parent_step_id": item.parent_step_id, "child_id": item.subtask_id, "child_run_id": item.id, "status": status, "failure_class": failure_class, "duration_ms": completion["duration_ms"]})
        child_db.commit()


def _persist_delegate_children(db: Any, run_id: str, step_id: str, output: str, context_receipt: dict[str, Any] | None = None) -> list[tuple[str, Any]]:
    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    children = payload.get("children") if isinstance(payload, dict) else None
    if not isinstance(children, list):
        return []
    monitors: list[tuple[str, Any]] = []
    for raw in children[:16]:
        if not isinstance(raw, dict):
            continue
        subtask_id = str(raw.get("child_id") or uuid.uuid4().hex)[:96]
        child_pk = f"{run_id}:{subtask_id}"[:96]
        receipt = raw.get("receipt") if isinstance(raw.get("receipt"), dict) else {}
        pid = receipt.get("pid") if isinstance(receipt.get("pid"), int) else None
        item = db.get(DelegateChild, child_pk) or DelegateChild(id=child_pk, parent_run_id=run_id, parent_step_id=step_id, subtask_id=subtask_id)
        db.add(item)
        item.worker_target = str(raw.get("worker_target") or payload.get("worker_target") or "")[:160]
        item.assignment = _bounded(raw.get("subtask"), 4000)
        item.status = str(raw.get("status") or "planned")[:32]
        item.process_id = pid
        item.receipt = {
            "child_run_id": child_pk,
            "parent_run_id": run_id,
            "parent_step_id": step_id,
            "dispatch": receipt,
            "context": context_receipt or {},
        }
        item.output = _bounded(raw.get("output"), 200_000)
        item.failure_class = str(raw.get("failure_class") or "")[:120]
        item.updated_at = utc_now()
        _emit(db, run_id, "delegate_child_registered", {"run_id": run_id, "parent_step_id": step_id, "child_id": subtask_id, "child_run_id": child_pk, "status": item.status, "worker_target": item.worker_target, "process_id": pid, "context": context_receipt or {}})
        if pid is not None:
            process = take_agent_process(pid)
            if process is None:
                process = take_dispatch_process(pid)
            if process is not None:
                monitors.append((child_pk, process))
    return monitors


def get_run(run_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            raise KeyError(run_id)
        steps = list(db.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.created_at, RunStep.id)).all())
        approvals = list(db.scalars(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id).order_by(ApprovalRequest.created_at)).all())
        events = list(db.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)).all())
        children = list(db.scalars(select(DelegateChild).where(DelegateChild.parent_run_id == run_id).order_by(DelegateChild.created_at, DelegateChild.id)).all())
        return {
            "id": run.id,
            "project_id": run.project_id,
            "status": run.status,
            "approval_policy": run.approval_policy,
            "graph_snapshot": run.graph_snapshot or {},
            "input_text": run.input_text,
            "final_output": run.final_output,
            "error_detail": run.error_detail,
            "retain_context": run.retain_context,
            "max_parallel": run.max_parallel,
            "runtime_state": run.runtime_state or {},
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "steps": [_step_payload(step) for step in steps],
            "approvals": [_approval_payload(item) for item in approvals],
            "events": [{"sequence": event.sequence, "event_type": event.event_type, "payload": event.payload, "created_at": event.created_at.isoformat() if event.created_at else None} for event in events],
            "children": [_child_payload(item) for item in children],
        }


def list_runs(project_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        statement = select(WorkflowRun).order_by(WorkflowRun.updated_at.desc()).limit(min(max(limit, 1), 200))
        if project_id:
            statement = statement.where(WorkflowRun.project_id == project_id)
        runs = list(db.scalars(statement).all())
        return [{"id": run.id, "project_id": run.project_id, "status": run.status, "approval_policy": run.approval_policy, "final_output": _bounded(run.final_output, 4000), "error_detail": run.error_detail, "created_at": run.created_at.isoformat() if run.created_at else None, "updated_at": run.updated_at.isoformat() if run.updated_at else None} for run in runs]


def events_after(run_id: str, sequence: int = 0) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        if db.get(WorkflowRun, run_id) is None:
            raise KeyError(run_id)
        events = list(db.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence > max(sequence, 0)).order_by(RunEvent.sequence)).all())
        return [{"sequence": event.sequence, "event_type": event.event_type, "payload": event.payload} for event in events]


def delete_run(run_id: str) -> None:
    with SessionLocal() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status in {"running", "committing"}:
            raise ValueError("a running workflow must be cancelled before deletion")
        active_child = db.scalar(select(DelegateChild).where(DelegateChild.parent_run_id == run_id, DelegateChild.status.in_(["queued", "running"])).limit(1))
        if active_child is not None:
            raise ValueError("a run with active delegated children cannot be deleted")
        db.execute(delete(ApprovalRequest).where(ApprovalRequest.run_id == run_id))
        db.execute(delete(RunEvent).where(RunEvent.run_id == run_id))
        db.execute(delete(DelegateChild).where(DelegateChild.parent_run_id == run_id))
        db.execute(delete(RunStep).where(RunStep.run_id == run_id))
        db.delete(run)
        db.commit()


def _split_value(value: str, data: dict[str, Any]) -> list[str]:
    strategy = str(data.get("chunk_strategy") or "paragraphs")
    size = min(max(int(data.get("chunk_size") or 2000), 1), 50_000)
    overlap = min(max(int(data.get("chunk_overlap") or 0), 0), size - 1)
    maximum = min(max(int(data.get("max_chunks") or 64), 1), MAX_CHUNKS)
    if strategy == "lines":
        chunks = value.splitlines()
    elif strategy == "paragraphs":
        chunks = [item for item in re.split(r"\n\s*\n", value) if item]
    elif strategy == "json_items":
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise NodeExecutionError("chunk input must be a JSON array", "chunk_json_invalid")
        chunks = [json.dumps(item, ensure_ascii=False) for item in parsed]
    else:
        step = max(size - overlap, 1)
        chunks = [value[index : index + size] for index in range(0, len(value), step)] or [""]
    return [_bounded(item) for item in chunks[:maximum]]


def _merge_values(values: list[str], data: dict[str, Any]) -> str:
    strategy = str(data.get("merge_strategy") or "concatenate")
    if strategy == "json_array":
        return json.dumps(values, ensure_ascii=False)
    if strategy == "labeled_object":
        return json.dumps({str(index): value for index, value in enumerate(values)}, ensure_ascii=False)
    if strategy == "first_success":
        return next((value for value in values if value and not value.startswith("Error:")), values[0] if values else "")
    return str(data.get("separator") or "\n\n").join(values)


def _condition_matches(condition: dict[str, Any], value: str) -> bool:
    if not condition:
        return True
    operator = str(condition.get("operator") or "always")
    expected = str(condition.get("value") or "")
    if operator == "equals":
        return value == expected
    if operator == "contains":
        return expected in value
    if operator == "regex":
        if len(expected) > 500:
            return False
        try:
            return re.search(expected, value[:MAX_CONTEXT_CHARS]) is not None
        except re.error:
            return False
    if operator == "route_label":
        try:
            parsed = json.loads(value)
            return isinstance(parsed, dict) and str(parsed.get("route")) == expected
        except json.JSONDecodeError:
            return False
    return operator == "always"


def _protected_action(node: GraphNode, policy: str) -> str | None:
    if node.type == "review":
        return "human_review"
    if node.type == "chat":
        return "chat_input"
    if policy == "step_through":
        return "step_review"
    if node.type == "delegate" and str(node.data.get("dispatch_mode") or "plan_only") != "plan_only":
        return f"delegate:{node.id}"
    if node.type == "agent":
        return "agent_dispatch"
    if node.type == "file" and str(node.data.get("mode") or "read") != "read":
        return "workspace_file_mutation"
    if node.type == "tool":
        resource_id = str(node.data.get("resource_id") or "")
        name = resource_id.split(":", 1)[1] if resource_id.startswith("tool:") else ""
        catalog = {str(item["name"]): item for item in WORKSPACE_TOOL_CATALOG}
        if catalog.get(name, {}).get("requires_approval"):
            return resource_id
    endpoint = str(node.data.get("endpoint_profile") or "")
    if node.type in {"planner", "coder", "merge"} and endpoint and not endpoint.startswith(("local-", "loopback-")):
        return "remote_model_request"
    return None


def _normalized_node(node: GraphNode, value: str = "") -> tuple[GraphNode, str]:
    if node.type in _WEB_NODE_TO_TOOL:
        name = _WEB_NODE_TO_TOOL[node.type]
        if node.type == "search":
            arguments = {"query": str(node.data.get("query") or value), "categories": str(node.data.get("categories") or "general"), "time_range": str(node.data.get("time_range") or ""), "language": str(node.data.get("language") or "en"), "safe_search": int(node.data.get("safe_search") or 1), "max_results": int(node.data.get("max_results") or 10), "domains": list(node.data.get("domains") or [])}
        elif node.type == "research":
            raw_queries = node.data.get("queries") or []
            queries = [item.strip() for item in raw_queries.splitlines() if item.strip()] if isinstance(raw_queries, str) else list(raw_queries)
            arguments = {"query": str(node.data.get("query") or value), "queries": queries, "categories": str(node.data.get("categories") or "general"), "time_range": str(node.data.get("time_range") or ""), "language": str(node.data.get("language") or "en"), "safe_search": int(node.data.get("safe_search") or 1), "max_results_per_query": int(node.data.get("max_results_per_query") or 8), "max_pages": int(node.data.get("max_pages") or 12), "per_domain": int(node.data.get("per_domain") or 2), "extract_pages": node.data.get("extract_pages") is not False}
        else:
            arguments = {"sources": list(node.data.get("sources") or []), "context_text": str(node.data.get("context_text") or value), "max_chars": int(node.data.get("max_chars") or 30_000)}
        return node.model_copy(update={"type": "tool", "data": {**node.data, "resource_id": f"tool:{name}", "arguments": arguments}}), ""
    if node.type == "file" and str(node.data.get("mode") or "read") != "read":
        mode = str(node.data.get("mode") or "write")
        if mode == "write":
            name, arguments, impact = preview_workspace_write(str(node.data.get("path") or ""), value)
        else:
            name = {"create": "create_workspace_file", "patch": "patch_workspace_file", "rename": "rename_workspace_file", "delete": "delete_workspace_file"}.get(mode, "")
            if not name:
                raise NodeExecutionError("unsupported file mutation mode", "file_mode_invalid")
            arguments = dict(node.data.get("arguments") or {})
            if node.data.get("path") and "relative_path" not in arguments:
                arguments["relative_path"] = node.data["path"]
            impact = preview_workspace_mutation(name, arguments)
            for key in ("expected_absent", "expected_sha256"):
                if key in impact:
                    arguments[key] = impact[key]
        return node.model_copy(update={"type": "tool", "data": {**node.data, "resource_id": f"tool:{name}", "arguments": arguments}}), str(impact.get("diff", ""))[:MAX_DIFF_CHARS]
    if node.type != "tool":
        return node, ""
    resource_id = str(node.data.get("resource_id") or "")
    name = resource_id.split(":", 1)[1] if resource_id.startswith("tool:") else ""
    if name not in _MUTATION_TOOLS:
        return node, ""
    arguments = dict(node.data.get("arguments") or {})
    impact = preview_workspace_mutation(name, arguments)
    for key in ("expected_absent", "expected_sha256"):
        if key in impact:
            arguments[key] = impact[key]
    return node.model_copy(update={"data": {**node.data, "arguments": arguments}}), str(impact.get("diff", ""))[:MAX_DIFF_CHARS]


def _execute_runtime_node(node: GraphNode, value: str, values: list[str], workspace_root: Path, project_id: str | None, approved: set[str], chat_value: str = "", run_id: str = "", step_id: str = "") -> list[str]:
    if node.type == "split":
        return _split_value(value, node.data)
    if node.type == "merge":
        return [_merge_values(values, node.data)]
    if node.type == "context":
        selector = str(node.data.get("selector") or "").strip()
        if not selector:
            return [value]
        try:
            parsed = json.loads(value)
            selected: Any = parsed
            for part in selector.split("."):
                selected = selected[int(part)] if isinstance(selected, list) else selected[part]
            return [_bounded(json.dumps(selected, ensure_ascii=False) if not isinstance(selected, str) else selected)]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise NodeExecutionError("context selector did not match input", "context_selector_invalid") from exc
    if node.type == "plugin":
        plugin_id = str(node.data.get("plugin_id") or "run_annotation")
        try:
            result = execute_plugin(plugin_id, value, node.data)
            return [_bounded(result.get("output", ""))]
        except PluginError as exc:
            raise NodeExecutionError(exc.detail, exc.failure_class) from exc
    if node.type == "review":
        return [value]
    if node.type == "chat":
        return [_bounded(chat_value or value)]
    state = {"messages": [value] if value else [], "project_tasks": {}, "input_text": value, "last_output": value, "values": {}}
    context = ExecutionContext(workspace_root=workspace_root, events=[], project_id=project_id, approved_resources=approved, run_id=run_id, step_id=step_id)
    return [_bounded(_execute_node(node, state, context))]


def create_run(payload: RunPayload, workspace_root: Path, approved_resources: set[str] | None = None) -> dict[str, Any]:
    document = payload.graph
    validate_graph(document)
    run_id = str(uuid.uuid4())
    order = _topological_order(document)
    start_id = next(node.id for node in document.nodes if node.type == "start")
    state = {"order": order, "node_index": 0, "instance_index": 0, "contexts": {start_id: [{"value": payload.input_text, "branch_key": "root", "chunk_index": None, "source": "input"}]}, "grants": [], "approved_resources": sorted(approved_resources or set()), "chat_values": {}}
    with SessionLocal() as db:
        run = WorkflowRun(id=run_id, project_id=payload.project_id, status="queued", approval_policy=payload.approval_policy, graph_snapshot=document.model_dump(mode="json"), runtime_state=state, input_text=_bounded(payload.input_text), retain_context=payload.retain_context, max_parallel=payload.max_parallel)
        db.add(run)
        _emit(db, run_id, "run_created", {"run_id": run_id, "status": "queued", "approval_policy": payload.approval_policy})
        db.commit()
    resume_run(run_id, workspace_root)
    return get_run(run_id)


def resume_run(run_id: str, workspace_root: Path) -> None:
    with _workers_lock:
        if run_id in _workers:
            return
        _workers.add(run_id)

    def worker() -> None:
        try:
            _run_worker(run_id, workspace_root)
        finally:
            with _workers_lock:
                _workers.discard(run_id)

    threading.Thread(target=worker, name=f"durable-run-{run_id[:8]}", daemon=True).start()


def _run_worker(run_id: str, workspace_root: Path) -> None:
    with SessionLocal() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None or run.status in {"completed", "cancelled", "denied"}:
            return
        document = GraphDocument.model_validate(run.graph_snapshot)
        nodes = {node.id: node for node in document.nodes}
        outgoing = {node.id: [] for node in document.nodes}
        for edge in document.edges:
            outgoing[edge.source].append(edge)
        for edges in outgoing.values():
            edges.sort(key=lambda edge: (edge.priority, edge.id))
        state = dict(run.runtime_state or {})
        run.status = "running"
        _emit(db, run_id, "run_started", {"run_id": run_id, "status": "running"})
        db.commit()

        try:
            while int(state.get("node_index", 0)) < len(state["order"]):
                node_id = state["order"][int(state["node_index"])]
                node = nodes[node_id]
                contexts = list(state.get("contexts", {}).get(node_id, []))
                if node.type == "merge" and contexts:
                    contexts = [{"value": _merge_values([str(item.get("value", "")) for item in contexts], node.data), "values": [str(item.get("value", "")) for item in contexts], "branch_key": "merge", "chunk_index": None, "source": "multiple"}]
                if not contexts:
                    state["node_index"] = int(state["node_index"]) + 1
                    state["instance_index"] = 0
                    run.runtime_state = dict(state)
                    db.commit()
                    continue

                instance_index = int(state.get("instance_index", 0))
                while instance_index < len(contexts):
                    item = contexts[instance_index]
                    value = _bounded(item.get("value", ""))
                    edited_data = dict(state.get("edited_arguments", {}).get(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{node_id}:{instance_index}").hex, {}))
                    effective_node = node.model_copy(update={"data": edited_data}) if edited_data else node
                    normalized_node, impact = _normalized_node(effective_node, value)
                    step_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{node_id}:{instance_index}").hex
                    step = db.get(RunStep, step_id)
                    if step is None:
                        step = RunStep(id=step_id, run_id=run_id, node_id=node_id, node_type=node.type, branch_key=str(item.get("branch_key") or "root")[:240], chunk_index=item.get("chunk_index"), status="queued", input_context={"value": value, "source": item.get("source"), "values": item.get("values", [])}, arguments=dict(normalized_node.data))
                        db.add(step)
                        db.flush()
                    else:
                        step.arguments = dict(normalized_node.data)
                    action = _protected_action(normalized_node, run.approval_policy)
                    subject = _stable_hash({"run_id": run_id, "step_id": step_id, "action": action, "arguments": normalized_node.data, "input": value})
                    grants = set(state.get("grants", []))
                    identical_subject = _stable_hash({"action": action, "arguments": normalized_node.data})
                    identical_grants = set(state.get("identical_grants", []))
                    approved_resources = set(state.get("approved_resources", []))
                    if action and action not in approved_resources and subject not in grants and identical_subject not in identical_grants:
                        existing = db.scalar(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id, ApprovalRequest.step_id == step_id, ApprovalRequest.status == "pending"))
                        if existing is None:
                            existing = ApprovalRequest(id=uuid.uuid4().hex, run_id=run_id, step_id=step_id, action_type=action, subject_hash=subject, status="pending", arguments=dict(normalized_node.data), impact_preview=impact)
                            db.add(existing)
                        step.status = "waiting_input" if action == "chat_input" else "waiting_approval"
                        run.status = step.status
                        run.runtime_state = dict(state)
                        _emit(db, run_id, "approval_required" if action != "chat_input" else "chat_required", {"run_id": run_id, "approval_id": existing.id, "step_id": step_id, "node_id": node_id, "action_type": action, "arguments": existing.arguments, "impact_preview": impact})
                        db.commit()
                        return

                    started = time.perf_counter()
                    step.status = "running"
                    db.commit()
                    chat_value = str(state.get("chat_values", {}).get(subject, ""))
                    outputs = _execute_runtime_node(normalized_node, value, list(item.get("values") or [value]), workspace_root, run.project_id, approved_resources | {action or "", str(normalized_node.data.get("resource_id") or ""), f"file-write:{node.id}"}, chat_value, run_id, step_id)
                    step.output = _bounded(outputs[0] if len(outputs) == 1 else json.dumps(outputs, ensure_ascii=False))
                    context_receipt = {"context_sha256": _stable_hash(value), "context_chars": len(value), "context_source": str(item.get("source") or ""), "branch_key": step.branch_key}
                    delegate_monitors = _persist_delegate_children(db, run_id, step_id, step.output, context_receipt) if node.type == "delegate" else []
                    step.status = "completed"
                    step.duration_ms = round((time.perf_counter() - started) * 1000)
                    step.updated_at = utc_now()
                    output_preview = "[transcript retained in local run context]" if node.type == "buzz" else _bounded(step.output, 4000)
                    _emit(db, run_id, "node_completed", {"run_id": run_id, "step_id": step_id, "node_id": node_id, "node_type": node.type, "branch_key": step.branch_key, "chunk_index": step.chunk_index, "status": "completed", "duration_ms": step.duration_ms, "output_preview": output_preview})
                    provenance = _web_provenance(step.output)
                    if provenance:
                        _emit(db, run_id, "web_provenance", {"run_id": run_id, "step_id": step_id, "node_id": node_id, **provenance})

                    for edge in outgoing[node_id]:
                        for output_index, output in enumerate(outputs):
                            if not _condition_matches(edge.condition, output):
                                continue
                            contexts_map = dict(state.get("contexts", {}))
                            target_contexts = list(contexts_map.get(edge.target, []))
                            target_contexts.append({"value": output, "branch_key": f"{step.branch_key}/{edge.label or edge.target}", "chunk_index": output_index if len(outputs) > 1 else item.get("chunk_index"), "source": node_id})
                            contexts_map[edge.target] = target_contexts
                            state["contexts"] = contexts_map
                    run.final_output = step.output
                    instance_index += 1
                    state["instance_index"] = instance_index
                    run.runtime_state = dict(state)
                    db.commit()
                    for child_id, process in delegate_monitors:
                        threading.Thread(target=_monitor_delegate_child, args=(child_id, process), name=f"delegate-child-{child_id[-8:]}", daemon=True).start()

                state["node_index"] = int(state["node_index"]) + 1
                state["instance_index"] = 0
                run.runtime_state = dict(state)
                db.commit()

            run.status = "completed"
            run.updated_at = utc_now()
            _emit(db, run_id, "run_completed", {"run_id": run_id, "status": "completed", "output": run.final_output})
            db.commit()
        except Exception as exc:
            run.status = "error"
            run.error_detail = _bounded(str(getattr(exc, "detail", exc)), 4000)
            _emit(db, run_id, "run_error", {"run_id": run_id, "status": "error", "detail": run.error_detail, "failure_class": str(getattr(exc, "failure_class", type(exc).__name__.lower()))})
            db.commit()


def decide_run(run_id: str, approval_id: str, decision: str, *, arguments: dict[str, Any] | None = None, note: str = "", approve_identical: bool = False, workspace_root: Path) -> dict[str, Any]:
    should_resume = False
    with SessionLocal() as db:
        run = db.get(WorkflowRun, run_id)
        approval = db.get(ApprovalRequest, approval_id)
        if run is None or approval is None or approval.run_id != run_id:
            raise KeyError(approval_id)
        if approval.status != "pending":
            raise ValueError("approval request is no longer pending")
        state = dict(run.runtime_state or {})
        if decision == "edit":
            if arguments is None:
                raise ValueError("edited arguments are required")
            approval.arguments = arguments
            step = db.get(RunStep, approval.step_id)
            input_value = str((step.input_context or {}).get("value") or "") if step else ""
            approval.subject_hash = _stable_hash({"run_id": run_id, "step_id": approval.step_id, "action": approval.action_type, "arguments": arguments, "input": input_value})
            approval.note = _bounded(note, 4000)
            edited = dict(state.get("edited_arguments", {}))
            edited[approval.step_id] = arguments
            state["edited_arguments"] = edited
            run.runtime_state = state
            _emit(db, run_id, "approval_edited", {"run_id": run_id, "approval_id": approval.id, "arguments": arguments})
        elif decision in {"deny", "cancel"}:
            approval.status = "denied"
            approval.note = _bounded(note, 4000)
            approval.decided_at = utc_now()
            run.status = "cancelled" if decision == "cancel" else "denied"
            _emit(db, run_id, "run_cancelled" if decision == "cancel" else "approval_denied", {"run_id": run_id, "approval_id": approval.id, "note": approval.note})
        elif decision == "approve":
            approval.status = "approved"
            approval.note = _bounded(note, 4000)
            approval.approve_identical = approve_identical
            approval.decided_at = utc_now()
            grants = list(state.get("grants", []))
            grants.append(approval.subject_hash)
            state["grants"] = sorted(set(grants))
            if approve_identical:
                identical = list(state.get("identical_grants", []))
                identical.append(_stable_hash({"action": approval.action_type, "arguments": approval.arguments or {}}))
                state["identical_grants"] = sorted(set(identical))
            if approval.action_type == "chat_input":
                chat_values = dict(state.get("chat_values", {}))
                chat_values[approval.subject_hash] = str((arguments or {}).get("content") or note)
                state["chat_values"] = chat_values
            run.runtime_state = state
            run.status = "queued"
            _emit(db, run_id, "approval_granted", {"run_id": run_id, "approval_id": approval.id, "step_id": approval.step_id, "approve_identical": approve_identical})
            should_resume = True
        else:
            raise ValueError("unsupported decision")
        db.commit()
    if should_resume:
        resume_run(run_id, workspace_root)
    return get_run(run_id)


def cancel_run(run_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status == "completed":
            raise ValueError("completed run cannot be cancelled")
        run.status = "cancelled"
        _emit(db, run_id, "run_cancelled", {"run_id": run_id})
        db.commit()
    return get_run(run_id)


def reconcile_detached_children() -> int:
    """Fail closed for child monitors that cannot survive a backend restart."""
    with SessionLocal() as db:
        children = list(db.scalars(select(DelegateChild).where(DelegateChild.status.in_(["queued", "running"]))).all())
        for item in children:
            item.status = "detached"
            item.failure_class = "worker_monitor_detached_after_restart"
            item.updated_at = utc_now()
            _emit(db, item.parent_run_id, "delegate_child_detached", {"run_id": item.parent_run_id, "parent_step_id": item.parent_step_id, "child_id": item.subtask_id, "status": "detached", "failure_class": item.failure_class})
        db.commit()
        return len(children)


reconcile_detached_children()
