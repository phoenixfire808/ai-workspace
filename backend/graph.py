from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, TypedDict


from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .database import SessionLocal, upsert_task
from .delegation import DelegationError, plan_or_dispatch
from .hermes_adapter import dispatch_hermes_skill
from .ollama_control import DEFAULT_OLLAMA_MODEL, preflight_ollama_model
from .model_settings import resolve_workspace_model
from .runtime_control import preflight_runtime_profile
from .model_profiles import generate_with_endpoint
from .schema import GraphDocument, GraphNode
from .tools import WORKSPACE_TOOL_CATALOG, WORKSPACE_TOOLS


SUPPORTED_NODE_TYPES = {"start", "buzz", "tts", "planner", "coder", "file", "task", "agent", "tool", "runtime", "review", "chat", "split", "merge", "context", "plugin", "delegate", "search", "research", "source_context"}
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".webm"}
ALLOWED_BUZZ_MODEL_SIZES = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
MAX_FILE_CHARS = 200_000
_AGENT_PROCESSES: dict[int, subprocess.Popen[str]] = {}
_AGENT_PROCESSES_LOCK = threading.Lock()
DEFAULT_MINIMAX_MODEL = "MiniMax-M3"

DEFAULT_PLANNER_PROMPT = (
    "You are the local workflow planner. Convert the supplied user intent into a concise, "
    "structured implementation plan with goal, assumptions, ordered steps, files or tools "
    "involved, risks, and a verification checklist. Do not execute actions or invent results."
)


class AgentState(TypedDict):
    messages: list[str]
    project_tasks: dict[str, str]
    input_text: str
    last_output: str
    values: dict[str, Any]


class GraphValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class NodeExecutionError(RuntimeError):
    def __init__(self, detail: str, failure_class: str):
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


@dataclass
class ExecutionContext:
    workspace_root: Path
    events: list[dict[str, Any]]
    project_id: str | None = None
    approved_resources: set[str] = field(default_factory=set)
    run_id: str = ""
    step_id: str = ""


def _node_dict(node: GraphNode) -> dict[str, Any]:
    return node.model_dump(mode="python")


