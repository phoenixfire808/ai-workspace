# M⊕ AI Visual Workspace — Canonical Project Tracker

> This is the source of truth for the project roadmap, decisions, implementation state, verification receipts, and remaining work. Update it after every meaningful scope, architecture, file, dependency, or verification change.

## 1. Current status

- **Phase:** Runtime/GPU control, integrated terminal, and upgrade-center specification
- **Status:** Current M⊕ build is live for Drew's inspection on loopback with the shared RTX 2070 Nanbeige route; LFM2.5 remains an offline opt-in route; selectable GPU/model profiles, terminal, and safe upgrades are the next product slice
- **Workspace:** `C:\Users\Drew\Documents\Jarvis_Context\Projects\ai-workspace`
- **Repository boundary:** Standalone sibling workspace. The existing dirty `DrewLocalVoice` repository is not being modified for this project.
- **Last verified:** `2026-08-07 00:02:39 CDT`
- **Current parent todo:** Launch the current assembled M⊕ build on loopback so Drew can inspect its present UI and agentic workflow progress; preserve runtime-profile, terminal, and upgrade work as the next implementation slice
- **Testing policy:** Do not run the broad/final test batch until the implementation is assembled. Focused checks and the final smoke happen at the end in one consolidated verification pass.

### Immediate next action

Keep the existing publisher-fork Nanbeige runtime on the RTX 2070 SUPER as the verified default while defining the runtime-profile contract with Drew. Profiles must support RTX 5060 Ti only, RTX 2070 SUPER only, and explicitly approved dual-GPU modes without exposing arbitrary runtime arguments. Preserve the current LFM integration, and do not repoint a live listener until its replacement profile passes preflight and rollback checks.

## 1.1 Proposed LFM2.5-2.6B agent-engine upgrade

- **Source requested by Drew:** `https://huggingface.co/LiquidAI/LFM2.5-2.6B`
- **Local clone:** `D:\AI\Models\LFM2.5-2.6B` using Git LFS; the clone command exited 0 and fetched approximately 1.04 GiB. Production route remains unchanged.
- **Model facts from the publisher card:** 2.69B parameters, 131,072-token context, reasoning-first chat template, native tool/function-calling format, and on-device deployment focus.
- **Publisher caveat:** LFM2.5 is recommended for agentic workloads/tool use but is not recommended for agentic coding or knowledge-heavy tasks; this is a quality risk to benchmark rather than hide.
- **Backend slice requested:** richer `AgentState`, a native Python sandbox tool registry, cyclic LangGraph agent↔tools routing, and `/api/chat/stream` SSE.
- **Safety boundary:** sandbox execution must remain workspace-rooted, bounded, approval-aware, metadata-safe, and never execute arbitrary model-provided shell text without policy checks.
- **Current route boundary:** verified Nanbeige/SearXNG services remain active until Drew selects whether LFM replaces M⊕, is an explicit alternate, or is experimental only.

## 1.2 Live implementation log (append-only)

| Timestamp | Workstream | Receipt / state |
|---|---|---|
| 2026-08-06 23:18 CDT | Scope | Drew selected: keep Nanbeige as the default and add LFM2.5-2.6B as an explicit Coder/provider option. No silent fallback and no SearXNG route change. |
| 2026-08-06 23:18 CDT | Acquisition | `git clone https://huggingface.co/LiquidAI/LFM2.5-2.6B D:\\AI\\Models\\LFM2.5-2.6B` completed with exit code 0; Git LFS filtered approximately 1.04 GiB. |
| 2026-08-06 23:19 CDT | Background process receipt | Tracked clone process `proc_ed15b695f28e` completed normally with exit code 0; Git reported all 22 objects, all 11 files updated, and all 3 LFS payloads filtered successfully. |
| 2026-08-06 23:28 CDT | Acquisition verification | Scoped `git -c safe.directory=D:/AI/Models/LFM2.5-2.6B` verification passed: clone is clean on `main...origin/main`, revision `403f92a2c4d78f2505f874b8b1b713cc0c9b9ae8`, and all three LFS files (`model-00001-of-00002.safetensors`, `model-00002-of-00002.safetensors`, `tokenizer.json`) are hydrated. The ai-workspace directory itself is not a Git checkout; no repository mutation was attempted. |
| 2026-08-06 23:18 CDT | Acquisition verification blocker | Plain `git -C D:\\AI\\Models\\LFM2.5-2.6B rev-parse HEAD` was rejected by Git's dubious-ownership guard because the D: filesystem does not record ownership. No global `safe.directory` mutation was made; next check uses a scoped `git -c safe.directory=...` override. |
| 2026-08-06 23:18 CDT | Backend state | Added `AgentState` to `backend/schema.py` with reducer-backed messages, workspace root, project ID, pending approvals, hardware lane, loop bounds, tool outputs, and bounded error state. |
| 2026-08-06 23:18 CDT | Backend tools | Added `backend/tools.py` with `execute_python_sandbox`, workspace CWD, filtered environment, 45-second timeout, output caps, blocked process/network imports/calls, and graph-level approval gating. |
| 2026-08-06 23:18 CDT | Backend agent engine | Added `backend/agent_engine.py` with exact LFM identity/loopback policy, LangGraph agent↔ToolNode cycle, approval stop, loop bound, safe token/tool events, and reasoning-tag suppression. |
| 2026-08-06 23:18 CDT | Backend/API | Added `POST /api/chat/stream`, LFM readiness fields, exact LFM Coder provider handling in `backend/graph.py`, and `backend/.env.example` entries for a separate `:8082` runtime. |
| 2026-08-06 23:18 CDT | Frontend | Added LFM to `ModelProvider`, read-only exact model selection in `CoderNode`, route/readiness display in `Canvas.tsx`; Nanbeige remains PRIMARY. |
| 2026-08-06 23:18 CDT | Verification boundary | Code has not yet received the final consolidated syntax/typecheck/build/smoke batch. No LFM runtime has been started; `LFM2.5-2.6B` remains an explicit offline option until its endpoint advertises the exact model. |
| 2026-08-06 23:32 CDT | Scope / execution mode | Drew expanded M⊕ with selectable GPU/model profiles, optional use of both graphics cards, an integrated terminal, and easy upgrades. Drew explicitly stopped all subagent/delegated-worker use; implementation, integration, and acceptance are parent-only until he explicitly reverses that instruction. |
| 2026-08-06 23:46 CDT | Parent todo reconciliation | Re-read the branch-updated tracker and synchronized the active todo list: backend/Hermes/LFM reconciliation is in progress; ChatPanel/Planner wiring, named runtime profiles, governed terminal contract, and consolidated acceptance remain pending. Clone acquisition/identity verification is complete and no longer tracked as an open todo. |
| 2026-08-06 23:50 CDT | Parent hardening scope | Identified two integration defects for the current branch: unknown LFM tool calls must fail closed as `tool_not_allowlisted` rather than enter approval, and Hermes dispatch must use the configured workspace root rather than ambient process CWD. |
| 2026-08-06 23:50 CDT | Parent hardening implementation | Updated `backend/schema.py`, `backend/agent_engine.py`, and `backend/main.py` to add the bounded `tool_not_allowlisted` graph/SSE stop; updated `backend/hermes_adapter.py` to launch configured skill adapters from `WORKSPACE_ROOT`. No Nanbeige listener or runtime-profile files were changed. |
| 2026-08-06 23:50 CDT | Direct handoff lineage | Drew linked `@session:personal/20260806_232211_021cbe` as the active branch context; its clone receipt, Hermes adapter, Planner, and ChatPanel work are now reconciled against the live workspace rather than treated as an unverified plan. |
| 2026-08-06 23:57 CDT | Branch completion handoff | The linked branch reached its tool-call limit with the LFM/Hermes/Planner/ChatPanel implementation slice complete and explicitly handed consolidated clone/backend/frontend/Nanbeige/chat acceptance to the parent session. |
| 2026-08-06 23:58 CDT | Acceptance batch started | Parent-owned acceptance will cover the verified LFM clone, backend syntax/import, frontend typecheck/build, live Nanbeige health/graph SSE non-regression, and fail-closed LFM readiness/chat behavior. A real LFM tool-loop claim remains blocked until a separate exact-identity LFM endpoint is provisioned. |
| 2026-08-06 23:59 CDT | Live inspection launch requested | Drew asked to run the current working build from the linked branch session so he can inspect its actual progress. Parent confirmed the standalone workspace, backend venv, frontend dependencies, and launch scripts are present; ports `3000`, `8000`, `8080`, and `8082` were initially down. Next action is to start the verified shared Nanbeige route plus the current FastAPI and Next development services, then record fresh loopback receipts. |
| 2026-08-07 00:01 CDT | Frontend launch recovery | The first Next development process compiled and served four HTTP 200 requests, then exited after its generated `.next` cache lost `app-paths-manifest.json` and `routes-manifest.json`. Backend `:8000` and exact Nanbeige `:8080` remained healthy. Recovery is a bounded removal of the generated `.next` cache followed by one clean frontend restart; no source or dependency files are being changed. |
| 2026-08-06 23:59 CDT | Parent acceptance checks | LFM clone revision `403f92a2c4d78f2505f874b8b1b713cc0c9b9ae8`, clean `main...origin/main`, and all three LFS payloads passed. Backend `py_compile`/import passed; unknown tool routing returned `invalid` with `tool_not_allowlisted`. Frontend `tsc --noEmit` passed. `next build` hit an ENOENT `pages-manifest.json` race because the live Next server was using `.next`; build isolation/retry remains required. |
| 2026-08-06 23:59 CDT | Frontend build isolation | Added an optional `NEXT_DIST_DIR` override to `frontend/next.config.ts` while preserving the default `.next`; the acceptance build will use `.next-acceptance` so it cannot race the live `next start` process. |
| 2026-08-07 00:02 CDT | Live inspection ready | Opened `http://127.0.0.1:3000` for Drew. Fresh checks returned HTTP 200 from frontend `:3000`, backend `/api/health` on `:8000`, and exact-model `/v1/models` on `:8080`; health reports provider `nanbeige`, model `nanbeige4.2-3b-local`, `nanbeige_ready=true`, and `lfm_ready=false`. Browser activity reached `/api/chat/tools`, `/api/projects`, and `/api/execute` successfully. A second isolated dev launch correctly stopped on `EADDRINUSE` because the reconciled live frontend had already acquired port 3000; no extra frontend process was left running. |
| 2026-08-07 00:05 CDT | Ollama route discovery | Drew requested Ollama operation. Live `http://127.0.0.1:11434/api/tags` returned 200 and the installed Ollama CLI listed two models: the recent 5.4 GB `LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS:BF16` tag and the existing 19 GB Qwen3.6 tag. M⊕ already has an explicit Ollama provider contract; selecting the exact target model and deciding whether Ollama becomes the process-wide default or only a per-node option are the remaining scope decisions before restart and focused acceptance. |
| 2026-08-07 00:05 CDT | Ollama scope decision | Drew selected manual instructions only and explicitly prohibited changes or restarts for this request. No configuration, source, model, backend, frontend, or runtime lifecycle mutation is authorized; the documented path uses the existing per-Coder-node Ollama selector and exact installed model tag. |
| 2026-08-07 00:03 CDT | Isolated API acceptance | Disposable FastAPI `:8010` returned health 200 with Nanbeige ready and LFM not ready; `/v1/models` on `:8080` advertised only exact `nanbeige4.2-3b-local`; `/api/chat/tools` exposed seven governed tools with execution/dispatch approval flags; chat failed closed as `lfm_preflight_timeout`; Nanbeige Start→Coder SSE completed in 1.03 seconds. |
| 2026-08-07 00:04 CDT | Frontend SSE framing fix | Corrected `frontend/components/ChatPanel.tsx` to normalize CRLF SSE framing before splitting events. The first acceptance parser masked this client defect; isolated production build had already passed before this one-line fix, so typecheck/build must be rerun after the correction. |
| 2026-08-07 00:05 CDT | Parent process correction | The attempted exact-PID cleanup used `taskkill /T` and terminated the live Next process on `:3000` through the shared process tree. FastAPI/Nanbeige were not targeted. Frontend build/restart and post-recovery HTTP verification are now required; no live UI claim is made until those checks pass. |
| 2026-08-07 00:07 CDT | Frontend recovery build | After removing only generated `.next-acceptance`, the isolated `NEXT_DIST_DIR=.next-acceptance` typecheck and Next production build passed after the ChatPanel CRLF fix. The live Next server was restarted on `127.0.0.1:3000` and reached `Ready in 1.5s`; final HTTP smoke remains pending. |
| 2026-08-07 00:09 CDT | Acceptance harness correction | The first parent HTTP harness correctly reached the live services but assumed `/api/chat/tools` was a bare list; the endpoint returned an envelope object, so no product assertion completed. The parser was corrected for the retry. |
| 2026-08-07 00:10 CDT | Parent final loopback smoke | Frontend `:3000` returned HTTP 200 with the Local coding loop surface; backend `:8000/api/health` returned Nanbeige provider `nanbeige4.2-3b-local` and `lfm_ready=false`; `/api/chat/tools` returned seven governed tools; shared `:8080/v1/models` returned only exact `nanbeige4.2-3b-local`. |
| 2026-08-07 00:10 CDT | Changed-behavior acceptance | Safe sandbox output completed, `os.environ` access was rejected by the AST policy, Hermes catalog discovery returned 192 skills without credential/session access, and Start→Planner SSE completed `run_started → node → node → complete`. Disposable FastAPI `:8010` was stopped after acceptance. |
| 2026-08-07 00:10 CDT | Acceptance status | LFM clone identity, backend compile/import, frontend typecheck, isolated Next production build, Nanbeige non-regression, governed tool catalog, LFM fail-closed readiness, Planner execution, sandbox policy, and live loopback smoke are accepted. A real LFM tool-generation loop remains blocked until an exact `LFM2.5-2.6B` endpoint is separately provisioned. |
| 2026-08-07 00:10 CDT | Parent acceptance close | Independent retry against reconciled FastAPI `:8001` confirmed frontend `:3000` HTTP 200, exact Nanbeige model on `:8080`, seven governed tools, `lfm_preflight_timeout` fail-closed chat behavior, and real Nanbeige Start→Coder SSE completion in 1.96 seconds. Both parent-launched services remained running after smoke. |

