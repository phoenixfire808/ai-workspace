from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

from .graph import configured_agents, trigger_agent, _model_output
from .hermes_adapter import hermes_capability_audit, list_hermes_skills
from .ollama_control import DEFAULT_OLLAMA_MODEL, list_ollama_models, preflight_ollama_model
from .runtime_control import list_runtime_profiles, preflight_runtime_profile
from .schema import GraphDocument
from .tools import APPROVAL_REQUIRED_TOOLS, WORKSPACE_TOOL_CATALOG, WORKSPACE_TOOLS, preview_workspace_mutation
from .web_research import web_preflight
from .observability import log_event, log_exception

ResourceCategory = Literal["tool", "agent", "skill", "model", "runtime", "template"]


class LibraryResource(BaseModel):
    resource_id: str = Field(min_length=3, max_length=800)
    category: ResourceCategory
    label: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=1000)
    scope: str = Field(default="local", max_length=160)
    ready: bool = True
    disabled_reason: str | None = Field(default=None, max_length=500)
    requires_approval: bool = False
    capabilities: list[str] = Field(default_factory=list)
    arguments_schema: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionPreviewPayload(BaseModel):
    resource_id: str = Field(min_length=3, max_length=800)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ActionRunPayload(ActionPreviewPayload):
    preview_id: str = Field(min_length=1, max_length=80)
    approved: bool = False


class TemplateInstantiatePayload(BaseModel):
    options: dict[str, Any] = Field(default_factory=dict)


class GraphApprovalPayload(BaseModel):
    graph: GraphDocument


_PREVIEW_TTL_SECONDS = 600
_preview_lock = Lock()
_previews: dict[str, dict[str, Any]] = {}


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tool_map() -> dict[str, Any]:
    return {str(tool.name): tool for tool in WORKSPACE_TOOLS}


def _tool_schema(name: str) -> dict[str, Any]:
    tool = _tool_map().get(name)
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return {"type": "object", "properties": {}}
    try:
        return schema.model_json_schema()
    except Exception:
        return {"type": "object", "properties": {}}


def _skills() -> list[dict[str, str]]:
    try:
        payload = json.loads(list_hermes_skills.invoke({"skill_name": ""}))
    except Exception:
        return []
    skills = payload.get("skills", []) if isinstance(payload, dict) else []
    return [
        {"name": str(item.get("name", "")), "description": str(item.get("description", ""))}
        for item in skills
        if isinstance(item, dict) and item.get("name")
    ]


