from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, TypedDict
from urllib.parse import urlsplit

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .agent_engine import DEFAULT_LFM_BASE_URL, DEFAULT_LFM_MODEL
from .database import SessionLocal, upsert_task
from .ollama_control import DEFAULT_OLLAMA_MODEL, preflight_ollama_model
from .runtime_control import preflight_runtime_profile
from .schema import GraphDocument, GraphNode
from .tools import WORKSPACE_TOOL_CATALOG, WORKSPACE_TOOLS


SUPPORTED_NODE_TYPES = {"start", "buzz", "planner", "coder", "file", "task", "agent", "tool", "runtime"}
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".webm"}
ALLOWED_BUZZ_MODEL_SIZES = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
MAX_FILE_CHARS = 200_000
DEFAULT_MINIMAX_MODEL = "MiniMax-M3"
DEFAULT_NANBEIGE_MODEL = "nanbeige4.2-3b-local"
DEFAULT_NANBEIGE_BASE_URL = "http://127.0.0.1:8080/v1"
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

    # The first slice is deliberately linear. It keeps execution order obvious while the
    # persisted edge format remains compatible with future branch/merge support.
    for source, targets in outgoing.items():
        if len(targets) > 1:
            errors.append(f"node {source} has multiple outputs; branching is not enabled in the MVP")

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


def _nanbeige_base_url() -> str:
    raw = os.getenv("NANBEIGE_BASE_URL", DEFAULT_NANBEIGE_BASE_URL).strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise NodeExecutionError("Nanbeige endpoint configuration is invalid", "nanbeige_endpoint_invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise NodeExecutionError(
            "Nanbeige endpoint must be an unauthenticated 127.0.0.1 HTTP /v1 URL",
            "nanbeige_endpoint_invalid",
        )
    return f"http://127.0.0.1:{port}/v1/"