## 1.3 Branch handoff and autonomy boundary — ACTIVE

- **Handoff source:** Drew branched this work from `@session:personal/20260806_214105_e60df0`. That session was consulted before continuing; its implementation receipts are treated as proposed history, while the files currently on disk remain authoritative.
- **Parent ownership:** This session owns final reconciliation, integration, acceptance, and tracker updates. Existing `schema.py`, `tools.py`, `agent_engine.py`, `graph.py`, `main.py`, and frontend LFM edits are preserved and will be reviewed in place rather than replaced wholesale.
- **Concurrent-work rule:** Keep Nanbeige/SearXNG on `127.0.0.1:8080` untouched. Do not start or repoint the unverified LFM runtime until its route is explicitly provisioned. Do not modify `DrewLocalVoice` or another project checkout.
- **Access policy:** The workspace will gain useful local tools through explicit, workspace-rooted, bounded, approval-aware capabilities—not unrestricted raw shell, credential access, arbitrary filesystem traversal, destructive GUI control, or unreviewed external sends. Tool names, approvals, limits, and failure classes must be visible in the chat/UI contract.
- **Next reconciliation:** Verify the clone with a scoped Git safe-directory override, inspect the existing backend/frontend seams, then complete one backend-to-chat vertical slice before expanding the tool library.
- **Execution-mode correction:** Drew explicitly prohibited further subagent/delegated-worker spawning on 2026-08-06 at 23:32 CDT. All remaining implementation and verification is owned by this primary session; prior worker receipts remain historical only.

### 1.4 Expanded implementation priority — 2026-08-06 23:30 CDT

Drew requested that we implement as much of the autonomous-workspace roadmap as is practical instead of choosing between one isolated feature. The execution order is now:

1. **Cyclic agent loop:** model → approved tool → result/error → model, with bounded loop counts and explicit stop states.
2. **Bounded local execution:** workspace-rooted inspection and execution tools, safe output caps, no credential inheritance, and per-tool approval.
3. **Chat control surface:** SSE tokens, tool metadata, approval prompts, and resumable approval requests.
4. **Hermes integration seam:** allowlisted skill/agent dispatch through a local adapter; no direct mutation of Hermes profiles or credentials from graph JSON.
5. **Planner/voice seam:** Buzz transcript → structured plan → coder prompt, keeping raw audio/transcript content out of logs and allowing typed input to remain the deterministic fallback.

The roadmap items are additive. Nanbeige remains the active default on the shared RTX 2070 SUPER listener; LFM remains an explicit opt-in agent route and is not silently substituted.

### 1.5 GPU, terminal, and upgrade expansion — 2026-08-06 23:32 CDT

