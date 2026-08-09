# Refactor Workflow Studio — Roadmap (maintained)

> **Source of truth for plans.** Detailed frozen plans live in
> `.hermes/plans/`. Implementation state and receipts live in
> `PROJECT_TRACKER.md`. This file is the **maintained summary** — one
> page to see where the project is headed, what is shipped, what is
> next, and how we maintain it. Update after every phase boundary.

---

## 0. Mission

A local-first visual workspace for building, executing, and inspecting
multi-step AI workflows. Every exposed capability is honestly
executable or visibly disabled — no silent stubs. One exact local
model — no silent cloud fallback. Drew stays in the loop for every
protected action.

**Hard constraints (locked by Drew):**

| # | Constraint | Notes |
|---|---|---|
| C1 | Exact Ollama model only | `hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M`. No llama3.2 / hermes3 / Qwen / Nanbeige / BF16 / MiniMax fallback without explicit approval. |
| C2 | Loopback-only network exposure | Docker ports bound to `127.0.0.1`. No LAN / public exposure without approval. |
| C3 | Parent-only execution | No subagents, no delegated workers, no hidden orchestration unless Drew explicitly re-authorizes. |
| C4 | Workspace-rooted tools | Every mutation is bounded to the configured `WORKSPACE_ROOT`. No arbitrary shell, no credential inheritance. |
| C5 | Fail-closed defaults | Anything not explicitly verified returns a structured `not_ready` / `tool_not_allowlisted` / `preflight_failed` — never a fabricated success. |
| C6 | Approval granularity = capability | Per-action or step-through approval is selectable per workflow; preflight-only is the legacy mode. |
| C7 | Persistent durable runs | Run history, decisions, approvals, and context retained until explicit transactional deletion. |
| C8 | Canonical tracker | `PROJECT_TRACKER.md` is append-only. Never overwrite history. |

---

## 1. Status snapshot

| Surface | State | Where |
|---|---|---|
| Native frontend (Next.js) | Live on `127.0.0.1:3000` (accepted build) | `frontend/` |
| Native backend (FastAPI + LangGraph) | Live on `127.0.0.1:8000` | `backend/` |
| Docker smoke stack | Live on `127.0.0.1:3100/8100/11435/8889` | `docker-compose.yml` |
| Native Ollama | Live on `127.0.0.1:11434` with exact LFM tag | host `~/.ollama` |
| Local SearXNG | Live on `127.0.0.1:8888` (research route) | native |
| GitHub | Branch `feat/shared-nanbeige-agentic-workspace` synced; PR #1 open | `phoenixfire808/ai-workspace` |

**Verification receipts (latest):**

- `8/8` backend tests pass (`backend/tests/test_*.py`).
- `npm run typecheck` passes.
- `POST /api/settings/model` with `llama3.2:3b` → `HTTP 400`.
- `GET /api/health` → `model_ready=true`, `model_policy=exact_only`, exact tag persisted.
- Frontend `:3100` and backend `:8100` → HTTP 200.
- No credential value present in `.env.docker.example` or tracked source.

---

## 2. Frozen plans (source)

These are the approved specifications. Read them before starting any
phase that touches their scope.

| Plan | File | Phase |
|---|---|---|
| Unified Agent + Tool Library | `.hermes/plans/2026-08-07_002401-unified-agent-tool-library.md` | ✅ shipped (Phase 25) |
| Resizable workspace panels | `.hermes/plans/2026-08-07_010712-resizable-workspace-panels.md` | ✅ shipped (Phase 26) |
| Durable HITL workflow runtime | `.hermes/plans/2026-08-07_014925-durable-hitl-workflow-runtime.md` | 🟡 in progress (Phases 27–43) |
| Option-complete workspace | `.hermes/plans/2026-08-07_044931-option-complete-workspace-roadmap.md` | 🟡 in progress |

---

## 3. Phases

> Status legend: ✅ shipped • 🟡 in progress • ⏳ next • 🚫 deferred / blocked.

### Phase 25 — Unified Local Library ✅
Single backend-owned normalized registry exposed at `/api/library`
(217 entries). UI: searchable category + search box, `Add to canvas`
and `Run now` paths, Ollama-first ordering, eight starter templates.
Commits: `0088f54`, `a72a8ff`, `b1835bb`.