def validate_graph(graph: GraphDocument | dict[str, Any]) -> dict[str, Any]:
    document = graph if isinstance(graph, GraphDocument) else GraphDocument.model_validate(graph)
    errors: list[str] = []
    nodes = document.nodes
    ids = [node.id for node in nodes]
    id_set = set(ids)

    if len(ids) != len(id_set):
        errors.append("node ids must be unique")
    starts = [node for node in nodes if node.type == "start"]
    if len(starts) != 1:
        errors.append("the graph must contain exactly one Start node")

    for node in nodes:
        if node.type not in SUPPORTED_NODE_TYPES:
            errors.append(f"unsupported node type: {node.type}")

    outgoing: dict[str, list[str]] = {node_id: [] for node_id in id_set}
    incoming: dict[str, list[str]] = {node_id: [] for node_id in id_set}
    for edge in document.edges:
        if edge.source not in id_set or edge.target not in id_set:
            errors.append(f"edge {edge.id} references a missing node")
            continue
        if edge.source == edge.target:
            errors.append(f"edge {edge.id} cannot connect a node to itself")
        outgoing[edge.source].append(edge.target)
        incoming[edge.target].append(edge.source)

    if not errors:
        indegree = {node_id: len(incoming[node_id]) for node_id in id_set}
        queue = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for target in outgoing[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if visited != len(id_set):
            errors.append("the graph contains a cycle")

    if starts and not errors:
        reachable: set[str] = set()
        queue = [starts[0].id]
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(outgoing[current])
        unreachable = sorted(id_set - reachable)
        if unreachable:
            errors.append(f"unreachable nodes: {', '.join(unreachable)}")

    if errors:
        raise GraphValidationError(errors)

    return {
        "valid": True,
        "node_count": len(nodes),
        "edge_count": len(document.edges),
        "start_node": starts[0].id,
    }


def _safe_path(root: Path, configured: str, *, require_existing: bool = False) -> Path:
    if not configured.strip():
        raise NodeExecutionError("a local path is required", "path_missing")
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise NodeExecutionError("path is outside the configured workspace root", "path_denied") from exc
    if require_existing and not resolved.is_file():
        raise NodeExecutionError("local file was not found", "file_missing")
    return resolved


def _current_input(state: AgentState) -> str:
    return state.get("last_output") or state.get("input_text") or ""


def _buzz_command() -> str:
    return os.getenv("BUZZ_EXECUTABLE", "buzz")


def _model_timeout_seconds() -> float:
    try:
        configured = float(os.getenv("WORKSPACE_MODEL_TIMEOUT_SECONDS", "120"))
    except ValueError:
        configured = 120.0
    return min(max(configured, 1.0), 600.0)



def _enforce_model_policy(model: str) -> str:
    if re.search(r"qwen[\s/_-]*2\.5", model, flags=re.IGNORECASE):
        raise NodeExecutionError("Qwen 2.5 models are not permitted in this workspace", "model_policy_rejected")
    return model


def transcribe_audio(file_path: str, model_size: str, root: Path) -> str:
    safe_file = _safe_path(root, file_path, require_existing=True)
    if safe_file.suffix.lower() not in ALLOWED_AUDIO_SUFFIXES:
        raise NodeExecutionError("unsupported audio file type", "audio_type_denied")
    model_size = (model_size or "small").strip().lower()
    if model_size not in ALLOWED_BUZZ_MODEL_SIZES:
        raise NodeExecutionError("unsupported Buzz model size", "buzz_model_size_invalid")
    output_path = safe_file.with_suffix(".txt")
    command = [
        _buzz_command(),
        "add",
        "--task",
        "transcribe",
        "--model-type",
        "whispercpp",
        "--model-size",
        model_size,
        "--txt",
        str(safe_file),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        raise NodeExecutionError("Buzz CLI is not configured or not on PATH", "buzz_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise NodeExecutionError("Buzz transcription timed out", "buzz_timeout") from exc
    if completed.returncode != 0:
        raise NodeExecutionError("Buzz transcription failed", "buzz_failed")
    if not output_path.is_file():
        raise NodeExecutionError("Buzz completed without producing a transcript file", "buzz_output_missing")
    try:
        return output_path.read_text(encoding="utf-8")[:MAX_FILE_CHARS]
    except OSError as exc:
        raise NodeExecutionError("the transcript output could not be read", "buzz_output_unreadable") from exc



def _minimax_output(prompt: str, data: dict[str, Any]) -> str:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise NodeExecutionError("MiniMax integration dependencies are not installed", "minimax_dependency_missing") from exc

    model = _enforce_model_policy(str(data.get("model") or os.getenv("MINIMAX_MODEL", DEFAULT_MINIMAX_MODEL)))
    base_url = os.getenv("MINIMAX_BASE_URL", "").strip()
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not base_url or not api_key:
        raise NodeExecutionError(
            "MiniMax is selected but MINIMAX_BASE_URL and MINIMAX_API_KEY are not configured",
            "minimax_not_configured",
        )
    system_prompt = str(
        data.get("system_prompt")
        or "You are a precise coding assistant. Return the most useful direct result for the workflow."
    )
    try:
        llm = ChatOpenAI(
            model=model,
            temperature=float(data.get("temperature", 0.1)),
            base_url=base_url,
            api_key=api_key,
            timeout=_model_timeout_seconds(),
            max_retries=1,
        )
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
    except Exception as exc:
        raise NodeExecutionError("MiniMax generation failed; check the configured endpoint", "minimax_failed") from exc
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content[:MAX_FILE_CHARS]


def _ollama_output(prompt: str, data: dict[str, Any]) -> str:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise NodeExecutionError("Ollama integration dependencies are not installed", "ollama_dependency_missing") from exc

    try:
        selection = resolve_workspace_model(
            node_provider=str(data.get("provider") or "") or None,
            node_model=str(data.get("model") or "") or None,
        )
    except ValueError as exc:
        failure = str(exc)
        raise NodeExecutionError("workspace model selection is not executable", failure) from exc
    requested_model = selection["model"]
    preflight = preflight_ollama_model(requested_model)
    model = _enforce_model_policy(str(preflight.get("model") or DEFAULT_OLLAMA_MODEL))
    if preflight.get("status") != "ready" or not preflight.get("exact_model"):
        failure_class = str(preflight.get("failure_class") or "ollama_model_mismatch")
        raise NodeExecutionError(
            f"Ollama model preflight failed for the exact local model: {preflight.get('status', 'unknown')}",
            failure_class,
        )
    base_url = str(preflight["base_url"])
    system_prompt = str(
        data.get("system_prompt")
        or "You are a precise local coding assistant. Return the most useful direct result for the workflow."
    )
    try:
        llm = ChatOllama(
            model=model,
            temperature=float(data.get("temperature", 0.1)),
            base_url=base_url,
            client_kwargs={"timeout": _model_timeout_seconds()},
        )
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
    except Exception as exc:  # Provider errors are mapped to a bounded public failure class.
        raise NodeExecutionError("Ollama generation failed; check the local server and model", "ollama_failed") from exc
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content[:MAX_FILE_CHARS]


def _model_output(prompt: str, data: dict[str, Any]) -> str:
    endpoint_profile = str(data.get("endpoint_profile") or "").strip()
    if endpoint_profile:
        try:
            return generate_with_endpoint(endpoint_profile, model=str(data.get("model") or ""), prompt=prompt, system_prompt=str(data.get("system_prompt") or ""), settings=data)
        except KeyError as exc:
            raise NodeExecutionError("the selected endpoint profile is not registered", "endpoint_profile_unknown") from exc
        except (RuntimeError, ValueError) as exc:
            raise NodeExecutionError("the selected endpoint could not generate a response", "endpoint_generation_failed") from exc
    provider = str(data.get("provider") or os.getenv("WORKSPACE_MODEL_PROVIDER", "ollama")).strip().lower()
    if provider == "nanbeige":
        raise NodeExecutionError("Nanbeige has been retired from M⊕", "nanbeige_retired_from_workspace")
    if provider == "lfm":
        legacy_data = {**data, "provider": "ollama"}
        if str(legacy_data.get("model") or "") == "LFM2.5-2.6B":
            legacy_data["model"] = ""
        return _ollama_output(prompt, legacy_data)
    if provider in {"minimax", "minimax-oauth"}:
        return _minimax_output(prompt, data)
    if provider == "ollama":
        return _ollama_output(prompt, data)
    if provider == "openrouter":
        try:
            return generate_with_endpoint("openrouter", model=str(data.get("model") or ""), prompt=prompt, system_prompt=str(data.get("system_prompt") or ""), settings=data)
        except KeyError as exc:
            raise NodeExecutionError("the OpenRouter endpoint profile is not registered", "openrouter_profile_unknown") from exc
        except (RuntimeError, ValueError) as exc:
            raise NodeExecutionError("OpenRouter is not ready or rejected the request", "openrouter_not_ready") from exc
    raise NodeExecutionError("unsupported coder model provider", "model_provider_invalid")


def _planner_output(prompt: str, data: dict[str, Any]) -> str:
    planner_data = {
        **data,
        "provider": str(data.get("provider") or "ollama"),
        "model": str(data.get("model") or ""),
        "system_prompt": str(data.get("system_prompt") or DEFAULT_PLANNER_PROMPT),
        "enable_thinking": False,
        "max_tokens": min(int(data.get("max_tokens", 4096)), 4096),
    }
    return _model_output(prompt, planner_data)


def _configured_agent_commands() -> dict[str, list[str]]:
    raw = os.getenv("WORKSPACE_AGENT_COMMANDS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    commands: dict[str, list[str]] = {}
    for target, command in parsed.items():
        if isinstance(target, str) and isinstance(command, list) and command and all(isinstance(part, str) for part in command):
            commands[target] = command
    return commands


def configured_agents() -> list[str]:
    return sorted(_configured_agent_commands())


def take_agent_process(process_id: int) -> subprocess.Popen[str] | None:
    with _AGENT_PROCESSES_LOCK:
        return _AGENT_PROCESSES.pop(process_id, None)


def trigger_agent(target: str, prompt: str, root: Path) -> dict[str, Any]:
    commands = _configured_agent_commands()
    command = commands.get(target)
    if not command:
        raise NodeExecutionError("the selected local agent is not configured", "agent_unavailable")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.stdin is not None:
            process.stdin.write(prompt[:MAX_FILE_CHARS])
            process.stdin.close()
            process.stdin = None
        with _AGENT_PROCESSES_LOCK:
            _AGENT_PROCESSES[int(process.pid)] = process
        return {"pid": int(process.pid), "capture": "bounded_stdout", "status": "started"}
    except (OSError, ValueError) as exc:
        raise NodeExecutionError("the configured local agent could not be started", "agent_start_failed") from exc


def _delegate_node(node: GraphNode, state: AgentState, context: ExecutionContext) -> str:
    data = node.data
    mode = str(data.get("dispatch_mode") or "plan_only").strip().lower()
    if mode != "plan_only" and not ({f"delegate:{node.id}", "step_review"} & context.approved_resources):
        raise NodeExecutionError("worker dispatch requires approval review", "approval_required")
    try:
        result = plan_or_dispatch(
            _current_input(state),
            strategy=str(data.get("decompose_strategy") or "checklist"),
            explicit=data.get("subtasks"),
            max_subtasks=int(data.get("max_subtasks", 8)),
            worker_target=str(data.get("worker_target") or data.get("target") or ""),
            mode=mode,
            context=f"PARENT_RUN_ID: {context.run_id or 'legacy'}\nPARENT_STEP_ID: {context.step_id or node.id}\n\n{_current_input(state)}",
            max_parallel=int(data.get("max_parallel", 4)),
            dispatch_agent=lambda target, prompt: trigger_agent(target, prompt, context.workspace_root),
            dispatch_hermes=lambda skill, prompt: dispatch_hermes_skill.invoke({"skill_name": skill, "prompt": prompt}),
        )
    except DelegationError as exc:
        raise NodeExecutionError(exc.detail, exc.failure_class) from exc
    return json.dumps(result, ensure_ascii=False)[:MAX_FILE_CHARS]


def _task_node(node: GraphNode, state: AgentState, context: ExecutionContext) -> str:
    data = node.data
    title = str(data.get("title") or _current_input(state)[:240] or "Untitled task")[:240]
    status = str(data.get("status") or "todo")
    if status not in {"todo", "in_progress", "done", "blocked"}:
        raise NodeExecutionError("task status is invalid", "task_status_invalid")
    task_id = str(data.get("task_id") or uuid.uuid4())
    notes = str(data.get("notes") or "")[:MAX_FILE_CHARS]
    with SessionLocal() as db:
        upsert_task(
            db,
            task_id=task_id,
            project_id=context.project_id,
            title=title,
            status=status,
            notes=notes,
        )
    return f"Task updated: {title} ({status})"


def _tool_node(node: GraphNode, state: AgentState, context: ExecutionContext) -> str:
    resource_id = str(node.data.get("resource_id") or "")
    if not resource_id.startswith("tool:"):
        raise NodeExecutionError("a governed tool resource is required", "tool_resource_invalid")
    name = resource_id.split(":", 1)[1]
    catalog = {str(item["name"]): item for item in WORKSPACE_TOOL_CATALOG}
    item = catalog.get(name)
    tools = {str(tool.name): tool for tool in WORKSPACE_TOOLS}
    tool = tools.get(name)
    if item is None or tool is None:
        raise NodeExecutionError("the selected tool is not allowlisted", "tool_not_allowlisted")
    if item.get("requires_approval") and resource_id not in context.approved_resources:
        raise NodeExecutionError("the selected tool requires approval review", "approval_required")
    raw_arguments = node.data.get("arguments") or {}
    if not isinstance(raw_arguments, dict):
        raise NodeExecutionError("tool arguments must be an object", "tool_arguments_invalid")
    arguments = dict(raw_arguments)
    if name in {"search_web", "deep_research"} and not str(arguments.get("query") or "").strip():
        arguments["query"] = _current_input(state)
    if name == "build_research_context" and not arguments.get("sources") and not str(arguments.get("context_text") or "").strip():
        arguments["context_text"] = _current_input(state)
    try:
        return str(tool.invoke(arguments))[:MAX_FILE_CHARS]
    except Exception as exc:
        raise NodeExecutionError("the governed tool failed", "tool_failed") from exc


def _runtime_node(node: GraphNode) -> str:
    profile_id = str(node.data.get("profile_id") or "")
    if not profile_id:
        raise NodeExecutionError("a runtime profile is required", "runtime_profile_missing")
    try:
        result = preflight_runtime_profile(profile_id)
    except KeyError as exc:
        raise NodeExecutionError("the runtime profile is not registered", "runtime_profile_unknown") from exc
    return json.dumps(result, ensure_ascii=False)[:MAX_FILE_CHARS]


def _execute_node(node: GraphNode, state: AgentState, context: ExecutionContext) -> str:
    data = node.data
    if node.type == "start":
        return state.get("input_text", "")
    if node.type == "buzz":
        if str(data.get("input_mode") or "") == "captured_transcript" and str(data.get("transcript") or "").strip():
            return str(data.get("transcript"))[:MAX_FILE_CHARS]
        file_path = str(data.get("file_path") or state.get("input_text", ""))
        return transcribe_audio(file_path, str(data.get("model_size") or "small"), context.workspace_root)
    if node.type == "tts":
        return str(data.get("text") or _current_input(state))[:MAX_FILE_CHARS]
    if node.type == "planner":
        return _planner_output(_current_input(state), data)
    if node.type == "coder":
        return _model_output(_current_input(state), data)
    if node.type == "file":
        mode = str(data.get("mode") or "read")
        safe_file = _safe_path(
            context.workspace_root,
            str(data.get("path") or ""),
            require_existing=mode == "read",
        )
        if mode == "read":
            try:
                return safe_file.read_text(encoding="utf-8")[:MAX_FILE_CHARS]
            except OSError as exc:
                raise NodeExecutionError("local file could not be read", "file_read_failed") from exc
        if mode == "write":
            approval_id = f"file-write:{node.id}"
            if approval_id not in context.approved_resources:
                raise NodeExecutionError("workspace file writes require approval review", "approval_required")
            safe_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                safe_file.write_text(_current_input(state)[:MAX_FILE_CHARS], encoding="utf-8")
            except OSError as exc:
                raise NodeExecutionError("local file could not be written", "file_write_failed") from exc
            return f"Wrote workflow output to {safe_file.relative_to(context.workspace_root)}"
        raise NodeExecutionError("file mode must be read or write", "file_mode_invalid")
    if node.type == "task":
        return _task_node(node, state, context)
    if node.type == "agent":
        target = str(data.get("target") or "")
        if f"agent:{target}" not in context.approved_resources:
            raise NodeExecutionError("local agent dispatch requires approval review", "approval_required")
        prefix = str(data.get("prompt_prefix") or "").strip()
        prompt = _current_input(state)
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"
        pid = trigger_agent(target, prompt, context.workspace_root)
        return f"Started local agent '{target}' (pid {pid})"
    if node.type == "delegate":
        return _delegate_node(node, state, context)
    if node.type == "tool":
        return _tool_node(node, state, context)
    if node.type == "runtime":
        return _runtime_node(node)
    raise NodeExecutionError("node type is not executable", "node_type_invalid")


def compile_graph_from_json(
    graph_json: GraphDocument | dict[str, Any],
    context: ExecutionContext | None = None,
) -> CompiledStateGraph:
    document = graph_json if isinstance(graph_json, GraphDocument) else GraphDocument.model_validate(graph_json)
    validate_graph(document)
    default_root = Path(os.getenv("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[1]))).expanduser().resolve()
    context = context or ExecutionContext(workspace_root=default_root, events=[])
    outgoing = {node.id: [] for node in document.nodes}
    for edge in document.edges:
        outgoing[edge.source].append(edge.target)

    builder = StateGraph(AgentState)
    for node in document.nodes:
        if node.type in {"planner", "coder"}:
            merged_data = dict(node.data)
            if not merged_data.get("provider") and document.settings.get("model_provider"):
                merged_data["provider"] = document.settings["model_provider"]
            if not merged_data.get("model") and document.settings.get("model"):
                merged_data["model"] = document.settings["model"]
            node = node.model_copy(update={"data": merged_data})
        def make_executor(current_node: GraphNode) -> Callable[[AgentState], dict[str, Any]]:
            def executor(state: AgentState) -> dict[str, Any]:
                started = time.perf_counter()
                try:
                    output = _execute_node(current_node, state, context)
                except NodeExecutionError as exc:
                    context.events.append(
                        {
                            "node_id": current_node.id,
                            "node_type": current_node.type,
                            "status": "error",
                            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                            "failure_class": exc.failure_class,
                        }
                    )
                    raise
                except Exception as exc:
                    context.events.append(
                        {
                            "node_id": current_node.id,
                            "node_type": current_node.type,
                            "status": "error",
                            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                            "failure_class": type(exc).__name__.lower(),
                        }
                    )
                    raise NodeExecutionError("workflow node failed", "node_failed") from exc
                context.events.append(
                    {
                        "node_id": current_node.id,
                        "node_type": current_node.type,
                        "status": "completed",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
                project_tasks = dict(state.get("project_tasks", {}))
                if current_node.type == "task":
                    project_tasks[current_node.id] = str(current_node.data.get("status") or "todo")
                return {
                    "messages": [*state.get("messages", []), output],
                    "project_tasks": project_tasks,
                    "last_output": output,
                    "values": {**state.get("values", {}), current_node.id: output},
                }

            return executor

        builder.add_node(node.id, make_executor(node))

    start_id = next(node.id for node in document.nodes if node.type == "start")
    builder.add_edge(START, start_id)
    for edge in document.edges:
        builder.add_edge(edge.source, edge.target)
    for node in document.nodes:
        if not outgoing[node.id]:
            builder.add_edge(node.id, END)
    return builder.compile()


def stream_graph(
    graph_json: GraphDocument | dict[str, Any],
    *,
    input_text: str,
    workspace_root: Path,
    project_id: str | None = None,
    events: list[dict[str, Any]] | None = None,
    result: dict[str, Any] | None = None,
    approved_resources: set[str] | None = None,
) -> Iterator[dict[str, Any]]:
    event_log = events if events is not None else []
    result_holder = result if result is not None else {}
    context = ExecutionContext(
        workspace_root=workspace_root,
        events=event_log,
        project_id=project_id,
        approved_resources=set(approved_resources or set()),
    )
    graph = compile_graph_from_json(graph_json, context)
    state: AgentState = {
        "messages": [input_text] if input_text else [],
        "project_tasks": {},
        "input_text": input_text,
        "last_output": input_text,
        "values": {},
    }
    for update in graph.stream(state, stream_mode="updates"):
        for node_update in update.values():
            if isinstance(node_update, dict):
                if "last_output" in node_update:
                    state["last_output"] = str(node_update["last_output"])
                    result_holder["last_output"] = state["last_output"]
                if "messages" in node_update and isinstance(node_update["messages"], list):
                    state["messages"] = [str(message) for message in node_update["messages"]]
                if "project_tasks" in node_update and isinstance(node_update["project_tasks"], dict):
                    state["project_tasks"] = {
                        str(task_id): str(status) for task_id, status in node_update["project_tasks"].items()
                    }
                if "values" in node_update and isinstance(node_update["values"], dict):
                    state["values"] = dict(node_update["values"])
        yield update


def run_graph(
    graph_json: GraphDocument | dict[str, Any],
    *,
    input_text: str,
    workspace_root: Path,
    project_id: str | None = None,
    events: list[dict[str, Any]] | None = None,
    approved_resources: set[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    event_log = events if events is not None else []
    result: dict[str, Any] = {}
    for _update in stream_graph(
        graph_json,
        input_text=input_text,
        workspace_root=workspace_root,
        project_id=project_id,
        events=event_log,
        result=result,
        approved_resources=approved_resources,
    ):
        pass
    return str(result.get("last_output", input_text)), event_log