- **GPU/model selection:** Add named runtime profiles that bind an approved local model and exact alias to one of: RTX 5060 Ti only, RTX 2070 SUPER only, or both GPUs. The UI must show physical GPU name/index/UUID, backend/device mode, context, slots, and readiness before activation.
- **Both-GPU options:** Treat two meanings as distinct selectable profiles: one compatible model split across both GPUs, or two independent local model servers with one assigned to each GPU. Never infer one mode from the other, add VRAM numbers as if they were shared memory, or silently involve the second card.
- **Current baseline:** Preserve the verified shared Nanbeige route on RTX 2070 SUPER until a different profile passes artifact, listener, exact-alias, positive target-GPU, negative foreign-GPU, generation, and rollback gates.
- **Integrated terminal:** Add a visible terminal panel with workspace-rooted sessions, explicit command lifecycle, bounded output, cancel/kill controls, filtered environment, metadata-safe history, and approval gates for operations outside the normal workspace policy. Do not make graph JSON an arbitrary-shell escape hatch.
- **Upgrade Center:** Inventory the M⊕ app, models, and runtimes; show installed/pinned/candidate versions; perform disk/toolchain preflight; use background progress; verify checksums; preserve backups; and expose one-step rollback. Downloads, builds, service changes, and external network actions remain explicit actions rather than silent updates.
- **Open design decisions:** Drew will confirm whether the default terminal is fully interactive ConPTY or a bounded command/session console, and whether “both GPUs” prioritizes split-model inference, independent per-GPU servers, or both modes in the first release.

### 1.6 Markdown stewardship and branch synchronization — ACTIVE

- **Canonical Markdown:** `PROJECT_TRACKER.md` is the authoritative append-preserving record for scope, decisions, implementation, handoffs, blockers, and verification. It must be re-read from disk before any targeted edit because sibling branches may update it between turns.
- **Operator documentation:** `README.md` is the user-facing setup/run guide. It may be edited when behavior or commands change, but historical receipts belong in the tracker rather than being replaced in the README.
- **Branch notes:** Other branches may append sections or rows. Preserve unfamiliar entries, retain their timestamps/ownership labels, and reconcile conflicts by adding a newer decision or correction instead of deleting the older record.
- **Generated/vendor Markdown:** Markdown under `backend/.venv/`, `frontend/node_modules/`, caches, and third-party artifacts is inventory-only and is not part of the project documentation surface. Do not edit it or copy it into the tracker.
- **Edit protocol:** Before a Markdown mutation: inventory the relevant project Markdown, read the whole target when feasible, patch a unique anchor, verify the resulting section, and record the changed path plus branch/handoff context. Never overwrite the tracker from a stale partial read.
- **Cross-branch receipts:** Every code or scope change gets one append-only tracker receipt naming the workstream, files/area, owner, current state, and verification boundary. A receipt is not accepted as proof until the parent session re-reads the settled file or runs a parent-owned check.
- **Current inventory (2026-08-06 23:33 CDT):** project-owned Markdown is `PROJECT_TRACKER.md` and `README.md`; dependency/vendor trees contain additional Markdown and remain excluded from edits.

## 2. Product goal

Build a local-first visual node IDE for composing coding and input/output workflows. Drew should be able to drag nodes onto a canvas, connect them, configure each node, save/load projects, run the graph, inspect bounded run events, and trigger configured local agents as reactions.

## 3. Fixed product requirements

### User experience

- Dark, usable local browser GUI.
- Drag-and-drop React Flow canvas.
- Node palette for Start, Buzz transcription, Coder/model, File I/O, Task tracker, and Agent Reaction.
- Inline node configuration plus a clear run/output/event surface.
- Runtime Control surface for model, endpoint profile, GPU placement, context, slots, and live readiness.
- Integrated terminal surface with visible process/session lifecycle and approval state.
- Upgrade Center with inventory, preflight, progress, backup, and rollback receipts.
- Save and load named projects.
- Validate the graph before execution.
- Preserve graph definitions as React Flow-compatible `nodes` and `edges` JSON.

### Runtime

- Target OS: Windows 10/11.
- Frontend: Next.js 15, React, `@xyflow/react`.
- Backend: FastAPI, LangGraph, SQLite, SQLAlchemy, Pydantic.
- Audio path: Buzz CLI/Whisper on the RTX 2070 SUPER.
- LLM path: exact local providers use named runtime profiles. The verified default is Nanbeige on the shared RTX 2070 SUPER listener; selectable profiles may use RTX 5060 Ti, RTX 2070 SUPER, or both cards after compatibility and placement validation.
- Local agent reactions are allowlisted/configured; a canvas node must never execute arbitrary shell text.
- No cloud transcription, telemetry, implicit network fallback, or secret logging.
- Do not log transcript text, captured audio, clipboard contents, credentials, file contents, or target-field contents. Run events contain node IDs, types, statuses, bounded timing, and failure classes only.

## 4. Model decision ledger

### Drew's correction

- **Rejected:** Qwen 2.5 Coder. It must not appear as a default or fallback in the workspace.
- **Preferred direction:** Use a strong model already on the machine, or use MiniMax-M3.
- **Selected 2026-08-06:** Upgrade the workspace's local route to exact `Nanbeige/Nanbeige4.2-3B`, reusing the already verified D:-hosted Q4_K_M artifact and publisher runtime. No second model download is needed.
- **Verified baseline topology:** M⊕ and SearXNG currently share the existing RTX 2070 SUPER listener at `127.0.0.1:8080`, alias `nanbeige4.2-3b-local`, with two 20,480-token slots (40,960 total context). This remains the safe default while selectable single-GPU and dual-GPU profiles are added.
- **Expanded topology requirement 2026-08-06:** M⊕ must no longer hard-code one GPU arrangement as the only option. Approved runtime profiles will expose RTX 5060 Ti only, RTX 2070 SUPER only, compatible one-model/two-GPU splitting, and optionally independent per-GPU model servers.

### Verified discovery

- Ollama executable exists at `C:\Users\Drew\AppData\Local\Programs\Ollama\ollama.exe`.
- Local Ollama manifests contain one visible model:
  `hf.co/DavidAU/Qwen3.6-27B-Fable-Fusion-711-Uncensored-Heretic-NM-DAU-NEO-MAX-MTP-GGUF/Q4_K_M`.
- The Ollama API probe at `http://127.0.0.1:11434/api/tags` timed out.
- A bounded `ollama list` probe found an existing Ollama instance but timed out waiting for the server; no model readiness has been claimed.
- `buzz` is not available on the current MSYS PATH probe.
- Hermes `config get model` for the active personal profile reports `gpt-5.6-luna` / `openai-codex`.
- Hermes configuration also contains a `MiniMax-M3` / `minimax-oauth` route in its model settings, but the standalone FastAPI app cannot safely inherit Hermes OAuth credentials automatically.

### Current implementation decision

The backend is provider-agnostic with an exact local default:

- `WORKSPACE_MODEL_PROVIDER=nanbeige` selects the shared loopback-only listener at `127.0.0.1:8080` and requires alias `nanbeige4.2-3b-local`.
- `WORKSPACE_MODEL_PROVIDER=minimax` selects MiniMax-M3 through an explicitly configured OpenAI-compatible endpoint and process environment key.
- `WORKSPACE_MODEL_PROVIDER=ollama` selects the installed local Ollama model through the local Ollama endpoint.
- No credential is copied from Hermes configuration into the project; no route silently falls back to another provider.
- **Selected:** Nanbeige4.2-3B for M⊕ and SearXNG on the shared RTX 2070 SUPER listener. MiniMax-M3 and Ollama remain explicit alternates.

## 5. Architecture decisions

| ID | Decision | Reason / consequence |
|---|---|---|
| D-01 | Standalone sibling workspace | Keeps the dirty `DrewLocalVoice` work isolated and lets this become an independent node IDE. |
| D-02 | Browser edits graph JSON; backend owns validation/execution | Prevents UI-only assumptions from bypassing runtime safety. |
| D-03 | Compile graph JSON into LangGraph `StateGraph` per run | Provides a real execution boundary while preserving the React Flow format. |
| D-04 | MVP execution is linear | Multiple outputs/branching are rejected for now so ordering and state handoff are deterministic. The edge format remains extensible for later branching. |
| D-05 | Local paths are constrained to `WORKSPACE_ROOT` | Prevents a graph from reading/writing arbitrary Windows paths. |
| D-06 | Agent commands are allowlisted through configuration | Prevents arbitrary shell execution from node data. Prompt input is sent through stdin rather than command-line arguments. |
| D-07 | Provider/model selection is explicit | Qwen 2.5 Coder is removed; Nanbeige, MiniMax, Ollama, and approved local additions are separate routes with separate readiness checks. |
| D-08 | Metadata-only run events | The GUI can show progress/failures without persisting transcript, code, or file content in logs. |
| D-09 | No device/microphone/native-window acceptance in first smoke | Synthetic graph input is sufficient for the first software integration check; real Buzz/GPU acceptance is separate. |
| D-10 | Hardware placement uses named profiles | Model/alias/runtime/GPU/context/slot settings are validated as one unit; canvas JSON cannot inject arbitrary device or server arguments. |
| D-11 | Dual-GPU modes are explicit | Split-model inference and independent per-GPU servers are different profiles with different acceptance evidence. |
| D-12 | Terminal is a governed execution surface | It is workspace-rooted, lifecycle-visible, output-bounded, cancellable, secret-safe, and approval-gated rather than an unrestricted graph node. |
| D-13 | Upgrades are transactional | Inventory, preflight, checksums, backup, activation, verification, and rollback are one receipted workflow; no silent auto-update. |