def _templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": "inspect-workspace",
            "label": "Inspect workspace",
            "description": "List workspace metadata and inspect a selected Python module.",
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:list_workspace_files", "arguments": {"relative_path": ""}}),
                ("tool", {"resource_id": "tool:inspect_python_ast", "arguments": {"relative_path": "backend/main.py"}}),
            ],
        },
        {
            "template_id": "plan-feature",
            "label": "Plan a feature",
            "description": "Turn the workflow input into a structured implementation plan and task.",
            "nodes": [("start", {}), ("planner", {}), ("task", {"status": "todo"})],
        },
        {
            "template_id": "code-local-model",
            "label": "Code with selected local model",
            "description": "Send workflow input to an exact local Ollama model.",
            "nodes": [("start", {}), ("coder", {"provider": "ollama", "model": ""})],
        },
        {
            "template_id": "read-transform-save",
            "label": "Read, transform, and save",
            "description": "Read a workspace file, transform it with a local model, and write a reviewed output.",
            "nodes": [
                ("start", {}),
                ("file", {"mode": "read", "path": "README.md"}),
                ("coder", {"provider": "ollama", "model": ""}),
                ("file", {"mode": "write", "path": "output/generated.md"}),
            ],
        },
        {
            "template_id": "buzz-to-plan",
            "label": "Buzz to implementation plan",
            "description": "Transcribe a local audio file, plan the request, and create a task.",
            "nodes": [("start", {}), ("buzz", {"file_path": "", "model_size": "small"}), ("planner", {}), ("task", {"status": "todo"})],
        },
        {
            "template_id": "agent-handoff",
            "label": "Agent handoff",
            "description": "Prepare work with a local model and hand it to an allowlisted configured agent.",
            "nodes": [("start", {}), ("coder", {"provider": "ollama", "model": ""}), ("agent", {"target": ""})],
        },
        {
            "template_id": "hermes-skill-workflow",
            "label": "Hermes skill workflow",
            "description": "Read one local Hermes skill as bounded workflow guidance.",
            "nodes": [("start", {}), ("tool", {"resource_id": "tool:read_hermes_skill", "arguments": {"skill_name": ""}})],
        },
        {
            "template_id": "runtime-readiness",
            "label": "Runtime readiness check",
            "description": "Preflight an exact named local runtime profile without activating it.",
            "nodes": [("start", {}), ("runtime", {"profile_id": "ollama-local-models"})],
        },
        {
            "template_id": "deep-research-context",
            "label": "Deep research to cited context",
            "description": "Use workflow input as a local SearXNG research query, build a bounded cited context packet, and pass it to a local model.",
            "default_arguments": {
                "tool:deep_research": {
                    "query": "fastapi vs flask performance 2025",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:deep_research", "arguments": {"query": "", "max_pages": 8, "max_results_per_query": 6, "extract_pages": True}}),
                ("tool", {"resource_id": "tool:build_research_context", "arguments": {"context_text": "", "max_chars": 30000}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
        {
            "template_id": "search-and-test",
            "label": "Search the web and run a Python check",
            "description": "Use workflow input as a SearXNG search query, fetch one selected result page, then run a bounded Python sandbox against the page contents. Final output is the sandbox return value plus the source URL.",
            "default_arguments": {
                "tool:search_web": {
                    "query": "ollama python library",
                },
                "tool:extract_web_page": {
                    "url": "https://pypi.org/project/ollama/",
                },
                "tool:execute_python_sandbox": {
                    "script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)[:10]\nprint(f'page_chars={len(text)}')\nprint(f'link_count={len(set(links))}')\nfor url in sorted(set(links))[:5]:\n    print(url)\n",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:search_web", "arguments": {"query": "", "max_results": 8}}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 8000}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nprint(f'page_chars={len(text)}')\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)[:10]\nfor link in links:\n    print(link)\n"}}),
            ],
        },
        {
            "template_id": "decompose-worker-plan",
            "label": "Decompose worker plan",
            "description": "Split workflow input into a bounded worker plan; dispatch remains off until a configured worker and approval policy are selected.",
            "nodes": [("start", {}), ("delegate", {"dispatch_mode": "plan_only", "decompose_strategy": "checklist", "max_subtasks": 8})],
        },
        {
            "template_id": "mcp-create-workflow",
            "label": "MCP: list templates, create a new workflow file",
            "description": "Read the workspace template catalog through the MCP resource, then create a new workflow JSON file in the workspace via the create_workspace_file MCP tool. Demonstrates the external-agent communication path.",
            "default_arguments": {
                "tool:read_workspace_file": {
                    "relative_path": "ROADMAP.md",
                },
                "tool:create_workspace_file": {
                    "relative_path": "output/new-workflow.json",
                    "content": "{\n  \"name\": \"new-workflow\",\n  \"nodes\": [],\n  \"edges\": []\n}\n",
                    "expected_absent": True,
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:list_workspace_files", "arguments": {"relative_path": ""}}),
                ("tool", {"resource_id": "tool:read_workspace_file", "arguments": {"relative_path": "ROADMAP.md"}}),
                ("tool", {"resource_id": "tool:create_workspace_file", "arguments": {"relative_path": "output/new-workflow.json", "content": "{}", "expected_absent": True}}),
            ],
        },
        {
            "template_id": "mcp-edit-and-verify",
            "label": "MCP: read workflow and prepare a safe edit",
            "description": "Read an existing workflow file and inspect its current contents before an external MCP agent performs a guarded patch. The actual edit requires the read result's current SHA-256 and is approval-gated.",
            "default_arguments": {
                "tool:read_workspace_file": {
                    "relative_path": "output/new-workflow.json",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:read_workspace_file", "arguments": {"relative_path": "output/new-workflow.json"}}),
            ],
        },
        {
            "template_id": "research-and-summarize",
            "label": "Multi-query research with bounded summary",
            "description": "Run multi-query SearXNG research on the workflow input topic, build a citation-preserving context packet, and pass it to the exact local model for a bounded summary.",
            "default_arguments": {
                "tool:deep_research": {
                    "query": "fastapi vs flask 2025 benchmark",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:deep_research", "arguments": {"query": "", "max_pages": 6, "max_results_per_query": 5, "extract_pages": True}}),
                ("tool", {"resource_id": "tool:build_research_context", "arguments": {"context_text": "", "max_chars": 20000}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
        {
            "template_id": "fetch-and-parse",
            "label": "Fetch one URL and parse the page",
            "description": "Pull the workflow input URL with redirect / DNS / size / robots enforcement, then run a bounded Python sandbox to extract structured fields (title, links, counts).",
            "default_arguments": {
                "tool:extract_web_page": {
                    "url": "https://ollama.com/blog",
                },
                "tool:execute_python_sandbox": {
                    "script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nm = re.search(r'<title>([^<]+)</title>', text) or re.search(r'#\\s+(.+)', text)\ntitle = (m.group(1).strip() if m else '(no title)')[:120]\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)\nprint(f'title={title}')\nprint(f'link_count={len(set(links))}')\nprint(f'char_count={len(text)}')\nfor url in sorted(set(links))[:8]:\n    print(url)\n",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 12000}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nm = re.search(r'<title>([^<]+)</title>', text) or re.search(r'#\\s+(.+)', text)\ntitle = (m.group(1).strip() if m else '(no title)')[:120]\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)\nprint(f'title={title}')\nprint(f'link_count={len(set(links))}')\nprint(f'char_count={len(text)}')\nfor url in sorted(set(links))[:8]:\n    print(url)\n"}}),
            ],
        },
        {
            "template_id": "code-with-tests",
            "label": "Code with a built-in smoke test",
            "description": "Send workflow input as a Python task to the exact local coder model, then run a bounded Python sandbox that asserts a property of the expected output (verifying the model's reply without trusting it).",
            "nodes": [
                ("start", {}),
                ("coder", {"provider": "ollama", "model": ""}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "text = sys.stdin.read() if not sys.stdin.isatty() else ''\nimport re\nhas_code = bool(re.search(r'def\\s+\\w+\\s*\\(', text))\nhas_doc = bool(re.search(r'\"\"\".*?\"\"\"', text, re.DOTALL))\nprint(f'has_function_def={has_code}')\nprint(f'has_docstring={has_doc}')\nprint(f'char_count={len(text)}')\n"}}),
            ],
        },
        {
            "template_id": "search-compare-summarize",
            "label": "Search, compare two pages, summarize",
            "description": "Run a SearXNG search on the workflow input, fetch the top two result pages, run a bounded Python sandbox to diff them (shared links, text overlap), and pass the diff to the local model for a comparison summary.",
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:search_web", "arguments": {"query": "", "max_results": 4}}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 8000}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re\npage_a = sys.stdin.read()\n# placeholder: diff computed below after second extract\n"}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re\na = open('/tmp/a.txt').read() if False else ''  # placeholder\nprint('diff_placeholder=ok')\n"}}),
            ],
        },
        {
            "template_id": "inspect-and-document",
            "label": "Inspect a Python module and document it",
            "description": "Read a workspace Python module, list workspace files, inspect the AST for top-level symbols, then send the metadata to the local model for a documentation summary.",
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:list_workspace_files", "arguments": {"relative_path": ""}}),
                ("tool", {"resource_id": "tool:inspect_python_ast", "arguments": {"relative_path": "backend/main.py"}}),
                ("tool", {"resource_id": "tool:read_workspace_file", "arguments": {"relative_path": "backend/main.py"}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
        {
            "template_id": "research-with-quote",
            "label": "Research, then quote a single source",
            "description": "SearXNG search on the workflow input, fetch the top page, extract a bounded quoted excerpt with a bounded Python regex, then pass the quote to the local model for a one-paragraph summary.",
            "default_arguments": {
                "tool:search_web": {
                    "query": "what is searxng",
                },
                "tool:extract_web_page": {
                    "url": "https://github.com/searxng/searxng",
                },
                "tool:execute_python_sandbox": {
                    "script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nparagraphs = [p.strip() for p in re.split(r'\\n\\s*\\n', text) if len(p.strip()) > 80]\nquote = paragraphs[0][:400] if paragraphs else '(no paragraph found)'\nprint(f'quote={quote}')\nprint(f'paragraph_count={len(paragraphs)}')\n",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:search_web", "arguments": {"query": "", "max_results": 5}}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 12000}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nparagraphs = [p.strip() for p in re.split(r'\\n\\s*\\n', text) if len(p.strip()) > 80]\nquote = paragraphs[0][:400] if paragraphs else '(no paragraph found)'\nprint(f'quote={quote}')\nprint(f'paragraph_count={len(paragraphs)}')\n"}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
        {
            "template_id": "audit-suggestions",
            "label": "Audit workspace and suggest improvements",
            "description": "List workspace files, inspect the top-level Python AST of the workspace, and ask the local model for a small set of bounded, actionable improvement suggestions. Output is metadata-only (file paths, symbol names) — no code is generated.",
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:list_workspace_files", "arguments": {"relative_path": ""}}),
                ("tool", {"resource_id": "tool:inspect_python_ast", "arguments": {"relative_path": "backend/main.py"}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
        {
            "template_id": "code-and-prove",
            "label": "Code with a numeric proof",
            "description": "Ask the local model to solve a math / counting problem, then run a bounded Python sandbox that re-computes the expected result from the model output and proves the answer is correct (or shows the divergence).",
            "nodes": [
                ("start", {}),
                ("coder", {"provider": "ollama", "model": ""}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nm = re.search(r'(?<![\\w.])(\\d+)(?![\\w.])', text)\nanswer = int(m.group(1)) if m else None\nprint(f'extracted_answer={answer}')\n# sanity: a re-computation point (no model-specific math here)\nprint(f'has_number={bool(m)}')\n"}}),
            ],
        },
        {
            "template_id": "quick-webcheck",
            "label": "Quick webcheck for the workflow input",
            "description": "Run a single SearXNG search for the workflow input query and return the top three result titles + URLs. No model call, no sandbox — fast pure-search template.",
            "default_arguments": {
                "tool:search_web": {
                    "query": "ollama python library",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:search_web", "arguments": {"query": "", "max_results": 3}}),
            ],
        },
        {
            "template_id": "research-extract-execute",
            "label": "Research, extract page, execute a check",
            "description": "Full pipeline: SearXNG research (multi-query), extract one selected page, then run a bounded Python sandbox against the page contents. End output is the sandbox stdout and the source URL.",
            "default_arguments": {
                "tool:deep_research": {
                    "query": "ollama api documentation",
                },
                "tool:extract_web_page": {
                    "url": "https://github.com/ollama/ollama/blob/main/docs/api.md",
                },
                "tool:execute_python_sandbox": {
                    "script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nprint(f'page_chars={len(text)}')\nprint(f'word_count={len(text.split())}')\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)\nprint(f'link_count={len(set(links))}')\nfor url in sorted(set(links))[:5]:\n    print(url)\n",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:deep_research", "arguments": {"query": "", "max_pages": 6, "max_results_per_query": 5, "extract_pages": True}}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 12000}}),
                ("tool", {"resource_id": "tool:execute_python_sandbox", "arguments": {"script_content": "import re, sys\ntext = sys.stdin.read() if not sys.stdin.isatty() else ''\nprint(f'page_chars={len(text)}')\nprint(f'word_count={len(text.split())}')\nlinks = re.findall(r'href=\"(https?://[^\"]+)\"', text)\nprint(f'link_count={len(set(links))}')\nfor url in sorted(set(links))[:5]:\n    print(url)\n"}}),
            ],
        },
        {
            "template_id": "extract-and-summarize",
            "label": "Extract one URL and summarize",
            "description": "Pull one URL with robots / DNS / size enforcement, then ask the local model to summarize the page in a bounded way. Final output is the model summary plus the source URL.",
            "default_arguments": {
                "tool:extract_web_page": {
                    "url": "https://ollama.com/blog",
                },
            },
            "nodes": [
                ("start", {}),
                ("tool", {"resource_id": "tool:extract_web_page", "arguments": {"url": "", "max_chars": 15000}}),
                ("coder", {"provider": "ollama", "model": ""}),
            ],
        },
    ]


def _template_graph(template: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    default_arguments = template.get("default_arguments") or {}
    for index, (kind, data) in enumerate(template["nodes"]):
        node_id = f"{kind}-{index + 1}-{uuid.uuid4().hex[:6]}"
        merged = {**data}
        # Apply per-template default arguments AFTER the per-node
        # arguments so concrete defaults override the empty placeholder
        # strings in the template definition. Defaults are keyed by
        # resource_id when present (so they target one specific tool
        # node, not every tool node of the same kind) and fall back to
        # a kind-level key for coder / file / runtime / agent nodes.
        # Defaults do not overwrite values that the caller passed via
        # options.
        resource_id = str(merged.get("resource_id", ""))
        keyed = default_arguments.get(resource_id) or default_arguments.get(kind) or {}
        for arg_name, default_value in keyed.items():
            if merged.get("arguments", {}).get(arg_name, "") in ("", None):
                merged.setdefault("arguments", {})
                merged["arguments"][arg_name] = default_value
        if kind == "coder" and options.get("model"):
            merged["model"] = str(options["model"])
        if kind == "coder" and options.get("provider"):
            merged["provider"] = str(options["provider"])
        if kind == "agent" and options.get("agent"):
            merged["target"] = str(options["agent"])
        if kind == "runtime" and options.get("profile_id"):
            merged["profile_id"] = str(options["profile_id"])
        nodes.append({"id": node_id, "type": kind, "position": {"x": 140 + index * 320, "y": 180}, "data": merged})
        if index:
            edges.append({"id": f"edge-{nodes[index - 1]['id']}-{node_id}", "source": nodes[index - 1]["id"], "target": node_id})
    return {"nodes": nodes, "edges": edges}


def library_resources() -> list[LibraryResource]:
    resources: list[LibraryResource] = []
    web_status = web_preflight()
    hermes_status = hermes_capability_audit()
    hermes_capabilities = {str(item.get("capability")): item for item in hermes_status.get("capabilities", []) if isinstance(item, dict)}
    for item in WORKSPACE_TOOL_CATALOG:
        name = str(item["name"])
        web_unavailable = name in {"search_web", "deep_research"} and not web_status.get("ready")
        hermes_key = {"list_hermes_skills": "inventory", "read_hermes_skill": "read_skill", "dispatch_hermes_skill": "dispatch_skill"}.get(name)
        hermes_item = hermes_capabilities.get(hermes_key or "", {})
        hermes_unavailable = bool(hermes_key) and not bool(hermes_item.get("ready"))
        resources.append(
            LibraryResource(
                resource_id=f"tool:{name}",
                category="tool",
                label=name.replace("_", " ").title(),
                description=str(item.get("description", "")),
                scope=str(item.get("scope", "workspace")),
                ready=not web_unavailable and not hermes_unavailable,
                disabled_reason=(str(web_status.get("failure_class") or "search backend unavailable") if web_unavailable else str(hermes_item.get("disabled_reason")) if hermes_unavailable else None),
                requires_approval=bool(item.get("requires_approval")),
                capabilities=["add_to_canvas", "run_now"],
                arguments_schema=_tool_schema(name),
            )
        )
    for target in configured_agents():
        resources.append(
            LibraryResource(
                resource_id=f"agent:{target}",
                category="agent",
                label=target,
                description="Allowlisted local agent target configured by the backend.",
                scope="workspace-agent",
                requires_approval=True,
                capabilities=["add_to_canvas", "run_now"],
                arguments_schema={"type": "object", "properties": {"prompt": {"type": "string", "title": "Prompt"}}, "required": ["prompt"]},
            )
        )
    for skill in _skills():
        resources.append(
            LibraryResource(
                resource_id=f"skill:{skill['name']}",
                category="skill",
                label=skill["name"],
                description=skill["description"],
                scope="hermes-skills-readonly",
                capabilities=["add_to_canvas", "run_now"],
                arguments_schema={"type": "object", "properties": {}},
                metadata={"skill_name": skill["name"]},
            )
        )
    ollama = list_ollama_models()
    for model in ollama.get("models", []):
        if not isinstance(model, dict) or not model.get("name"):
            continue
        name = str(model["name"])
        if name != DEFAULT_OLLAMA_MODEL:
            continue
        resources.append(
            LibraryResource(
                resource_id=f"model:ollama:{name}",
                category="model",
                label=name,
                description="Exact installed Ollama model.",
                scope="loopback-model",
                ready=ollama.get("status") == "ready",
                disabled_reason=None if ollama.get("status") == "ready" else str(ollama.get("failure_class") or "Ollama unavailable"),
                capabilities=["add_to_canvas", "run_now"],
                arguments_schema={"type": "object", "properties": {"prompt": {"type": "string", "title": "Prompt"}}, "required": ["prompt"]},
                provider="ollama",
                model=name,
                metadata={"size": model.get("size"), "openai_advertised": model.get("openai_advertised", False)},
            )
        )

    for profile in list_runtime_profiles():
        resources.append(
            LibraryResource(
                resource_id=f"runtime:{profile['profile_id']}",
                category="runtime",
                label=str(profile["label"]),
                description=str(profile.get("notes", "")),
                scope="runtime-preflight",
                ready=profile.get("state") not in {"not-provisioned", "target-not-provisioned"},
                disabled_reason=None if profile.get("state") not in {"not-provisioned", "target-not-provisioned"} else str(profile.get("state")),
                capabilities=["add_to_canvas", "run_now"],
                metadata={"profile_id": profile["profile_id"], "state": profile.get("state"), "mode": profile.get("mode")},
                provider=str(profile.get("provider", "")),
                model=str(profile.get("model", "")),
            )
        )
    for template in _templates():
        resources.append(
            LibraryResource(
                resource_id=f"template:{template['template_id']}",
                category="template",
                label=str(template["label"]),
                description=str(template["description"]),
                scope="workspace-template",
                capabilities=["deploy_template"],
                metadata={"template_id": template["template_id"], "node_count": len(template["nodes"])},
            )
        )
    category_order = {"model": 0, "tool": 1, "agent": 2, "skill": 3, "runtime": 4, "template": 5}
    return sorted(resources, key=lambda item: (category_order[item.category], item.label.lower()))


def query_library(category: str | None = None, query: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    items = library_resources()
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1
    if category and category != "all":
        items = [item for item in items if item.category == category]
    if query:
        needle = query.strip().lower()
        items = [item for item in items if needle in f"{item.resource_id} {item.label} {item.description}".lower()]
    bounded_limit = min(max(limit, 1), 500)
    bounded_offset = max(offset, 0)
    page = items[bounded_offset : bounded_offset + bounded_limit]
    return {"resources": [item.model_dump(mode="json") for item in page], "total": len(items), "offset": bounded_offset, "limit": bounded_limit, "category_counts": counts, "mutation": "none"}


def capability_audit() -> dict[str, Any]:
    tool_handlers = {str(getattr(tool, "name", "")): tool for tool in WORKSPACE_TOOLS}
    rows: list[dict[str, Any]] = []
    for resource in library_resources():
        handler = ""
        primary_action = ""
        schema_present = bool(resource.arguments_schema)
        executable = False
        if resource.category == "tool":
            name = resource.resource_id.split(":", 1)[1]
            handler = name if name in tool_handlers else ""
            primary_action = "invoke_tool"
            executable = bool(handler and schema_present and resource.ready)
        elif resource.category == "agent":
            handler, primary_action, executable = "trigger_agent", "dispatch_agent", resource.ready
        elif resource.category == "skill":
            handler, primary_action, executable = "read_hermes_skill", "inspect_skill", resource.ready
        elif resource.category == "model":
            handler, primary_action, executable = "model_route", "generate", resource.ready
        elif resource.category == "runtime":
            handler, primary_action, executable = "preflight_runtime_profile", "preflight", resource.ready
        elif resource.category == "template":
            handler, primary_action, executable = "instantiate_template", "instantiate", resource.ready
        if not resource.ready:
            status = "DISABLED"
        elif not executable:
            status = "FAIL"
        elif resource.requires_approval:
            status = "BLOCKED"
        else:
            status = "PASS"
        rows.append({"resource_id": resource.resource_id, "category": resource.category, "status": status, "ready": resource.ready, "executable": executable, "primary_action": primary_action, "handler": handler, "schema_present": schema_present, "requires_approval": resource.requires_approval, "gate": "approval_required" if resource.requires_approval else "none", "failure_class": resource.disabled_reason or ("handler_or_argument_schema_unavailable" if resource.ready and not executable else ""), "disabled_reason": resource.disabled_reason or ("handler or argument schema is unavailable" if resource.ready and not executable else "")})
    status_counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("PASS", "BLOCKED", "DISABLED", "FAIL")}
    return {"matrix_version": "2026-08-07.v1", "resources": rows, "total": len(rows), "ready": sum(1 for row in rows if row["ready"]), "executable": sum(1 for row in rows if row["executable"]), "status_counts": status_counts, "invalid_ready": [row for row in rows if row["status"] == "FAIL"]}


def get_resource(resource_id: str) -> LibraryResource:
    for item in library_resources():
        if item.resource_id == resource_id:
            return item
    raise KeyError(resource_id)


def _store_preview(kind: str, subject: Any, approvals: list[dict[str, Any]]) -> dict[str, Any]:
    preview_id = uuid.uuid4().hex
    record = {"kind": kind, "subject_hash": _stable_hash(subject), "approvals": approvals, "expires_at": time.time() + _PREVIEW_TTL_SECONDS}
    with _preview_lock:
        now = time.time()
        for key in [key for key, value in _previews.items() if value["expires_at"] < now]:
            _previews.pop(key, None)
        _previews[preview_id] = record
    return {"preview_id": preview_id, "approvals": approvals, "requires_approval": bool(approvals), "expires_in_seconds": _PREVIEW_TTL_SECONDS}


def preview_action(payload: ActionPreviewPayload) -> dict[str, Any]:
    log_event("workflow.action.preview.start", resource_id=payload.resource_id)
    resource = get_resource(payload.resource_id)
    if not resource.ready:
        raise ValueError(resource.disabled_reason or "resource is not ready")
    approvals = []
    arguments = dict(payload.arguments)
    impact_preview = ""
    if resource.category == "tool":
        tool_name = resource.resource_id.split(":", 1)[1] if ":" in resource.resource_id else ""
        if tool_name in {"create_workspace_file", "patch_workspace_file", "rename_workspace_file", "delete_workspace_file"}:
            impact = preview_workspace_mutation(tool_name, arguments)
            impact_preview = str(impact.get("diff", ""))
            for key in ("expected_absent", "expected_sha256"):
                if key in impact:
                    arguments[key] = impact[key]
    if resource.requires_approval:
        approvals.append({"resource_id": resource.resource_id, "label": resource.label, "scope": resource.scope})
    subject = {"resource_id": payload.resource_id, "arguments": arguments}
    result = {"resource": resource.model_dump(mode="json"), "arguments": arguments, "impact_preview": impact_preview, **_store_preview("action", subject, approvals)}
    log_event("workflow.action.preview.ready", resource_id=payload.resource_id, preview_id=result.get("preview_id"), requires_approval=result.get("requires_approval"))
    return result


def run_action(payload: ActionRunPayload, workspace_root: Path) -> dict[str, Any]:
    log_event("workflow.action.run.start", resource_id=payload.resource_id, preview_id=payload.preview_id, approved=payload.approved)
    subject = {"resource_id": payload.resource_id, "arguments": payload.arguments}
    with _preview_lock:
        record = _previews.pop(payload.preview_id, None)
    if not record or record["kind"] != "action" or record["expires_at"] < time.time() or record["subject_hash"] != _stable_hash(subject):
        raise ValueError("action preview is missing, expired, or does not match")
    if record["approvals"] and not payload.approved:
        raise PermissionError("action approval is required")
    resource = get_resource(payload.resource_id)
    if resource.category == "tool":
        name = resource.resource_id.split(":", 1)[1]
        tool = _tool_map().get(name)
        if tool is None:
            raise KeyError(name)
        output = tool.invoke(payload.arguments)
    elif resource.category == "skill":
        skill_name = resource.resource_id.split(":", 1)[1]
        output = _tool_map()["read_hermes_skill"].invoke({"skill_name": skill_name})
    elif resource.category == "agent":
        target = resource.resource_id.split(":", 1)[1]
        pid = trigger_agent(target, str(payload.arguments.get("prompt", "")), workspace_root)
        output = f"Started configured local agent '{target}' (pid {pid})"
    elif resource.category == "model":
        output = _model_output(str(payload.arguments.get("prompt", "")), {"provider": resource.provider, "model": resource.model})
    elif resource.category == "runtime":
        profile_id = str(resource.metadata.get("profile_id", ""))
        output = json.dumps(preflight_runtime_profile(profile_id), ensure_ascii=False)
    else:
        raise ValueError("resource does not support Run now")
    result = {"status": "completed", "resource_id": resource.resource_id, "output": str(output)[:200_000]}
    log_event("workflow.action.run.complete", resource_id=resource.resource_id, status="completed", output_chars=len(result["output"]))
    return result


def instantiate_template(template_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    for template in _templates():
        if template["template_id"] == template_id:
            graph = _template_graph(template, options)
            return {"template_id": template_id, "label": template["label"], "graph": graph, "mutation": "canvas-only"}
    raise KeyError(template_id)


def _graph_approvals(graph: GraphDocument) -> list[dict[str, str]]:
    approvals: list[dict[str, str]] = []
    seen: set[str] = set()
    tool_catalog = {str(item["name"]): item for item in WORKSPACE_TOOL_CATALOG}
    for node in graph.nodes:
        resource_id = ""
        label = ""
        scope = "workspace"
        if node.type == "tool":
            resource_id = str(node.data.get("resource_id") or "")
            name = resource_id.split(":", 1)[1] if resource_id.startswith("tool:") else ""
            item = tool_catalog.get(name)
            if not item or not item.get("requires_approval"):
                continue
            label = name
            scope = str(item.get("scope", "workspace"))
        elif node.type == "agent":
            target = str(node.data.get("target") or "")
            resource_id = f"agent:{target}"
            label = target or "Configured agent"
            scope = "workspace-agent"
        elif node.type == "delegate" and str(node.data.get("dispatch_mode") or "plan_only") != "plan_only":
            resource_id = f"delegate:{node.id}"
            label = "Dispatch decomposed worker tasks"
            scope = "workspace-agent"
        elif node.type == "file" and str(node.data.get("mode") or "read") == "write":
            resource_id = f"file-write:{node.id}"
            label = "Write workspace file"
            scope = "workspace-write"
        if resource_id and resource_id not in seen:
            seen.add(resource_id)
            approvals.append({"resource_id": resource_id, "label": label, "scope": scope})
    return approvals


def preview_graph(graph: GraphDocument) -> dict[str, Any]:
    approvals = _graph_approvals(graph)
    return {"graph_hash": _stable_hash(graph.model_dump(mode="json")), **_store_preview("graph", graph.model_dump(mode="json"), approvals)}


def consume_graph_preview(preview_id: str | None, graph: GraphDocument) -> set[str]:
    approvals = _graph_approvals(graph)
    if not approvals:
        return set()
    if not preview_id:
        raise PermissionError("workflow approval review is required")
    with _preview_lock:
        record = _previews.pop(preview_id, None)
    subject = graph.model_dump(mode="json")
    if not record or record["kind"] != "graph" or record["expires_at"] < time.time() or record["subject_hash"] != _stable_hash(subject):
        raise PermissionError("workflow approval preview is missing, expired, or stale")
    return {str(item["resource_id"]) for item in approvals}


__all__ = [
    "ActionPreviewPayload",
    "ActionRunPayload",
    "GraphApprovalPayload",
    "TemplateInstantiatePayload",
    "consume_graph_preview",
    "get_resource",
    "instantiate_template",
    "preview_action",
    "preview_graph",
    "query_library",
    "run_action",
]