def _bounded_nanbeige_tokens(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 4096
    return min(max(parsed, 64), 8192)


def _lfm_base_url() -> str:
    raw = os.getenv("LFM_BASE_URL", DEFAULT_LFM_BASE_URL).strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise NodeExecutionError("LFM endpoint configuration is invalid", "lfm_endpoint_invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise NodeExecutionError(
            "LFM endpoint must be an unauthenticated 127.0.0.1 HTTP /v1 URL",
            "lfm_endpoint_invalid",
        )
    return f"http://127.0.0.1:{port}/v1/"


def _bounded_lfm_tokens(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 4096
    return min(max(parsed, 64), 8192)


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


def _nanbeige_output(prompt: str, data: dict[str, Any]) -> str:
    try:
        import httpx
    except ImportError as exc:
        raise NodeExecutionError("Nanbeige integration dependencies are not installed", "nanbeige_dependency_missing") from exc

    configured_model = os.getenv("NANBEIGE_MODEL", DEFAULT_NANBEIGE_MODEL).strip()
    requested_model = str(data.get("model") or configured_model).strip()
    if configured_model != DEFAULT_NANBEIGE_MODEL or requested_model != DEFAULT_NANBEIGE_MODEL:
        raise NodeExecutionError(
            "Nanbeige model must match the approved local workspace alias",
            "nanbeige_model_policy_rejected",
        )
    base_url = _nanbeige_base_url()
    try:
        temperature = min(max(float(data.get("temperature", 0.6)), 0.0), 2.0)
    except (TypeError, ValueError):
        temperature = 0.6
    payload = {
        "model": DEFAULT_NANBEIGE_MODEL,
        "messages": [
            {
                "role": "system",
                "content": str(
                    data.get("system_prompt")
                    or "You are a precise local coding assistant. Return the most useful direct result for the workflow."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 20,
        "max_tokens": _bounded_nanbeige_tokens(data.get("max_tokens", 4096)),
        "stream": False,
        "chat_template_kwargs": {
            "enable_thinking": data.get("enable_thinking", True) is not False,
            "preserve_thinking": False,
        },
    }
    try:
        with httpx.Client(base_url=base_url, timeout=_model_timeout_seconds(), trust_env=False) as client:
            models_response = client.get("models")
            models_response.raise_for_status()
            models_payload = models_response.json()
            if not isinstance(models_payload, dict):
                raise NodeExecutionError(
                    "The local Nanbeige model inventory was invalid",
                    "nanbeige_invalid_response",
                )
            model_ids = {
                item.get("id")
                for item in models_payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            if DEFAULT_NANBEIGE_MODEL not in model_ids:
                raise NodeExecutionError(
                    "The approved Nanbeige workspace model is not exposed by the local endpoint",
                    "nanbeige_model_mismatch",
                )
            response = client.post("chat/completions", json=payload)
            response.raise_for_status()
            response_payload = response.json()
            content = response_payload["choices"][0]["message"]["content"]
    except NodeExecutionError:
        raise
    except httpx.TimeoutException as exc:
        raise NodeExecutionError("Nanbeige generation timed out", "nanbeige_timeout") from exc
    except httpx.ConnectError as exc:
        raise NodeExecutionError("The local Nanbeige workspace server is unavailable", "nanbeige_unavailable") from exc
    except httpx.HTTPStatusError as exc:
        raise NodeExecutionError("The local Nanbeige workspace server rejected the request", "nanbeige_failed") from exc
    except httpx.RequestError as exc:
        raise NodeExecutionError("The local Nanbeige workspace request failed", "nanbeige_unavailable") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise NodeExecutionError("The local Nanbeige workspace response was invalid", "nanbeige_invalid_response") from exc
    if not isinstance(content, str) or not content.strip():
        raise NodeExecutionError("The local Nanbeige workspace response was empty", "nanbeige_empty_response")
    return content[:MAX_FILE_CHARS]


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


def _lfm_output(prompt: str, data: dict[str, Any]) -> str:
    try:
        import httpx
    except ImportError as exc:
        raise NodeExecutionError("LFM integration dependencies are not installed", "lfm_dependency_missing") from exc

    configured_model = os.getenv("LFM_MODEL", DEFAULT_LFM_MODEL).strip()
    requested_model = str(data.get("model") or configured_model).strip()
    if configured_model != DEFAULT_LFM_MODEL or requested_model != DEFAULT_LFM_MODEL:
        raise NodeExecutionError(
            "LFM model must match the approved LiquidAI model identity",
            "lfm_model_policy_rejected",
        )
    base_url = _lfm_base_url()
    try:
        temperature = min(max(float(data.get("temperature", 0.1)), 0.0), 2.0)
    except (TypeError, ValueError):
        temperature = 0.1
    payload = {
        "model": DEFAULT_LFM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": str(
                    data.get("system_prompt")
                    or "You are a precise local agentic assistant. Return the most useful direct result."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "top_k": 50,
        "repetition_penalty": 1.1,
        "max_tokens": _bounded_lfm_tokens(data.get("max_tokens", 4096)),
        "stream": False,
    }
    try:
        with httpx.Client(base_url=base_url, timeout=_model_timeout_seconds(), trust_env=False) as client:
            models_response = client.get("models")
            models_response.raise_for_status()
            models_payload = models_response.json()
            model_ids = {
                item.get("id")
                for item in models_payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            if DEFAULT_LFM_MODEL not in model_ids:
                raise NodeExecutionError(
                    "The approved LFM model is not exposed by the configured local endpoint",
                    "lfm_model_mismatch",
                )
            response = client.post("chat/completions", json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    except NodeExecutionError:
        raise
    except httpx.TimeoutException as exc:
        raise NodeExecutionError("LFM generation timed out", "lfm_timeout") from exc
    except httpx.ConnectError as exc:
        raise NodeExecutionError("The local LFM server is unavailable", "lfm_unavailable") from exc
    except httpx.HTTPStatusError as exc:
        raise NodeExecutionError("The local LFM server rejected the request", "lfm_failed") from exc
    except httpx.RequestError as exc:
        raise NodeExecutionError("The local LFM request failed", "lfm_unavailable") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise NodeExecutionError("The local LFM response was invalid", "lfm_invalid_response") from exc
    if not isinstance(content, str) or not content.strip():
        raise NodeExecutionError("The local LFM response was empty", "lfm_empty_response")
    return content[:MAX_FILE_CHARS]


def _ollama_output(prompt: str, data: dict[str, Any]) -> str:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise NodeExecutionError("Ollama integration dependencies are not installed", "ollama_dependency_missing") from exc

    requested_model = str(data.get("model") or os.getenv("OLLAMA_MODEL", "")).strip()
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
    provider = str(data.get("provider") or os.getenv("WORKSPACE_MODEL_PROVIDER", "ollama")).strip().lower()
    if provider == "nanbeige":
        return _nanbeige_output(prompt, data)
    if provider == "lfm":
        return _lfm_output(prompt, data)
    if provider in {"minimax", "minimax-oauth"}:
        return _minimax_output(prompt, data)
    if provider == "ollama":
        return _ollama_output(prompt, data)
    raise NodeExecutionError("unsupported coder model provider", "model_provider_invalid")


def _planner_output(prompt: str, data: dict[str, Any]) -> str:
    planner_data = {
        **data,
        "provider": "nanbeige",
        "model": DEFAULT_NANBEIGE_MODEL,
        "system_prompt": str(data.get("system_prompt") or DEFAULT_PLANNER_PROMPT),
        "enable_thinking": False,
        "max_tokens": min(int(data.get("max_tokens", 4096)), 4096),
    }
    return _nanbeige_output(prompt, planner_data)


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


def trigger_agent(target: str, prompt: str, root: Path) -> int:
    commands = _configured_agent_commands()
    command = commands.get(target)
    if not command:
        raise NodeExecutionError("the selected local agent is not configured", "agent_unavailable")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.stdin is not None:
            process.stdin.write(prompt[:MAX_FILE_CHARS])
            process.stdin.close()
        return int(process.pid)
    except (OSError, ValueError) as exc:
        raise NodeExecutionError("the configured local agent could not be started", "agent_start_failed") from exc


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


def _tool_node(node: GraphNode, context: ExecutionContext) -> str:
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
    arguments = node.data.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise NodeExecutionError("tool arguments must be an object", "tool_arguments_invalid")
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
        file_path = str(data.get("file_path") or state.get("input_text", ""))
        return transcribe_audio(file_path, str(data.get("model_size") or "small"), context.workspace_root)
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
    if node.type == "tool":
        return _tool_node(node, context)
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