## 6. Roadmap and acceptance gates

### Milestone 0 — Scope and workspace boundary — COMPLETE

- [x] Interpret the request as a standalone `ai-workspace` project.
- [x] Preserve the existing `DrewLocalVoice` repository untouched.
- [x] Create this canonical tracker before implementation.
- [x] Capture Windows, GPU, stack, local-first, and agent-reaction constraints.

**Gate:** New files resolve inside the sibling workspace; no edits land in `DrewLocalVoice`.

### Milestone 1 — Model/provider route — NANBEIGE LIVE / VERIFIED

- [x] Remove Qwen 2.5 Coder from the project environment example and health default.
- [x] Add a MiniMax-compatible dependency route (`langchain-openai`).
- [x] Record the installed local Ollama model and the current Ollama readiness problem.
- [x] Finish the provider abstraction in `backend/graph.py` with exact Nanbeige as the selected default route; MiniMax and Ollama remain explicit alternates.
- [x] Add frontend model/provider controls and clear readiness diagnostics; type/build verification passed.
- [x] Add exact Nanbeige alias/endpoint enforcement and provider readiness diagnostics.
- [x] Complete a real local model smoke through the shared listener.

**Gate:** No executable path contains `qwen2.5-coder`; coder nodes expose provider/model explicitly; missing providers fail closed with a useful error.

### Milestone 2 — Backend workflow engine — CORE VERIFIED

Files:

- `backend/main.py`
- `backend/graph.py`
- `backend/database.py`
- `backend/schema.py`
- `backend/requirements.txt`
- `backend/.env.example`

Planned capabilities:

- [x] SQLite project persistence.
- [x] SQLite task persistence for Task nodes.
- [x] Pydantic graph/project/run payloads.
- [x] `AgentState` includes the requested `messages` and `project_tasks` fields plus execution values.
- [x] FastAPI health, project save/load/list, validation, run, agent list, and task list routes.
- [x] Graph validation for one Start node, missing edges, cycles, unreachable nodes, and linear-only execution.
- [x] Safe workspace-root path resolution.
- [x] Buzz adapter shape with timeout and failure classes.
- [x] Allowlisted local-agent adapter shape.
- [x] Repair the failed `graph.py` provider patch; `main.py` and `graph.py` now share provider constants and dispatch.
- [x] Add `/api/execute` SSE streaming over `StateGraph.stream()` for real-time node events; live SSE smoke passed.
- [x] Add explicit bounded response handling for provider failures and run-level diagnostics.
- [x] Run consolidated backend syntax/import/API smoke; a standalone unit-test suite remains future hardening.

**Gate:** Backend imports cleanly, `/api/health` responds, a Start-only graph validates/runs, a safe file graph works, and unavailable Buzz/model/agent routes return bounded diagnostics.

### Milestone 2A — Cyclic agent foundation — IMPLEMENTED / VERIFICATION PENDING

- [x] Persistent `AgentState` carries reducer-backed conversation messages, workspace/project context, approvals, hardware lane, loop bounds, tool outputs, and bounded failure state.
- [x] Opt-in LFM agent performs exact `/v1/models` preflight before each generation and fails closed on endpoint/model mismatch.
- [x] LangGraph cycles `agent → approved tools → tool-output capture → agent` with explicit approval and loop-limit terminal states.
- [x] Workspace tool registry includes bounded file listing, text reads, Python AST inspection, and approval-gated Python computation.
- [x] Hermes seam includes read-only local `SKILL.md` discovery/reading plus approval-gated dispatch through an explicitly configured command map; credentials, sessions, and Hermes config are not exposed.
- [ ] Add persistent checkpoint/time-travel resume rather than the current approval resubmission contract.
- [ ] Run the real LFM endpoint/tool-call acceptance; no LFM listener is started by this change.

**Gate:** Exact LFM preflight, read-only tool calls, approval pause, bounded execution, loop-limit stop, and SSE framing must pass together without touching the Nanbeige listener.

### Milestone 3 — Frontend visual canvas — BUILD / HTTP VERIFIED

Files planned:

- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/next-env.d.ts`
- `frontend/next.config.ts`
- `frontend/postcss.config.mjs`
- `frontend/tailwind.config.ts`
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/components/Canvas.tsx`
- `frontend/components/nodes/*.tsx`

Capabilities:

- [x] Node data contracts and node defaults.
- [x] Start, Buzz, Coder, File, Task, and Agent node components with safe editable data.
- [x] Planner node converts Buzz/typed intent into a structured plan before the coder node.
- [x] Palette-to-canvas node creation.
- [x] React Flow dragging, connecting, selecting, deleting, and viewport controls.
- [x] Provider/model selection on Coder node (shared Nanbeige default; MiniMax/Ollama explicit alternates).
- [x] Save/load controls and project name.
- [x] Input box, validate/run controls, output panel, and metadata-only event list.
- [x] Health/provider readiness indicator.
- [x] Serialization strips UI callbacks before saving.
- [x] Floating terminal overlay consumes `/api/execute` SSE events.
- [x] Chat panel consumes `/api/chat/stream`, displays safe token/tool metadata, and exposes one-turn approval controls.

**Gate:** UI opens against the local API, a user can build a valid Start → Coder graph, save/load it, run it, and see output or a clear provider diagnostic.

### Milestone 4 — Local integrations and reactions — IN PROGRESS

- [ ] Confirm Buzz executable/service contract on this Windows host.
- [ ] Keep Buzz/audio execution bounded while Nanbeige shares the RTX 2070 SUPER listener.
- [x] Run the shared RTX 2070 Nanbeige M⊕ workflow acceptance without changing unrelated local services.
- [ ] Define the first approved local agent adapter (Hermes, Codex, or another configured runner).
- [ ] Add a visible configured-agent list; unknown targets remain unavailable.
- [ ] Add run lifecycle state for background agent launches without exposing prompt contents in process arguments or logs.

**Gate:** One explicitly configured local agent can be launched by an Agent Reaction node; unconfigured targets fail closed; the GUI reports only bounded metadata.

### Milestone 5 — Documentation and operator workflow — COMPLETE

- [x] Root `README.md` with Windows setup/start commands.
- [x] Backend venv and frontend install instructions.
- [x] `.env` handling that never commits credentials.
- [x] GPU ownership and model selection notes.
- [x] Workflow examples and first-run guidance.
- [x] Troubleshooting for Ollama timeout, missing Buzz, CORS, and backend startup.

**Gate:** Drew can start both processes from the README without guessing paths or model defaults.

### Milestone 6 — Consolidated verification and smoke — CORE COMPLETE

Run only after Milestones 1–5 are assembled:

- [x] Backend syntax/import check.
- [x] Backend focused API checks: health, save, load, validate, synchronous run, and SSE run.
- [x] Frontend TypeScript and production build check.
- [x] Start FastAPI and Next.js locally on ports 8000 and 3000.
- [x] HTTP/API smoke: health → save → load → validate → run Start-only graph, plus frontend page response/title.
- [x] Confirm Qwen 2.5 Coder is absent from executable defaults/fallbacks.
- [x] Confirm all project mutations stayed in the standalone sibling workspace; `DrewLocalVoice` was inspected read-only.
- [x] Keep real Buzz/microphone/model/GPU acceptance separate unless explicitly authorized.

**Gate:** Working artifact plus real tool output, not just written files.

### Milestone 7 — Runtime and hardware selector — IN PROGRESS

- [ ] Inventory physical GPU index/name/UUID/VRAM and approved local model/runtime artifacts without exposing secrets or process command lines.
- [ ] Define versioned runtime-profile schema for model, exact alias, executable, endpoint, GPU mask/device/split mode, context, slots, and limits.
- [ ] Support profiles for RTX 5060 Ti only, RTX 2070 SUPER only, one compatible model split across both GPUs, and optionally one independent server per GPU.
- [ ] Add Runtime Control UI for selecting, preflighting, starting, stopping, and inspecting profiles; preserve the currently verified route until cutover succeeds.
- [ ] Require live exact-alias, executable ownership, target/foreign GPU placement, bounded generation, and rollback receipts per activated profile.

**Gate:** Drew can select an approved model/GPU profile, see the effective settings before launch, activate it without port/process ambiguity, and return to the prior verified profile in one controlled action.

### Milestone 8 — Integrated terminal — PLANNED

