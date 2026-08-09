# Lightweight Local-Model Agent Harness

**Status:** Implementation in progress — standalone v0 deployed locally for acceptance
**Workspace:** `C:\Users\Drew\Documents\Jarvis_Context\Projects\ai-workspace`
**Canonical runtime:** `harness/lightweight_agent.py`
**Entry point:** `scripts/rws_local_harness.py`
**Loopback port:** `127.0.0.1:8110`

## Goal

Provide local models with their own small agent harness without loading the Refactor Workflow Studio UI, LangGraph, LangChain, or a persistent conversation database. The harness should be easy for local coding models and external coding CLIs to drive while preserving the existing MCP workspace safety contract.

## Design decision

The harness is a separate stdlib-only process:

```text
local coding model/client
          |
          v
127.0.0.1:8110  rws-local-harness
          |  direct OpenAI-compatible HTTP
          v
Ollama :11435/v1  (exact LFM model)
          |
          |  JSON-RPC HTTP, tool schemas, approval receipts
          v
RWS MCP :8100/mcp
          |
          v
workspace tools / SearXNG / approval + preimage policy
```

The harness owns only the model loop, tool-schema adaptation, bounded turns, and pending approval continuation. Workspace mutation policy remains in MCP; the harness does not duplicate file safety or preimage logic.

## Runtime contract

- Python standard library only for the harness process.
- Exact model: `hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M`.
- Ollama route: `/v1/chat/completions`, non-streaming v0 loop.
- MCP route: `tools/list` + `tools/call` over the existing local bridge.
- Safe-by-default tools: workspace listing/reading, AST inspection, skill reading, web search, and page extraction.
- Mutating/sandbox tools are visible to the model so it can request them, but first produce a preview and require explicit approval.
- Pending approvals are in-memory only and bounded to 32 receipts; restart clears them deliberately.
- No cloud fallback, hidden model substitution, shell execution outside the existing MCP tool policy, or persistent user history.

## Endpoints

- `GET /health` — exact model advertisement, MCP status, tool count, dependency/runtime metadata.
- `GET /tools` — MCP-derived tool catalog with `safe_by_default` and `approval_required` flags.
- `GET /v1/models` — local harness model identity for simple client discovery.
- `POST /run` — `{message, approved_tools?, max_turns?}`; returns completed answer, tool events, approval receipt, or bounded failure.
- `POST /resume` — `{run_id, approve: true|false}`; resumes a stored approval receipt or rejects it.

## Why this is lightweight

- No LangChain or LangGraph import.
- No FastAPI/ASGI server requirement.
- No SDK install; `urllib.request` drives both model and MCP.
- One `ThreadingHTTPServer` process, one model route, one in-memory pending map.
- Existing MCP remains the policy/tool adapter, avoiding a second implementation of workspace security.
- The model is loaded by Ollama, not duplicated inside the harness.

## Evidence and source notes

Selected official documentation was directly extracted after the local SearXNG discovery backend returned the same unrelated WSJ result for five independent official-doc queries. The discovery failure is recorded rather than hidden; direct extraction was restricted to these selected official URLs:

1. Ollama tool calling: <https://docs.ollama.com/capabilities/tool-calling> — tool schemas, assistant `tool_calls`, tool result messages, and bounded agent-loop pattern.
2. Ollama OpenAI compatibility: <https://docs.ollama.com/api/openai-compatibility> — `/v1/chat/completions`, streaming/tool support, model identity, and local OpenAI-shaped clients.
3. MCP specification: <https://modelcontextprotocol.io/specification/2025-06-18> — JSON-RPC, tools/resources/prompts, explicit consent, and tool safety expectations.
4. FastAPI lifespan guidance: <https://fastapi.tiangolo.com/advanced/events/> — shared model resources belong to application lifespan, but the dedicated harness intentionally avoids that heavier dependency.
5. LangChain overview: <https://docs.langchain.com/oss/python/langchain/overview> — agent harness is the model + prompt + tools + middleware loop; this project implements only the minimum local subset directly.

## Verification receipts

- `py_compile` passed for harness, entry point, and tests.
- Four focused harness unit tests passed.
- Compose configuration validation passed.
- Next acceptance gate: build/recreate `rws-harness`, verify `/health` and `/tools`, run exact local model `/run`, execute one safe `search_web` loop, and verify mutation preview/resume through the live MCP bridge.

## Next intentions

1. Start the dedicated Compose service without restarting the frontend.
2. Verify direct plain response and one structured safe-tool turn.
3. Verify a mutation returns `approval_required` before any write.
4. Verify explicit resume executes only the MCP-approved preview.
5. Keep v0 non-streaming until the core loop is proven; add SSE only as a separate versioned change.
6. Add a client helper only if external coding agents need less than the documented HTTP contract.