### Phase 26 — Resizable workspace panels ✅
Draggable side splitters with collapse buttons, keyboard resize,
persisted and resettable layout, taller resizable library list, 320/340
px defaults. Commit: `470fe60` (published to PR #1).

### Phase 27 — Nanbeige retirement + LFM global default ✅
`/api/settings/model` persists the exact LFM tag to SQLite. All
non-exact saves rejected. Frontend `Local Library` shows the exact
model as pinned. Commits: `c69c3ff`, `05c71ee`.

### Phase 28 — Async LLM hang fix ✅
Sync `iter_lfm_events` generator with `ThreadPoolExecutor` decouples
the blocking LLM call from the FastAPI event loop. SSE and sync JSON
endpoints stream correctly. Commit: `5fee07c`.

### Phase 43 — Docker migration 🟡
- ✅ Loopback-only Compose stack (`docker-compose.yml` + Dockerfiles).
- ✅ Exact-model one-shot verifier (`mo-ollama-model-init`).
- ✅ 8/8 backend tests pass; frontend typecheck clean.
- ✅ Smoke stack live on `3100/8100/11435/8889`.
- ⏳ Native→Docker cutover acceptance (deferred per testing policy).
- ⏳ Multi-GPU placement verification (`RTX 5060 Ti` + `RTX 2070 SUPER`).

### Phase 50 — Durable HITL workflow runtime 🟡
Approved specification at `.hermes/plans/2026-08-07_014925-...md`.
Shards owned by the parent session (parent-only per C3):

| Shard | Status | Receipt |
|---|---|---|
| Durable run / decision / chat / delete APIs | 🟡 | `backend/execution_runtime.py` |
| Capability-bound file mutation (create / patch / rename / delete with diff approval) | 🟡 | `backend/tools.py` |
| Branch / chunk / merge scheduling | ⏳ | — |
| Endpoint / hardware profile registry | 🟡 | `backend/model_profiles.py` |
| Approval / chat / plugin runtime | 🟡 | graph + SSE |
| Run Inspector UI | 🟡 | `frontend/components/RunInspector.tsx` |
| Decompose / Delegate plan-only path | 🟡 | bounded — never spawns workers without approval |
| Plugin registry | 🟡 | local, no placeholder |
| Consolidated acceptance batch | ⏳ | deferred per testing policy |

### Phase 60 — Option-complete workspace 🟡
Backend-owned normalized option registry + resolver. Every option has
one stable ID, safe default, scope, effect, prerequisite, evidence
tier, and rollback path. UI: read-only registry table driven by the
same definition. Status: schema complete, runtime integration
sharded into Phase 50.

### Phase 70 — Multi-GPU placement (deferred) 🚫
Ollama controls placement within a server. Strict per-GPU targeting
needs separate visible-device runtime profiles plus recorded
requested-vs-observed placement. Awaiting Drew's explicit profile
selection before any listener mutation.

### Phase 80 — Native→Docker cutover 🚫
Smoke stack stays alongside native services until consolidated
acceptance passes. No standard-port cutover without explicit
approval.

---

## 4. Next up (parent todo)

In priority order, parent-only:

1. **Track maintenance** — keep `ROADMAP.md` and `PROJECT_TRACKER.md`
   consistent after every meaningful change (this file exists for
   that).
2. **Phase 50 acceptance** — durable runtime API contract verification,
   Run Inspector visual acceptance, branch/merge executor unit
   coverage.
3. **Phase 43 closure** — record the post-CUDA Ollama readiness,
   confirm the exact LFM tag is still the only model loaded, and
   archive the legacy `:3000/:8000/:11434` smoke once `:3100/:8100/:11435/:8889`
   parity is final.
4. **Phase 60 inventory** — option registry audit: zero invalid-ready
   entries, capability matrix export to Markdown.
5. **Phase 70 preflight** — define one read-only multi-GPU profile
   test (request N GPUs, observe placement) without repointing live
   listeners.

---

## 5. Maintainer protocol

Every session that ships a meaningful change updates this file in
**one** atomic commit alongside the change. Order is:

1. Land the source/test/doc change.
2. Update the phase status table (✅ / 🟡 / ⏳ / 🚫).
3. Append a dated entry to §6 (Changelog) with the commit SHA(s).
4. Mirror the receipt in `PROJECT_TRACKER.md` (append-only).
5. Push the branch; PR #1 stays the authoritative review surface.

If a phase description becomes stale, **edit the description** rather
than letting two contradictory copies exist. If a frozen plan changes,
link the new plan file from §2 and update the affected phases.

---

## 6. Changelog (append-only)

> Newest entries on top. One bullet per shipped commit or phase
> boundary. Never delete; supersede with a new entry when retiring
> content.

| Date | Phase | Change | SHA(s) |
|---|---|---|---|
| 2026-08-08 | 44 | **Rename to Refactor Workflow Studio.** Display, FastAPI title, brand banner, ChatPanel, ControlCenterPanel, planner note, `package.json`, all model-profile / runtime / upgrade labels, options registry header, runbook, README, ROADMAP, plan titles, tracker header. Compose project + container names + volume + network → `refactor` / `rws-*`. SearXNG `secret_key` rotated. GitHub repo name + PR #1 preserved. | `(next)` |
| 2026-08-08 | 50/60 | Add option registry / Run Inspector / endpoint profiles (durable runtime slice) | `a72a8ff`, `0088f54`, `5fee07c`, `0fd2797`, `691d862` |
| 2026-08-08 | 27 | Retire Nanbeige from Refactor Workflow Studio, pin exact LFM as global default | `c69c3ff`, `05c71ee` |
| 2026-08-07 | 26 | Resizable workspace panels shipped | `470fe60` |
| 2026-08-07 | 25 | Unified Local Library shipped | `0088f54`, `b1835bb` |
| 2026-08-07 | 50 | Durable HITL runtime plan approved | `.hermes/plans/2026-08-07_014925-...md` |
| 2026-08-08 | 43 | Docker loopback-only Compose stack + exact-model one-shot verifier | `594cb80` |
| 2026-08-08 | 43 | Exact LFM lock enforced across backend, control center, coder UI | `ebed43b` |
| 2026-08-08 | — | Tracker append-only entry for Docker migration | `bd69249` |
| 2026-08-08 | — | Add maintained `ROADMAP.md` | `ac150b2` |