- [ ] Select a Windows terminal contract: interactive ConPTY versus bounded command/session console for the first release.
- [ ] Add terminal session create/input/resize/cancel/close APIs and streamed output with explicit process ownership.
- [ ] Root sessions in the project workspace, filter inherited credentials/environment, cap retained output, and keep commands/results out of metadata-only workflow logs.
- [ ] Add visible approval and policy boundaries for network, destructive, external, credential, or out-of-workspace operations.

**Gate:** A user can open, use, cancel, and close a local workspace terminal from M⊕ without focus theft, orphaned processes, secret leakage, or graph-driven arbitrary command execution.

### Milestone 9 — Upgrade Center — PLANNED

- [ ] Inventory M⊕ app dependencies, local model revisions/artifact hashes, and runtime source/binary revisions.
- [ ] Show installed, pinned, and candidate versions plus disk/toolchain/GPU preflight before mutation.
- [ ] Run approved downloads/builds in tracked background jobs with progress and bounded logs on the intended drive.
- [ ] Verify artifact checksums and runtime smoke before activation; retain the previous app/runtime/profile for rollback.
- [ ] Provide status, cancel, retry, activate, and one-step rollback controls without silently touching SearXNG or another live project.

**Gate:** An approved upgrade can be prepared, verified, activated, and rolled back from M⊕ with explicit receipts and no credential exposure or unapproved service mutation.

## 7. Current implementation inventory

### Created

- `PROJECT_TRACKER.md`
- `MARKDOWN_INDEX.md`
- `backend/__init__.py`
- `backend/agent_engine.py`
- `backend/tools.py`
- `backend/hermes_adapter.py`
- `backend/requirements.txt`
- `backend/database.py`
- `backend/schema.py`
- `backend/graph.py`
- `backend/main.py`
- `backend/.env.example`
- `frontend/app/globals.css`
- `frontend/components/ChatPanel.tsx`
- `frontend/components/Canvas.tsx`
- `frontend/components/nodes/*.tsx`
- `frontend/components/nodes/PlannerNode.tsx`
- `frontend/package.json` and `frontend/package-lock.json`
- `frontend/postcss.config.mjs` and `frontend/tailwind.config.ts`
- `README.md`
- `.gitignore`
- `START_BACKEND.cmd`
- `START_FRONTEND.cmd`
- Preserved superseded runtime artifacts: `D:\AI\Runtimes\nanbeige-llama.cpp\build-sm120\` and `D:\AI\Runtimes\nanbeige-workspace-launcher\{launch.config.json,Start-NanbeigeWorkspace.ps1,Status-NanbeigeWorkspace.ps1,Stop-NanbeigeWorkspace.ps1}`. They are not on the active route; the shared SearXNG SM75 launcher remains authoritative.

### Updated after model correction

- `backend/requirements.txt` includes `langchain-openai`.
- `backend/graph.py` now includes a first-class exact-alias Nanbeige provider: environment-only loopback `/v1` endpoint, proxy inheritance disabled, `/v1/models` preflight, bounded template/generation settings, and provider-specific failure classes. MiniMax and Ollama remain explicit non-fallback alternatives.
- `backend/.env.example`, ignored `backend/.env`, and the Coder node select exact `nanbeige4.2-3b-local` at `127.0.0.1:8080/v1`; the old long Ollama/Qwen model is no longer a UI or example default.
- `backend/main.py` health output reports the selected Nanbeige, MiniMax, and Ollama routes.
- `backend/main.py` exposes `/api/execute` as an SSE response over the graph execution worker; the live Start-only SSE smoke passed.
- API workflow failures now expose bounded `detail` plus `failure_class`, and the Canvas displays that diagnostic without raw subprocess output.
- Agent Reaction now applies its configured prompt prefix before sending workflow input through stdin to the allowlisted command.
- Frontend package/config files, app shell, polished local stylesheet, node types, node frame, six node components, and `Canvas.tsx` are created.
- Frontend manifest declares `tailwindcss`, `postcss`, and `autoprefixer`; Next.js is pinned to verified 15.5.23 and has a local tracing root.
- Frontend node inputs/selects/textareas now carry React Flow's `nodrag` class so configuration controls remain interactive while nodes stay draggable.
- `backend/agent_engine.py` now preflights the exact opt-in LFM model before every generation, binds the governed workspace/Hermes tools, cycles through tool results, and emits bounded token/tool/approval/loop-limit events.
- `backend/tools.py` now exposes workspace-relative listing, bounded text reads, Python AST inspection, and a stricter allowlisted-import computation tool; tool catalog metadata identifies approval requirements.
- `backend/hermes_adapter.py` adds local SKILL.md discovery/reading and an explicitly configured stdin-based dispatch seam without profile credentials or session access.
- `frontend/components/ChatPanel.tsx`, `PlannerNode.tsx`, and the Canvas palette/stylesheet add the chat control surface and Buzz/typed-intent Planner → Coder path.

### Known incomplete / deferred state

- The exact MiniMax-compatible endpoint and API key remain unconfigured because MiniMax is optional. A live M⊕ Nanbeige Coder-node call passed through the shared listener.
- The Ollama server was not ready, Buzz was absent from PATH, and no allowlisted agent command was configured; those integrations remain fail-closed.
- Real shared Nanbeige model/GPU acceptance passed. Buzz, microphone, and Agent Reaction acceptance remain separate and unrun.
- `npm audit --omit=dev` reports three high transitive PostCSS/sharp advisories in the newest Next 15 line; npm's automated fix requires the breaking Next 16 line, so it was not forced.
- Independent-review fixes are now verified: server-side Qwen 2.5 rejection, environment-only provider endpoints, bounded model calls, Buzz-size allowlist, safe graph IDs, tested LangGraph/LangChain pins, correct compiled-graph annotation, automatic ignored `.env` loading, frontend topology/load guards, and robust/correlated SSE framing.
- Deferred hardening: cancelling a synchronous worker after an SSE client disconnects, replacing the cross-thread event list with a queue, full SSE replay, and eliminating symlink/TOCTOU races around external Buzz/file writes.
- The Python tool is a bounded same-user subprocess policy layer, not a security boundary equivalent to a VM/container; destructive or unrestricted shell/GUI/browser tools remain intentionally unimplemented.
- The chat approval continuation currently resubmits the prompt with an approved tool list; durable LangGraph checkpoints/time-travel resume remain future work.

## 8. Worker orchestration log

- Three read-only research lanes were dispatched:
  1. dependency/version compatibility;
  2. canvas/node UX and graph contract;
  3. backend safety, GPU separation, and agent execution.
- The UX/data-contract lane returned a usable v0.1 design: typed acyclic graph, Start → Buzz → Coder → File/Task/Agent, bounded value mappings, and no arbitrary shell/collaboration/cloud features in the first slice.
- The dependency-compatibility and backend-audit lanes were interrupted while waiting for model responses; no execution or compatibility claim was accepted from them.
- The original three-lane batch completed on 2026-08-06; its partial/usable status is preserved rather than treated as a clean pass.
- No worker is authorized to modify this workspace without a disjoint ownership scope and parent verification.
- The write-capable integration worker completed read-only inspection but was blocked by a stale delegation allowlist that only permitted unrelated `DrewLocalVoice` tool/test paths; it changed no files. Parent-owned fallback is authorized for its five disjoint files.
- A fifth read-only integration-review worker completed an interrupted handoff after reporting concrete risks. Its P0 React Flow generic mismatch was reproduced by TypeScript, fixed in `Canvas.tsx`, and then proven by a clean typecheck/build; remaining hardening items are preserved above.
- Nanbeige cross-project upgrade lanes dispatched 2026-08-06:
  - `deleg_267615b2`: read-only SM120/publisher-runtime build audit; no branch/worktree and no write authority.
  - `deleg_65e1c5e1`: read-only M⊕ Nanbeige provider-contract review; no branch/worktree and no write authority.
  - `deleg_9e8a9449`: read-only SearXNG restore/acceptance review; interrupted before a final handoff and changed nothing.
  - `deleg_8c060871`: replacement read-only SearXNG restore/acceptance lane; no branch/worktree and no write authority.
- Parent ownership for this upgrade: D:-hosted SM120 build/launcher artifacts, all M⊕ source/config/docs edits, both live listener lifecycles, integration, and final acceptance. Worker findings are advisory until reconciled against parent tool output.
- All four Nanbeige audit attempts ended interrupted before a usable final handoff; transcript review found no patch/write operation. Parent independently discovered and implemented the required paths.
- Parallel parent launcher writes emitted a sibling-write warning, but full active-lane transcript review found zero delegated writes; the current config/start/status/stop files were read back and remain parent-owned.
- `README.md` changed concurrently between two parent reads. Active Nanbeige lane transcripts contained no write operation, so no worker mutation is claimed. Parent preserved the useful exact-route text, removed the stale long Ollama/Qwen default, and reconciled run/verification instructions.
- Drew requires continuous parent awareness of every active branch/worker. The parent must keep scope, status, findings, branch/worktree, changed files, blockers, and integration state synchronized here before accepting branch output.
- Replacement live-review lanes dispatched after the first interrupted set:
  - `deleg_bcdc3c8e`: read-only P0/P1 review of the M⊕ backend/frontend Nanbeige source changes; no branch/worktree and no write authority.
  - `deleg_3b859aa0`: read-only P0/P1 review of the D:-hosted SM120 launcher/config set; no branch/worktree and no write authority.
  - `deleg_a068d481`: read-only exact SearXNG restore/status/synthesis/rollback command handoff; no branch/worktree and no write authority.
- Parent will monitor the three live transcripts and reconcile each finding against current files/tool output before integration.
- Replacement-lane outcomes:
  - `deleg_bcdc3c8e` ended interrupted after reading backend/docs and locating corrected frontend paths; it produced no final review and changed no files.
  - `deleg_3b859aa0` ended interrupted after reading all four launcher/config files; it produced no final review and changed no files.
  - `deleg_a068d481` ended interrupted after locating the canonical SearXNG tracker, crawler, launch config, and Start/Status scripts; it produced no final command handoff and changed no files.
- No further worker replenishment is warranted for this slice: the remaining work is serial parent-owned build completion, process lifecycle, integration, and live acceptance. Parent verification is authoritative.

## 9. Verification receipts

| Time | Check | Result |
|---|---|---|
| 2026-08-06 20:16 CDT | Ollama executable/path discovery | Executable found; server/API probe timed out. |
| 2026-08-06 20:16 CDT | Local Ollama manifest discovery | One Qwen3.6-based manifest found; readiness not claimed. |
| 2026-08-06 20:16 CDT | Buzz PATH probe | `buzz` not found on current MSYS PATH. |
| 2026-08-06 20:16 CDT | Active Hermes model query | Personal profile reported `gpt-5.6-luna` / `openai-codex`; MiniMax-M3 route exists in config settings but is not automatically imported. |
| 2026-08-06 20:55 CDT | Isolated backend dependency install | Initial venv inherited Hermes `PYTHONPATH`; rerun with `env -u PYTHONPATH` installed/imported packages from `backend/.venv` only. |
| 2026-08-06 20:56 CDT | Backend syntax/import | `py_compile` passed; app imported as `M⊕ AI Visual Workspace API`, provider `minimax`, model `MiniMax-M3`. |
| 2026-08-06 20:57 CDT | FastAPI/API/SSE smoke | Health/save/load/validate/synchronous Start-only run returned 200; SSE returned `run_started`, `node`, `complete`. |
| 2026-08-06 21:01 CDT | Frontend TypeScript | Initial React Flow generic failure was corrected; `npm run typecheck` then passed. |
| 2026-08-06 21:03 CDT | Next.js production build | Next 15.5.23 build passed; local `outputFileTracingRoot` removed the unrelated home-lockfile warning. |
| 2026-08-06 21:04 CDT | Loopback HTTP smoke | FastAPI `/api/health` and Next `/` returned 200; rendered HTML contained `M⊕ AI Visual Workspace`. |
| 2026-08-06 21:05 CDT | Executable source safety scan | No `qwen2.5-coder`/Qwen 2.5 executable hits; no source credential pattern hit. Package-lock metadata was the only broad `sk-` substring match. |
| 2026-08-06 21:07 CDT | Running-process check | FastAPI remains live on 127.0.0.1:8000; Next remains live on 127.0.0.1:3000. |
| 2026-08-06 21:17 CDT | Audit-focused backend checks | Pinned install/syntax passed; safe IDs, Qwen 2.5 rejection, environment-only endpoint, Buzz-size allowlist, and compiled graph type all passed. |
| 2026-08-06 21:18 CDT | Hardened frontend type/build | Strict TypeScript and Next 15.5.23 production build passed with topology/load/SSE guards. |
| 2026-08-06 21:20 CDT | Fresh hardened live smoke | Health 200; reserved ID 422; Qwen 2.5 API 502 `model_policy_rejected`; SSE emitted three correlated frames with `run_id`; frontend 200/title present. |
| 2026-08-06 22:11 CDT | SM120 configure receipt | Clean publisher checkout at pinned commit configured successfully with CUDA 12.8; CMake rewrote architecture 120 to native `120a` and generated `build-sm120` on D:. The narrowed Release build was later canceled when Drew selected the shared RTX 2070 route; no SM120 completion is claimed. |
| 2026-08-06 22:33 CDT | Shared listener preflight | `Status-NanbeigeDeepResearch.ps1` reported healthy `nanbeige4.2-3b-local`, exact identity, physical GPU index 1 / RTX 2070 SUPER, `parallel=2`, and no foreign GPU UUIDs. `/v1/models` and `/props` matched the alias, Q4_K_M artifact, and two 20,480-token slots. |
| 2026-08-06 22:33 CDT | Artifact integrity | `Nanbeige4.2-3B-Q4_K_M.gguf` exists at the D:-hosted path, 2,574,807,986 bytes; SHA-256 matched `18a659d0c1744e5bd2f4b8da55e0dcabf42ec7f005b74ec8eb66593b3380f958`. |
| 2026-08-06 22:33 CDT | Backend/frontend final checks | Backend `py_compile`, frontend `npm run typecheck`, and Next 15.5.23 `npm run build` passed. FastAPI `/api/health` and Next `/` returned HTTP 200; health selected Nanbeige and reported `nanbeige_ready=true`. |
| 2026-08-06 22:33 CDT | M⊕ real model workflow | Start→Coder graph validation returned 200; `/api/execute` returned `run_started`, two node events, and `complete` with four unique SSE IDs, non-empty output, no error event, and 6.23-second elapsed time. |
| 2026-08-06 22:33 CDT | SearXNG GPU synthesis | Local SearXNG discovery produced 10 discoveries / 4 attempted pages / 2 retained documents with zero errors; Nanbeige synthesis at `127.0.0.1:8080/v1` returned `ok` in 12.25 seconds with valid `S1` citation and no unknown citations. |
| 2026-08-06 22:33 CDT | Runtime liveness | FastAPI `:8000`, Next `:3000`, SearXNG `:8888`, and shared Nanbeige `:8080` remained live after acceptance. |
| 2026-08-06 23:33 CDT | Markdown stewardship | Created `MARKDOWN_INDEX.md` as the document-control index. Project-owned Markdown is now explicitly classified as `PROJECT_TRACKER.md` (canonical), `README.md` (operator guide), and `MARKDOWN_INDEX.md` (coordination rules); dependency/vendor Markdown remains excluded. |
| 2026-08-06 23:40 CDT | Agentic slice assembly | Added the cyclic LFM engine hardening, governed workspace/Hermes tool registry, Planner node, and chat panel. Verification is intentionally deferred to one consolidated backend/frontend/route acceptance; no live listener was repointed or started. |

## 10. Change log

- **2026-08-06:** Created the standalone workspace tracker before implementation.
- **2026-08-06:** Established the sibling workspace boundary so existing `DrewLocalVoice` changes remain untouched.
- **2026-08-06:** Scaffolded the backend package, SQLite schema, graph compiler shape, FastAPI routes, requirements, and environment example.
- **2026-08-06:** Drew rejected Qwen 2.5 Coder; recorded the correction as a durable model preference and removed it from the environment example/health default.
- **2026-08-06:** Discovered the installed Ollama executable and Qwen3.6 manifest, but the Ollama API was not ready; recorded this as evidence, not as a successful model selection.
- **2026-08-06:** Added the explicit MiniMax-M3 provider route shape without copying credentials from Hermes.
- **2026-08-06:** A grouped provider patch was rejected before mutation; the tracker records the resulting incomplete state so the next edit repairs the root mismatch rather than hiding it.
- **2026-08-06 20:20 CDT:** Drew selected MiniMax-M3 through an explicit OpenAI-compatible endpoint as the first live default; API credentials remain environment-only.
- **2026-08-06:** Repaired `backend/graph.py` with MiniMax-M3/OpenAI-compatible dispatch, explicit Ollama alternate dispatch, and no Qwen 2.5 Coder fallback.
- **2026-08-06:** Scaffolded the Next.js app shell, package/config files, shared node data contract, node frame, and Start/Buzz/Coder/File/Task/Agent components.
- **2026-08-06:** Drew restated the Phase 2 graph-adapter, Phase 3 canvas/SSE, and Phase 4 port/verification requirements; promoted them into the active implementation delta.
- **2026-08-06:** Wrote the React Flow Canvas, palette/drop handling, save/load/validate/run controls, provider readiness surface, and SSE floating terminal consumer; verification remains pending.
- **2026-08-06:** Aligned `AgentState` with the master prompt and routed the JSON run/SSE paths through real LangGraph `.stream()` updates.
- **2026-08-06:** Dispatched a write-capable worker for the disjoint CSS, README, `.gitignore`, and Windows launcher slice.
- **2026-08-06:** Reconciled the completed worker batch: adopted the typed-acyclic v0.1 UX findings, rejected interrupted-lane claims, and dispatched a fifth read-only integration reviewer.
- **2026-08-06:** The integration writer was blocked by a stale workspace allowlist; no child mutation was accepted, and the parent took ownership of the CSS/docs/launcher fallback.
- **2026-08-06:** Added Tailwind/PostCSS manifest and config files to satisfy the frontend setup requirement without taking ownership of the worker's stylesheet.
- **2026-08-06:** Aligned graph edge compilation literally with the master adapter contract: each submitted edge is added directly, terminal nodes connect to `END`.
- **2026-08-06:** Normalized workflow failure responses and updated the SSE client to display provider/agent/Buzz failure classes safely.
- **2026-08-06:** Wired the Agent Reaction prompt prefix into the backend without putting prompt content into process arguments.
- **2026-08-06:** Marked all editable node controls as `nodrag` so React Flow does not steal input gestures for canvas movement.
- **2026-08-06:** Parent fallback wrote the blocked worker's CSS, README, `.gitignore`, and two Windows launchers; the child changed no files.
- **2026-08-06:** Installed isolated backend/frontend dependencies, corrected inherited Hermes `PYTHONPATH`, and upgraded Next from vulnerable 15.2.4 to the latest Next 15.5.23 line.
- **2026-08-06:** Fixed React Flow's node/instance generics after the first TypeScript pass, then completed clean typecheck and production build.
- **2026-08-06:** Completed real loopback API, SQLite, LangGraph synchronous/SSE, and frontend HTTP smoke; core MVP is verified.
- **2026-08-06:** Reconciled the interrupted independent audit. Fixed the stale P0 React Flow issue plus provider SSRF/model-policy, timeout, ID/Buzz validation, dependency reproducibility, `.env`, topology/runtime-load, and SSE framing/correlation findings; preserved cancellation/queue/TOCTOU work as explicit backlog.
- **2026-08-06:** Drew selected exact Nanbeige4.2 for both SearXNG synthesis and M⊕, with isolated GPU listeners and one shared D:-hosted GGUF. Updated both canonical trackers before implementation.
- **2026-08-06:** Verified the accepted publisher checkout is clean at commit `c6640a1c0cf7b38df342b67021a3900b04d092e7`; existing `build-sm75` is CUDA architecture 75 only, and the RTX 5060 Ti reports compute capability 12.0.
- **2026-08-06:** First `build-sm120` CMake configure was interrupted during compiler-feature detection. It produced no `CMakeCache.txt`, solution, project, or generation stamp; the accepted SM75 build and source checkout were untouched. The new empty/incomplete build directory remains parent-owned for a clean retry.
- **2026-08-06:** Clean background reconfigure completed for CUDA architecture `120a`; started the isolated `llama-server` Release target as tracked process `proc_b754bfd743f3` without modifying source or `build-sm75`.
- **2026-08-06:** Implemented the M⊕ Nanbeige route across `backend/graph.py`, `backend/main.py`, `backend/.env.example`, `START_BACKEND.cmd`, `frontend/components/nodes/{types.ts,CoderNode.tsx}`, `frontend/components/Canvas.tsx`, `frontend/app/globals.css`, and `README.md`.
- **2026-08-06:** Created parent-owned M⊕ runtime files `D:\AI\Runtimes\nanbeige-workspace-launcher\launch.config.json`, `Start-NanbeigeWorkspace.ps1`, `Status-NanbeigeWorkspace.ps1`, and `Stop-NanbeigeWorkspace.ps1`; they reference the shared exact GGUF but have independent port/PID/log/GPU state.
- **2026-08-06:** Drew changed the active topology to reuse the small Nanbeige model on the existing RTX 2070 SUPER listener. M⊕ now targets `127.0.0.1:8080/v1` / `nanbeige4.2-3b-local`; the SM120 build was canceled and its artifacts were preserved as superseded.
- **2026-08-06:** Reconciled backend defaults, ignored local `.env`, Coder-node model option, Canvas hardware/readiness copy, README commands, and tracker state to the shared-listener topology.
- **2026-08-06:** Completed final shared-listener acceptance: exact model/hash, RTX 2070 placement, SearXNG local synthesis, M⊕ SSE Coder execution, FastAPI/Next HTTP liveness, and frontend/backend final checks all passed.

## 11. Master agentic coding prompt — reference specification supplied by Drew

> This section preserves the master prompt supplied by Drew for use with advanced coding agents. It is reference material inside the project tracker, not an instruction to override the current decision ledger. The reconciliation directly below it is authoritative for this workspace.
>
> Current conflicts already resolved in favor of the active project decisions:
>
> - Qwen 2.5 Coder is rejected; MiniMax-M3 is the selected coder route.
> - The current path policy is workspace-rooted and fail-closed, not arbitrary absolute Windows paths from the canvas.
> - The current agent-launch policy is allowlisted configuration, not arbitrary subprocess arguments.
> - The current backend uses explicit provider configuration and must not copy Hermes credentials.
> - The prompt's `/api/execute` SSE stream is now a required implementation milestone, alongside the existing synchronous validation/run contract.

````markdown
# MASTER SYSTEM DIRECTIVE: M⊕ AI Visual Workspace
You are an expert full-stack AI engineer. Your objective is to build a complete, local-first visual node editor (IDE) that bridges a React Flow frontend with a FastAPI/LangGraph backend.

## Context & Hardware
The user is running this on Windows 10/11 with a dual-GPU setup:
- GPU 0 (RTX 5060 Ti): Reserved for local LLM inference (Ollama).
- GPU 1 (RTX 2070 Super): Reserved for audio transcription (Buzz CLI / Whisper).
All logic must be air-gapped. NO external cloud API calls are permitted.

## Project Architecture
Create a root folder `ai-workspace` containing two sub-directories: `backend` and `frontend`.
```text
ai-workspace/
├── backend/
│   ├── requirements.txt
│   ├── main.py              # FastAPI server, SQLite endpoints, SSE Streaming
│   ├── graph.py             # LangGraph state machine, JSON compilation adapter
│   └── database.py          # SQLAlchemy schema
└── frontend/
    ├── package.json
    ├── app/
    │   ├── globals.css
    │   ├── layout.tsx
    │   └── page.tsx
    └── components/
        ├── Canvas.tsx       # React Flow instance
        └── nodes/
            ├── BuzzNode.tsx # UI for audio transcription
            ├── CoderNode.tsx# UI for local code generation
            ├── FileNode.tsx # UI for file I/O
            └── TaskNode.tsx # UI for Kanban tracking

```

## PHASE 1: Backend Setup (Python)

1. **Initialize Environment:** Create `backend/requirements.txt` with: `fastapi uvicorn langchain langchain-community langgraph sqlalchemy pydantic aiofiles sse-starlette`.
2. **Database:** Implement `database.py` using SQLite (`workspace.db`). Create a `Project` table with `id`, `name`, and `canvas_state` (JSON).
3. **API Routes (`main.py`):**
* Configure CORS for `@url:`http://localhost:3000``.
* Implement `POST /api/projects` to save the React Flow JSON state.
* Implement `GET /api/projects/{id}` to load the state.


4. **LangGraph Tools (`graph.py`):**
* Define `AgentState(TypedDict)` containing `messages: List[str]` and `project_tasks: Dict[str, str]`.
* Implement the Buzz CLI tool wrapper exactly as follows using `subprocess`:
`buzz add --task transcribe --model-type whispercpp --model-size <size> --txt <file_path>`
Ensure it awaits completion, reads the `.txt` output, and returns the text.
* Implement the local Coder node using `ChatOllama(model="qwen2.5-coder")`.



## PHASE 2: The Graph Adapter (The Hard Part)

In `graph.py`, implement `compile_graph_from_json(graph_json: dict) -> StateGraph`.

* The agent must parse the incoming React Flow `nodes` and `edges`.
* Dynamically add nodes to a `StateGraph(AgentState)` based on the React Flow node `type` (e.g., if type is `buzz`, add the Buzz tool; if type is `coder`, add the Ollama function).
* Loop through the React Flow `edges` and call `builder.add_edge(edge.source, edge.target)`.
* Compile the graph.
* *Crucial:* In `main.py`, expose a POST endpoint `/api/execute` that takes the canvas JSON, compiles the graph, and uses Server-Sent Events (SSE) or WebSockets to stream the LangGraph node execution steps (using `.stream()`) back to the frontend.

## PHASE 3: Frontend Setup (Next.js)

1. **Initialize:** Scaffold a Next.js 15 app in `frontend/`. Install `@file:"xyflow/react`"` and `tailwindcss`.
2. **Custom Nodes:** Implement the 4 custom nodes in `components/nodes/`:
* `CoderNode`: A dark-themed card with a model select dropdown, prompt textarea, and Left/Right Handles.
* `BuzzNode`: A blue-themed card with an audio file path input, size dropdown, and Handles.
* `FileNode`: An input for absolute Windows file paths.
* `TaskNode`: A visual checklist/Kanban tracker.


3. **React Flow Canvas (`Canvas.tsx`):**
* Register the `nodeTypes`.
* Add a header bar with "Save Workspace", "Load Workspace", and "Execute Flow" buttons.
* "Execute Flow" must POST the current nodes and edges to `/api/execute` and listen to the SSE stream, displaying real-time AI execution logs in a floating terminal window overlay on the canvas.



## PHASE 4: Execution & Verification

1. Ensure the Python FastAPI server runs on port 8000.
2. Ensure the Next.js server runs on port 3000.
3. Read the codebase to ensure NO hardcoded cloud API keys exist.
4. Format all code cleanly. Acknowledge this prompt by outputting a brief plan, and then immediately begin scaffolding the files. Do not stop until the entire directory structure and all specified files are completely written and wired together.

````

### Tracker reconciliation of the reference prompt

- **Model:** The prompt is retained verbatim, but its `qwen2.5-coder` line is superseded by the current shared Nanbeige decision. No executable default or fallback may reintroduce Qwen 2.5.
- **Network boundary:** The prompt says air-gapped while also naming MiniMax. The active implementation treats MiniMax as an explicit endpoint selected by Drew; no endpoint or key is assumed, and a missing configuration fails closed. If strict air-gap is reaffirmed, switch the active provider back to a verified local runtime before the live model smoke.
- **Graph execution:** The synchronous `/api/workflows/validate` and `/api/workflows/run` routes remain useful for bounded acceptance; `/api/execute` with SSE node events is added to the remaining roadmap because the master prompt explicitly requires it.
- **Paths:** The prompt's absolute-path input is narrowed to `WORKSPACE_ROOT` containment to preserve local safety.
- **Dependencies:** The implementation uses split provider packages (`langchain-ollama` and `langchain-openai`) rather than assuming the older `langchain-community` import path; compatibility is recorded and verified in the dependency milestone.

## 12. Master-prompt implementation delta

- [x] Add `/api/execute` SSE streaming over LangGraph `.stream()` with metadata-only node events; live smoke passed.
- [x] Add the floating terminal/event overlay in `Canvas.tsx`; type/build verification passed.
- [x] Keep shared Nanbeige4.2-3B visible as the coder default and remove every Qwen 2.5 executable fallback; source scan passed.
- [x] Preserve the workspace-root path guard instead of accepting arbitrary absolute paths.
- [x] Add final Windows startup documentation for ports 8000 and 3000.
- [x] Run the consolidated verification batch only after the full directory is wired.

## 13. Phase 2–4 execution addendum supplied by Drew

````markdown
## PHASE 2: The Graph Adapter (The Hard Part)
In graph.py, implement compile_graph_from_json(graph_json: dict) -> StateGraph.

The agent must parse the incoming React Flow nodes and edges.

Dynamically add nodes to a StateGraph(AgentState) based on the React Flow node type (e.g., if type is buzz, add the Buzz tool; if type is coder, add the Ollama function).

Loop through the React Flow edges and call builder.add_edge(edge.source, edge.target).

Compile the graph.

Crucial: In main.py, expose a POST endpoint /api/execute that takes the canvas JSON, compiles the graph, and uses Server-Sent Events (SSE) or WebSockets to stream the LangGraph node execution steps (using .stream()) back to the frontend.

## PHASE 3: Frontend Setup (Next.js)
Initialize: Scaffold a Next.js 15 app in frontend/. Install @file:`xyflow/react` and tailwindcss.

Custom Nodes: Implement the 4 custom nodes in components/nodes/:

CoderNode: A dark-themed card with a model select dropdown, prompt textarea, and Left/Right Handles.

BuzzNode: A blue-themed card with an audio file path input, size dropdown, and Handles.

FileNode: An input for absolute Windows file paths.

TaskNode: A visual checklist/Kanban tracker.

React Flow Canvas (Canvas.tsx):

Register the nodeTypes.

Add a header bar with "Save Workspace", "Load Workspace", and "Execute Flow" buttons.

"Execute Flow" must POST the current nodes and edges to /api/execute and listen to the SSE stream, displaying real-time AI execution logs in a floating terminal window overlay on the canvas.

## PHASE 4: Execution & Verification
Ensure the Python FastAPI server runs on port 8000.

Ensure the Next.js server runs on port 3000.

Read the codebase to ensure NO hardcoded cloud API keys exist.

Format all code cleanly. Acknowledge this prompt by outputting a brief plan, and then immediately begin scaffolding the files. Do not stop until the entire directory structure and all specified files are completely written and wired together.
````

### Addendum reconciliation

- The requested graph-to-LangGraph translation is implemented as a typed, validated adapter rather than trusting arbitrary node JSON.
- The requested `/api/execute` SSE path is required in addition to the existing bounded JSON run endpoint.
- `CoderNode` defaults to the shared Nanbeige4.2-3B route per Drew's latest topology decision; MiniMax/Ollama remain explicit alternates.
- `FileNode` keeps the requested local-file workflow while enforcing `WORKSPACE_ROOT` containment instead of accepting arbitrary absolute paths.
- The final verification gate must prove ports 8000/3000, no hardcoded keys, the SSE path, and a real local graph smoke before the project is called complete.

## 14. Review and publication handoff — 2026-08-06 23:57 CDT

- Drew requested a source review, conventional commit, branch push, and pull request for the current shared-listener M⊕ changes. This publication request supersedes the prior local-only stopping point, but does not change the standalone workspace boundary or the shared RTX 2070 SUPER route.
- Parent-owned review inspected the current backend provider/agent/SSE paths, frontend Canvas/ChatPanel/node contracts, environment example, package manifest, README, `.gitignore`, and canonical tracker. No embedded credentials were found; credential-pattern matches are environment names, policy text, or the local `api_key="not-needed"` sentinel. The executable-source scan found only the intentional Qwen 2.5 rejection guard.
- Publication blocker: `ai-workspace` is not a Git checkout, has no `.git` directory or remote, and no matching GitHub repository was found under the authenticated `phoenixfire808` account. The existing `DrewLocalVoice` checkout remains a separate dirty project and must not receive this workspace's history.
- Commit/push/PR remain pending until Drew supplies or confirms the target GitHub repository (owner/repository), base branch, and whether a new repository should be created if no target exists. No repository initialization, commit, remote mutation, push, or PR creation is claimed.

## 15. Publication target and final pre-commit verification — 2026-08-06 23:59 CDT

- Drew confirmed creation of a new public GitHub repository `phoenixfire808/ai-workspace` with `main` as the base. The local project remains standalone; `DrewLocalVoice` is not a publication source.
- Final focused checks passed: backend `py_compile` for the active modules, frontend `npm run typecheck`, and a clean Next.js 15.5.23 production build after stopping the stale port-3000 server that was racing the generated `.next` tree.
- Focused live smoke passed after restoring the frontend service: `GET http://127.0.0.1:3000/` returned 200 with the M⊕ marker; FastAPI `/api/health` returned 200; `/api/chat/tools` returned 200.
- The first two build attempts exposed only stale/concurrent `.next` artifact failures (`ENOENT`/`MODULE_NOT_FOUND`); no source failure remained after the known server was stopped and the final build completed cleanly.

## 16. GitHub publication receipts — 2026-08-07 00:08 CDT

- Created public repository `https://github.com/phoenixfire808/ai-workspace`; pushed the empty `main` bootstrap commit `9b2c337` (`chore: initialize ai-workspace repository`).
- Created and pushed `feat/shared-nanbeige-agentic-workspace` with conventional commit `b675a077d8e5fb595c5dcdf7abdfdc1f24b5c457` (`feat: add shared Nanbeige agentic workspace`). The commit contains 37 intended project files; generated Next caches, dependencies, local `.env`, databases, and build metadata are ignored.
- Opened ready-for-review PR #1 against `main`: `https://github.com/phoenixfire808/ai-workspace/pull/1`. GitHub reports `OPEN`, non-draft, head `feat/shared-nanbeige-agentic-workspace`, and the expected feature commit.
- Parent-owned post-publication verification passed: `npm run typecheck`; `NEXT_DIST_DIR=.next-acceptance npm run build` on Next.js 15.5.23; frontend `/` 200; FastAPI `/api/health` 200; shared Nanbeige `/v1/models` 200. The isolated build did not race the live port-3000 server.
- The remaining follow-up working-tree changes are limited to the append-only tracker receipt and Next-generated `next-env.d.ts`/`tsconfig.json` references for `.next-acceptance`; they are being published without changing runtime behavior.
