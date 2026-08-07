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
| 2026-08-07 00:35 CDT | SM120 candidate build | Parent-owned `cmake --build build-sm120 --config Release --target llama-server --parallel 8` completed normally with exit code 0. `llama-server.exe`, `llama-server-impl.dll`, `llama-common.dll`, `llama.dll`, `ggml.dll`, `ggml-base.dll`, `ggml-cpu.dll`, `ggml-cuda.dll`, and `mtmd.dll` all exist under `D:\\AI\\Runtimes\\nanbeige-llama.cpp\\build-sm120\\bin\\Release`. This is a built RTX 5060 candidate profile, not an activated route. |
| 2026-08-07 00:35 CDT | SM120 artifact identity | SHA-256: `llama-server.exe` = `4d9de94cbf97d33153a8fcf61e55e7b7fc40dccd3f72927a513b7adfe5a3f000`; `ggml-cuda.dll` = `91e99e7c305db1b942d589097ffee4b04d8f206d2984060c1b5adc4c3e954a9c`. All nine expected runtime files were hashed successfully; full in-session receipt is retained in project history. |
| 2026-08-07 00:10 CDT | Changed-behavior acceptance | Safe sandbox output completed, `os.environ` access was rejected by the AST policy, Hermes catalog discovery returned 192 skills without credential/session access, and Start→Planner SSE completed `run_started → node → node → complete`. Disposable FastAPI `:8010` was stopped after acceptance. |
| 2026-08-07 00:10 CDT | Acceptance status | LFM clone identity, backend compile/import, frontend typecheck, isolated Next production build, Nanbeige non-regression, governed tool catalog, LFM fail-closed readiness, Planner execution, sandbox policy, and live loopback smoke are accepted. A real LFM tool-generation loop remains blocked until an exact `LFM2.5-2.6B` endpoint is separately provisioned. |
| 2026-08-07 00:10 CDT | Parent acceptance close | Independent retry against reconciled FastAPI `:8001` confirmed frontend `:3000` HTTP 200, exact Nanbeige model on `:8080`, seven governed tools, `lfm_preflight_timeout` fail-closed chat behavior, and real Nanbeige Start→Coder SSE completion in 1.96 seconds. Both parent-launched services remained running after smoke. |
| 2026-08-07 00:11 CDT | Acceptance lifecycle cleanup | Stopped only the disposable parent FastAPI `:8001` process after acceptance. The live frontend `:3000`, baseline FastAPI `:8000`, and Nanbeige `:8080` services remain outside that cleanup. |
| 2026-08-07 00:11 CDT | Runtime-control scope | Started the next additive slice: named GPU/model profiles and read-only preflight, a workspace-rooted terminal preview/classifier, and local Upgrade Center inventory/preflight. No listener activation, model restart, arbitrary shell execution, download, external action, or rollback mutation is included in this slice. |
| 2026-08-07 00:14 CDT | Frontend readiness receipt | Background process `proc_3dd9d229d713` matched `Ready in 1503ms` for `npm run start -- --hostname 127.0.0.1 --port 3000`; the live UI remains available on loopback. |
| 2026-08-07 00:14 CDT | Approved topology reconciliation | Drew's approved target is split Nanbeige: SearXNG on `:8080` / `nanbeige4.2-3b-local`, M⊕ on `:8081` / `nanbeige4.2-3b-workspace` using the SM120 RTX 5060 Ti route. Parent read-only probing found only `:8080` listening and `:8081` unavailable; no migration, restart, or listener mutation was performed, so the split topology remains pending implementation/acceptance. |
| 2026-08-07 00:24 CDT | Agent operator guidance requested | Drew asked how to use “the agent.” Current source exposes two distinct surfaces: the right-side `Local coding loop` (LFM-backed chat with seven governed tools and approval prompts) and the canvas `Agent reaction` node (allowlisted `WORKSPACE_AGENT_COMMANDS` launch). The chat UI is live but intentionally fails closed because the exact LFM endpoint is not provisioned; configured Agent Reaction targets are currently empty. No configuration or lifecycle mutation was performed for this guidance request. |
| 2026-08-07 00:24 CDT | Agent/tool UX priority | Drew requested visible dropdown menus for selecting agents and tools, immediate deployment controls, and first-class tool/agent nodes on the canvas. Planning is active before implementation. Proposed baseline: populate Agent choices from `/api/agents`, Tool choices from `/api/chat/tools`, add a governed Tool node, and provide both “Add to canvas” and “Run now” paths while retaining approval gates for execution/dispatch tools. Exact quick-deploy and registry scope await Drew's confirmation. |
| 2026-08-07 00:29 CDT | Ollama-first priority correction | Drew directed that models installed in Ollama take priority. Active implementation now targets local Ollama model discovery/selection, exact local readiness, and one real Ollama workflow smoke. Nanbeige `:8080` remains the verified baseline; the SM120 split target and LFM route are deferred and will not be started or repointed during this lane. |
| 2026-08-07 00:29 CDT | Unified library decisions | Drew selected the full interaction: `Add to canvas`, `Run now`, and one-click prebuilt templates. The registry should expose as many safe local options as possible, including governed tools, configured agents, Hermes skills, installed Ollama models, explicit model routes, runtime profiles, and templates. Templates must queue all required approvals into one review screen before execution. Ollama-first priority is preserved in model ordering. |
| 2026-08-07 00:29 CDT | Unified library plan | Wrote the parent-only implementation plan at `.hermes/plans/2026-08-07_002401-unified-agent-tool-library.md`. It specifies a backend-owned normalized registry, searchable category/dropdown UI, Tool and Runtime nodes, registry-backed Agent/Coder dropdowns, governed quick-run SSE, server-bound approval receipts, and eight starter templates. No source implementation or runtime mutation was performed during planning. |
| 2026-08-07 00:14 CDT | Disposable verifier cleanup | Confirmed `proc_02c22c668fe5` exited with code `-15` after the acceptance batch. No test FastAPI process remains on `:8010`; live `:8000`, `:3000`, and Nanbeige `:8080` services were not targeted. |
| 2026-08-07 00:42 CDT | Ollama implementation + testing boundary | Added loopback-only Ollama inventory/preflight, Ollama-first fresh defaults, exact installed-ID dropdowns in Coder/Control Center, and the `ollama-local-models` runtime profile. Read-only probing found the two exact installed models and both `/v1/models` entries; Drew directed that remaining model testing wait until final acceptance, so no more inference is run in this lane. |
| 2026-08-07 00:48 CDT | Live Ollama UI/backend integration | Replaced the stale FastAPI `:8000` process with the updated source; `/api/ollama/models` now returns HTTP 200 and `ready` with two models, while Nanbeige health remains ready. Rebuilt the frontend with typecheck + canonical production build, restarted `:3000`, and confirmed HTTP 200 plus the `Control Center` marker. Ollama inventory is client-fetched after hydration. No model inference was run. |
| 2026-08-07 01:00 CDT | Unified Library UI deployed | Drew approved the production UI replacement. Stopped only stale frontend PID `61824` without tree termination, confirmed port `3000` released, and launched the current Next production build on loopback. Next reported `Ready in 1299ms`; HTTP `:3000` returned 200 and the replacement listener is PID `5976`. Live browser acceptance shows the hydrated `Local library`, category/search controls, 217 registry options, Ollama-first installed model choices, governed Tool and Runtime palette nodes, eight templates, backend health, and the approval-aware controls. Backend `:8000/api/library` remained HTTP 200 throughout; no model inference or backend restart occurred. |
| 2026-08-07 01:04 CDT | Resizable visibility UX requested | Drew requested a more adjustable workspace where panels/content can be resized and the large option catalog is easier to see and browse. Planning is active before implementation. The current fixed grid uses `250px / canvas / 275px`, node cards are fixed at `266px`, and the 217-resource library uses a seven-row native listbox; likely improvements are draggable side splitters, collapsible panels, saved dimensions, a full-canvas mode, resizable node cards/output areas, and a searchable categorized resource browser. Exact resize scope and browser interaction await Drew's confirmation. |
| 2026-08-07 01:07 CDT | Resizable visibility scope confirmed | Drew selected left/right side-panel splitters with collapse buttons and chose to retain the current library list while making it taller, wider through panel resizing, and vertically resizable. Node-card and vertical chat/output resizing are excluded from this slice. The implementation plan is saved at `.hermes/plans/2026-08-07_010712-resizable-workspace-panels.md`; it includes bounded widths, keyboard-accessible splitters, persisted layout, reset control, responsive fallback, and a build-before-live-replacement gate. |
| 2026-08-07 01:19 CDT | Resizable layout deployed and accepted | Added bounded draggable splitters, keyboard resize, collapse/reopen rails, persisted/resettable panel state, 320/340 px defaults, and a 286 px vertically resizable library list. TypeScript and isolated Next production build passed. Acceptance on `:3001` verified keyboard resize from 320 to 340 px, collapse/reopen persistence, right-panel canvas expansion, reset, and list sizing; the disposable server was stopped. Replaced only stale frontend PID `5976`, launched the accepted build on `:3000` (`Ready in 1513ms`, listener PID `107676`), confirmed 217 hydrated resources and HTTP 200 for frontend/backend, and preserved `.next-pre-resizable-20260807-0107` for rollback. Backend/model listeners were untouched. |
| 2026-08-07 01:24 CDT | GitHub publication authorized | Drew explicitly authorized commit, push, and PR publication. The current branch is `feat/shared-nanbeige-agentic-workspace`, synchronized with origin, and already owns open PR #1. Publication will update that PR rather than create a duplicate. Scope is the accepted resizable-layout frontend and tracker receipts; transient isolated-build references are excluded before staging. |
| 2026-08-07 01:25 CDT | Resizable UI feature published | Committed the accepted layout slice as `470fe60` (`feat(ui): add resizable workspace panels`) with four scoped files and pushed `feat/shared-nanbeige-agentic-workspace` to origin. The existing open PR #1 is the authoritative review surface, avoiding a duplicate PR. Generated isolated-build path edits were removed before staging; the pushed commit contains the resizable/collapsible/persisted panels, taller resizable library list, CSS, and tracker receipts only. |
| 2026-08-07 01:30 CDT | Functional tools + human-in-the-loop requested | Drew requested that every exposed option perform a real bounded action, protected actions pause for meaningful human review, each run carry useful context, and execution visibly show what each node/tool does. Planning is active before implementation. Current source has seven governed tool contracts, one-shot action/graph preview tokens, a basic combined approval modal, transient SSE node status lines, and chat tool-start/tool-end events, but it does not yet provide a durable inspectable run timeline, editable per-action pause/resume, retained graph/input/tool context, or a verified capability receipt for every one of the 217 library entries. Exact coverage, approval granularity, and context-retention policy await Drew's confirmation. |
| 2026-08-07 01:49 CDT | Durable HITL runtime scope frozen | Drew selected the full configurable design: every library entry must have a real primary action or visible disabled reason; tools must be easy to drag/place/run; file operations include create, patch, rename, and delete with exact per-action diff approval; any node may fan out in parallel, sequentially, conditionally, or through chunked map execution; joins support selectable merge strategies; Human Review and Chat Input are draggable nodes; workflows can choose preflight, per-action, or step-through approval; Planner exposes every applicable model/prompt/tool/context/routing/chunk/approval control; registered local plugins are permitted but placeholders are not. Full local graph/input/step/argument/output/diff/approval/error/timing context is retained until explicit transactional deletion. The detailed implementation plan is `.hermes/plans/2026-08-07_014925-durable-hitl-workflow-runtime.md`. No runtime implementation begins until Drew approves that plan. |
| 2026-08-07 01:58 CDT | Model routing plan revision requested | Drew did not approve implementation yet and requested that the frozen plan add model placement on any selected graphics card plus Ollama Cloud/custom endpoint configurations. Revision planning must cover per-node/per-model hardware selection, Auto/CPU/single-GPU/multi-GPU policies where supported, VRAM/readiness guards, bounded load/unload/queue behavior, local Ollama and remote/custom provider profiles, secret-safe credential storage, visible endpoint/model readiness, and exact fallback rules. Official Ollama Cloud versus arbitrary compatible endpoint scope awaits clarification before the plan is rewritten. |
| 2026-08-07 02:04 CDT | Model routing revision completed | Drew selected all endpoint and hardware options plus maximum applicable advanced settings. The plan now supports local desktop Ollama, managed isolated loopback Ollama instances, LAN Ollama, official Ollama Cloud through local offload or direct API, arbitrary Ollama-compatible/OpenAI-compatible endpoints, and existing Nanbeige/LFM/MiniMax profiles. Model nodes can select Auto, CPU, any stable discovered GPU, ordered multi-GPU sets, or saved hardware profiles. Because Ollama controls placement within a server, strict GPU targeting uses separate visible-device runtime profiles and records requested versus observed processor placement; no per-request GPU guarantee is fabricated. All cloud/fallback policies are selectable and default to explicit-only. Credential aliases stay outside graphs/run history. Official Ollama cloud/FAQ/API docs were discovered through local SearXNG and incorporated into `.hermes/plans/2026-08-07_014925-durable-hitl-workflow-runtime.md`. Implementation still awaits Drew's approval. |
| 2026-08-07 02:06 CDT | Revised durable runtime plan approved | Drew explicitly approved the complete revised plan and authorized implementation. Primary-session ownership remains in force with no delegated workers. Implementation order is durable run/decision storage, capability-bound file mutation, branch/chunk/merge scheduling, endpoint/hardware profiles, approval/chat/plugin runtime, and Run Inspector UI; broad tests and live replacement remain deferred to the final consolidated acceptance batch. The currently deployed `:3000`/`:8000` services remain untouched during construction. |
| 2026-08-07 02:20 CDT | Branch-ready implementation handoff | Drew intends to branch the approved durable-runtime work and may assign another worker. The canonical tracker was updated before that branch cut with the exact dirty-worktree state, ownership boundaries, safe parallel lanes, known incompleteness, and required return receipts below. No checkpoint commit, branch, worktree, test, service restart, deployment, or external action was performed by the parent while preparing this handoff. |
| 2026-08-07 02:24 CDT | Parent implementation resumed | Drew directed work to continue after the branch-ready handoff. No worker receipt or sibling branch change was present in the canonical checkout. The parent claims Lane A plus the already-owned mutation contracts: durable scheduler/API integration in `backend/execution_runtime.py`, `backend/graph.py`, and `backend/main.py`, with coordinated use of the existing `schema.py`, `database.py`, `tools.py`, and `library.py` edits. Frontend/model lanes remain unclaimed and may be assigned only under the non-overlap protocol below. Live services remain untouched and testing stays deferred to the final batch. |
| 2026-08-07 02:46 CDT | Integrated implementation pass + concurrent-write incident | Parent added the durable run engine, run/history/decision/chat/delete APIs, capability audit, endpoint/hardware profile registry, explicit endpoint generation adapter, GPU inventory and managed-Ollama launch previews; frontend work added six control nodes, branching connections, schema-generated library arguments, drag/double-click placement, advanced Planner/Coder route settings, approval-policy selection, and a retained Run Inspector. New parent files are `backend/execution_runtime.py`, `backend/model_profiles.py`, `frontend/components/ModelRouteSettings.tsx`, `frontend/components/RunInspector.tsx`, and `frontend/components/nodes/WorkflowControlNodes.tsx`; shared files are listed by Git. No final tests or deployment have run. During this pass, an unclaimed concurrent actor replaced all of `README.md` with an unrelated request for an undetectable Twitch view bot and created `output/generated.md` containing generic unsupported workflow-analysis prose. Parent restored tracked `README.md` exactly from HEAD because the overwrite was unrelated repository corruption. `output/generated.md` was inspected but preserved pending ownership/cleanup direction. No worker receipt identified the actor, branch, or worktree; future workers must not write in the parent worktree and must register before editing. |
| 2026-08-07 03:06 CDT | Durable runtime acceptance and controlled deployment | Parent reconciled the full tracker and sibling additions, corrected a broken concurrent `runtime_control` import, integrated the bounded Decompose/Delegate plan-only path, concrete plugin registry, local SearXNG research tools, endpoint/hardware routing, and approval-gated app-owned Ollama start/stop/preload/unload tools. Consolidated checks passed: `backend/.venv/Scripts/python.exe -m py_compile backend/*.py`; frontend `npm run typecheck`; `git diff --check`; credential-value scan (`0` matches); isolated Next production build (`NEXT_DIST_DIR=.next-hitl npm run build`, compiled and generated 4/4 pages); and `backend/.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_durable_runtime.py' -v` (`7` tests, `OK`). The suite proves capability-audit honesty, endpoint/hardware inventory, split/merge/plugin execution, durable Human Review and Chat Input resume, step-through policy, Decompose plan-only behavior, exact file create/patch/rename/delete previews, stale-preimage rejection, single-use approval/replay rejection, retained-context deletion, and no model/audio/cloud/worker side effect. A source-only rollback archive was created at `.hermes/backups/hitl-predeploy-20260807_030051.zip` with 25 files. Exact prior listeners on ports 8000/3000 were replaced; new tracked backend/frontend sessions became ready, health/root returned HTTP 200, capability audit reported 227 resources and zero invalid-ready entries, and a live Start→Decompose(plan-only) durable run completed with two steps/five events and was transactionally deleted. `output/` is now ignored as a local runtime artifact. No microphone, TTS playback, model inference/load, cloud request, actual worker dispatch, Hermes mutation, or public send was exercised; those device/provider acceptance lanes remain explicit BLOCKED/DEFERRED until separately authorized/configured rather than falsely reported as passing. |
| 2026-08-07 04:23 CDT | Pre-publication parent review | Reviewed the uncommitted OpenRouter, capability-matrix, GPU-profile, Coder, and Run Inspector delta plus PR #1 state. Existing PR #1 is the authoritative review surface. Found three blockers before publication: endpoint operations unnecessarily invoked `nvidia-smi`, malformed multi-GPU profiles accepted duplicate/single device IDs, and completed runs displayed wall-clock age instead of execution duration. No hardcoded credential value or implicit provider fallback was identified. |
| 2026-08-07 04:23 CDT | Review fixes | Decoupled GPU discovery from endpoint default seeding, moved dynamic multi-GPU profile creation into hardware inventory, rejected duplicate/single-device multi-GPU definitions, corrected completed-run elapsed calculation, and added focused coverage for OpenRouter fail-closed defaults, capability matrix/Markdown export, GPU-probe isolation, and hardware validation. Final consolidated checks remain pending before commit/push. |

## 1.2A Durable runtime branch handoff — ACTIVE (2026-08-07 02:20 CDT)

### Authoritative source and branch-cut warning

- **Parent checkout:** `C:\Users\Drew\Documents\Jarvis_Context\Projects\ai-workspace`
- **Current parent branch:** `feat/shared-nanbeige-agentic-workspace`, synchronized with `origin/feat/shared-nanbeige-agentic-workspace` before the current uncommitted implementation began.
- **Approved specification:** `.hermes/plans/2026-08-07_014925-durable-hitl-workflow-runtime.md` (332 lines at handoff). This is the worker's primary scope contract; `PROJECT_TRACKER.md` remains the append-preserving progress and reconciliation record.
- **Dirty-worktree warning:** the current implementation is not committed. `git switch -c <branch>` in this same worktree carries these edits, but a separate worktree/clone created from the current HEAD or remote branch will not contain them. Before a separate worker starts from another worktree, create an explicit checkpoint commit or transfer an exact patch; do not assume the five edits exist there.
- **Live boundary:** the currently deployed frontend/backend remain the previously accepted build on loopback. The unfinished source has not been deployed. Do not replace `:3000` or `:8000`, start the unverified LFM route, download models, invoke cloud endpoints, or activate a managed model fleet during implementation lanes.

### Exact uncommitted parent state

At handoff, `git diff --stat` reports **5 modified files, 252 insertions, 4 deletions**:

| File | Parent-owned changes now present | State / caveat |
|---|---|---|
| `backend/schema.py` | Added review/chat/split/merge/context/plugin node literals, approval/branch policy types, edge label/priority/condition, graph settings, durable run fields, and decision/chat payloads. | Syntax auto-lint passed. Runtime validators and frontend types do not consume the new contracts yet. |
| `backend/database.py` | Added additive SQLAlchemy models for workflow runs, steps, events, approval requests, endpoint profiles, and hardware profiles. | Syntax auto-lint passed. No repository-layer helpers, transactional deletion, event sequencing, recovery, or acceptance migration check exists yet. Importing the updated module will create tables in the configured database, so workers should use a temporary DB until integration. |
| `backend/tools.py` | Added create/patch/rename/delete schemas, workspace-rooted preview generation, unified diffs, SHA-256 preimage guards, atomic text writes, mutation handlers, and approval-required catalog registration. | Syntax auto-lint passed. No consolidated behavioral test has run. The final approval capability is not yet checked inside these actuators; the durable scheduler must supply and consume that gate. |
| `backend/library.py` | Began enriching mutation previews with exact diffs and server-generated `expected_sha256`/`expected_absent` arguments, binding the preview subject to those normalized arguments. | A temporary syntax typo was corrected and syntax auto-lint then passed. Frontend approval state still sends the original arguments, so protected file quick-run is incomplete until it consumes returned normalized arguments and impact preview. |
| `PROJECT_TRACKER.md` | Recorded the approved product contracts, model-routing revision, implementation start, and this branch handoff. | Documentation only; preserve and append rather than replacing history. |

### Known incomplete or blocked seams

1. `backend/graph.py` still rejects multiple outgoing edges and does not execute the six new node kinds.
2. No durable scheduler, pause/resume recovery, branch/chunk lineage, merge barriers, capability consumption, or idempotent side-effect ledger exists yet.
3. `backend/main.py` does not expose durable run/history/event/decision/chat/delete/capability-audit/profile APIs.
4. No model endpoint/profile control plane, isolated Ollama runtime manager, GPU inventory/placement verifier, or credential-alias resolver exists yet.
5. The frontend has no new node components, Advanced settings, route/profile managers, schema-generated argument form, normalized mutation preview handling, or Run Inspector.
6. Existing `ApprovalReview` remains a one-shot preflight modal rather than a durable per-action Human Review surface.
7. No broad or focused test was run after implementation began, by explicit policy. Nothing in this handoff is an acceptance receipt.

### Recommended non-overlapping worker lanes

Workers must claim exactly one lane and append owner, branch/worktree, start SHA, and files before editing:

- **Lane A — durable scheduler/API:** create `backend/execution_runtime.py`; modify `backend/graph.py` and `backend/main.py`; add run-store helpers in a new module if possible. Treat the current `schema.py` and `database.py` changes as contracts and avoid rewriting them without a tracker receipt.
- **Lane B — frontend canvas/inspector:** create Human Review, Chat Input, Split, Merge, Context, Plugin, Advanced settings, model-route controls, and Run Inspector components; modify `frontend/components/Canvas.tsx`, `frontend/components/nodes/types.ts`, `frontend/components/LibraryPanel.tsx`, and `frontend/app/globals.css`. This is the safest disjoint lane while the parent owns backend mutation contracts.
- **Lane C — model routing:** create `backend/model_profiles.py` and `backend/model_runtime.py`; modify `backend/ollama_control.py` and `backend/runtime_control.py`. Coordinate before touching `schema.py`, `database.py`, `graph.py`, or `main.py`. Do not launch, stop, or repoint real services during implementation.
- **Lane D — acceptance fixtures/audit:** add temporary-workspace/temporary-SQLite tests and capability-audit fixtures without changing runtime source. Do not run GPU/model/cloud/agent acceptance until the parent schedules the final batch.

### Integration and return-receipt contract

Every worker handoff must append: owner/session, branch and worktree path, start/base SHA, claimed lane, files changed, commits, behavioral summary, tests actually run with exact results, tests deliberately not run, blockers, live side effects (normally none), and integration status. A worker must not claim another lane's files without first recording the overlap. The parent will re-read this tracker, inspect diffs, reconcile schema/API contracts, run the final consolidated checks, preserve rollback, and decide deployment/PR integration. Worker self-reports are not acceptance until parent-verified.

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
- [x] Define named runtime-profile schema for model, exact alias, endpoint, GPU mask/device/split mode, slots, state, and activation policy.
- [x] Add data-only profiles for RTX 5060 Ti artifact, RTX 2070 SUPER baseline, dual-GPU review, and explicit LFM experiment; no profile activation is implied.
- [x] Build and hash the complete SM120 `llama-server` candidate artifact set on D: for the RTX 5060 Ti profile; activation and GPU placement remain gated.
- [x] Add Runtime Control UI for selecting, preflighting, and inspecting profiles; start/stop/cutover controls remain intentionally unimplemented.
- [ ] Require live exact-alias, executable ownership, target/foreign GPU placement, bounded generation, and rollback receipts per activated profile.

**Gate:** Drew can select an approved model/GPU profile, see the effective settings before launch, activate it without port/process ambiguity, and return to the prior verified profile in one controlled action.

### Milestone 8 — Integrated terminal — PREVIEW CONTRACT

- [x] Select the first contract as a bounded workspace-rooted command preview/classifier; no command execution is exposed yet.
- [x] Reject credential access, shell chaining, redirection, network/process-control/destructive commands, and out-of-workspace CWDs.
- [ ] Add terminal session create/input/resize/cancel/close APIs and streamed output with explicit process ownership.
- [ ] Root sessions in the project workspace, filter inherited credentials/environment, cap retained output, and keep commands/results out of metadata-only workflow logs.
- [ ] Add visible approval and policy boundaries for network, destructive, external, credential, or out-of-workspace operations.

**Gate:** A user can open, use, cancel, and close a local workspace terminal from M⊕ without focus theft, orphaned processes, secret leakage, or graph-driven arbitrary command execution.

### Milestone 9 — Upgrade Center — READ-ONLY SLICE

- [x] Inventory local M⊕ manifests and LFM artifact presence without downloads or credential access.
- [x] Show disk, manifest, and verified Nanbeige baseline readiness before any mutation.
- [x] Expose a visible rollback policy that remains unarmed until a future explicit backup/activation workflow.
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
- `backend/ollama_control.py`
- `backend/runtime_control.py`
- `backend/terminal_control.py`
- `backend/upgrade_control.py`
- `backend/requirements.txt`
- `backend/database.py`
- `backend/schema.py`
- `backend/graph.py`
- `backend/main.py`
- `backend/.env.example`
- `frontend/app/globals.css`
- `frontend/components/ChatPanel.tsx`
- `frontend/components/ControlCenterPanel.tsx`
- `frontend/components/Canvas.tsx`
- `frontend/components/nodes/*.tsx`
- `frontend/components/nodes/PlannerNode.tsx`
- `frontend/package.json` and `frontend/package-lock.json`
- `frontend/postcss.config.mjs` and `frontend/tailwind.config.ts`
- `README.md`
- `.gitignore`
- `START_BACKEND.cmd`
- `START_FRONTEND.cmd`
- Built candidate RTX 5060 runtime artifacts: `D:\AI\Runtimes\nanbeige-llama.cpp\build-sm120\` and `D:\AI\Runtimes\nanbeige-workspace-launcher\{launch.config.json,Start-NanbeigeWorkspace.ps1,Status-NanbeigeWorkspace.ps1,Stop-NanbeigeWorkspace.ps1}`. The Release `llama-server` artifact set linked successfully and has recorded hashes, but it is not on the active route until profile preflight, generation, placement, and rollback acceptance pass; the shared SearXNG SM75 launcher remains authoritative.

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
- `backend/runtime_control.py` defines versioned named GPU/model profiles and exact loopback model preflight without activation or listener mutation.
- `backend/terminal_control.py` and `POST /api/terminal/preview` provide a workspace-rooted no-execution classifier with credential, shell-chain, network, process-control, destructive, and out-of-root rejection.
- `backend/upgrade_control.py` and the Upgrade Center routes inventory local manifests/artifacts, disk, and baseline readiness; rollback is visible but intentionally unarmed.
- `frontend/components/ControlCenterPanel.tsx` exposes profile preflight, terminal preview, and read-only Upgrade Center inventory in the right panel.
- `backend/ollama_control.py` adds loopback-only `/api/tags` + `/v1/models` inventory, exact-ID preflight, remote-endpoint rejection, and mutation-free readiness payloads.
- `backend/graph.py` now uses Ollama as the fresh-install provider default, resolves a blank `OLLAMA_MODEL` from exact installed inventory, and preflights the selected model before `ChatOllama` generation; explicit Nanbeige remains supported.
- `backend/runtime_control.py` puts `ollama-local-models` first and keeps the verified Nanbeige profile separately protected; `backend/.env.example` documents Ollama-first routing without mutating the ignored runtime `.env`.
- `frontend/components/nodes/CoderNode.tsx` and `frontend/components/nodes/types.ts` default new coder nodes to Ollama and populate an exact installed-model dropdown; `ControlCenterPanel.tsx` displays the local inventory.

### Known incomplete / deferred state

- The exact MiniMax-compatible endpoint and API key remain unconfigured because MiniMax is optional. A live M⊕ Nanbeige Coder-node call passed through the shared listener.
- The Ollama server was not ready, Buzz was absent from PATH, and no allowlisted agent command was configured; those integrations remain fail-closed.
- New parent read-only probing at 00:29–00:42 found Ollama healthy with two exact installed IDs and both OpenAI-compatible; this supersedes the earlier unavailable receipt for the current lane. No pull/delete/start mutation was performed.
- Real shared Nanbeige model/GPU acceptance passed. Buzz, microphone, and Agent Reaction acceptance remain separate and unrun.
- `npm audit --omit=dev` reports three high transitive PostCSS/sharp advisories in the newest Next 15 line; npm's automated fix requires the breaking Next 16 line, so it was not forced.
- Independent-review fixes are now verified: server-side Qwen 2.5 rejection, environment-only provider endpoints, bounded model calls, Buzz-size allowlist, safe graph IDs, tested LangGraph/LangChain pins, correct compiled-graph annotation, automatic ignored `.env` loading, frontend topology/load guards, and robust/correlated SSE framing.
- Deferred hardening: cancelling a synchronous worker after an SSE client disconnects, replacing the cross-thread event list with a queue, full SSE replay, and eliminating symlink/TOCTOU races around external Buzz/file writes.
- The Python tool is a bounded same-user subprocess policy layer, not a security boundary equivalent to a VM/container; destructive or unrestricted shell/GUI/browser tools remain intentionally unimplemented.
- The chat approval continuation currently resubmits the prompt with an approved tool list; durable LangGraph checkpoints/time-travel resume remain future work.
- Runtime profile activation/start/stop/cutover, interactive ConPTY/session APIs, downloads/build jobs, checksum activation, and rollback mutation remain intentionally deferred.
- Drew directed that all model testing be performed at the end. One bounded Ollama inference smoke against the installed LFM Ollama ID completed before that correction (`OLLAMA_SMOKE_OK`, 45.55s); it is an early receipt only, not final model acceptance. No further model inference/testing is authorized in this lane before final acceptance.

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
- The follow-up working-tree changes were limited to the append-only tracker receipt and Next-generated `next-env.d.ts`/`tsconfig.json` references for `.next-acceptance`; they were published in `b59285b` without changing runtime behavior.

## 17. Current-version GitHub update preflight — 2026-08-07 01:00 CDT

- Drew requested the current assembled version be pushed to GitHub and carried by the existing ready-for-review PR #1. The target remains `phoenixfire808/ai-workspace`, base `main`, branch `feat/shared-nanbeige-agentic-workspace`; no duplicate repository or PR will be created.
- The newer source slice adds the backend-owned unified local library/templates/approval contracts, Ollama inventory/preflight, named runtime profiles, terminal command preview classification, read-only upgrade inventory/preflight, Tool/Runtime nodes, Library/Control Center/approval UI, and Ollama-first Coder selection. The standalone Nanbeige baseline and LFM fail-closed route remain preserved.
- The publication candidate excludes `.hermes/` internal plan output and `notes/` unrelated session material via `.gitignore`; caches, virtualenvs, local configuration, databases, and generated build outputs remain excluded. The canonical tracker and README are project-owned and remain included.
- Parent-owned readiness hardening gates static library model routes: Nanbeige uses the active exact-model runtime preflight, LFM remains disabled until its separate runtime is provisioned, and MiniMax remains disabled until its endpoint/key are explicitly configured. No provider fallback or runtime mutation was added.
- Final preflight passed: backend `.venv` `py_compile` for all modules; frontend `npm run typecheck`; isolated `NEXT_DIST_DIR=.next-current npm run build`; FastAPI TestClient matrix (health 200, 217-resource library, templates 200, five runtime profiles, Ollama ready, upgrade preflight ready, safe terminal preview allowed, shell command rejected, action preview 200); and current frontend build HTTP smoke on `127.0.0.1:3001` returned 200 with the M⊕ marker.
- Publication state at this receipt: source is verified and ready to update PR #1; the final commit SHA and GitHub head will be recorded in the follow-up publication receipt after the push is confirmed.

## 18. Current-version GitHub publication — 2026-08-07 01:04 CDT

- Published the current unified-library/runtime-control source slice in `f61bdf3be8f2c6ceebb15dfaab670b52d08c13c1` (`feat: add unified local tool and runtime library`) on `feat/shared-nanbeige-agentic-workspace`.
- Remote verification confirms `origin/main` remains `9b2c337cc974d49dffb30fc1f86c48d2ced1d3fd` and the feature branch contains `f61bdf3be8f2c6ceebb15dfaab670b52d08c13c1`.
- PR #1 is open and non-draft at `https://github.com/phoenixfire808/ai-workspace/pull/1`, targeting `main`; its title/body now describe the unified library, approval controls, Ollama-first route, read-only runtime/terminal/upgrade boundaries, verification, and deferred mutations.
- The isolated current frontend smoke server on `127.0.0.1:3001` exited with code `-15` after returning HTTP 200 with the M⊕ marker; no temporary test process remains. Existing baseline loopback services were not targeted by this smoke cleanup.
- Publication closeout is complete for the current GitHub/PR target. Runtime activation, interactive terminal sessions, downloads, service cutover, external hosting, and rollback mutation remain intentionally deferred and are not claimed by this receipt.

## 19. Complete functionality, voice, and execution-visibility roadmap — 2026-08-07 02:27 CDT

### 19.1 Drew's requested outcome

Drew wants the workspace treated as a real, inspectable local automation product rather than a visual catalog of partial integrations. Every exposed tool, agent, skill, model route, runtime, template, Buzz transcription control, TTS control, Hermes action, and workflow execution path must either work end-to-end or clearly show why it is unavailable. When a run executes, Drew must be able to see what each node and tool did, what context it received, what approval decision allowed it, what it returned, and where the run stopped.

This section is an append-only roadmap annotation. It records the product contract and future acceptance gates; it does not claim that the items below are already implemented.

### 19.2 Annotation legend

- **`[NOW]`** — active parent-owned implementation or reconciliation target.
- **`[NEXT]`** — the next implementation slice after the current tracker/branch handoff.
- **`[AUDIT]`** — must be checked against source and a real bounded execution path; catalog presence is not evidence.
- **`[HITL]`** — must pause for a meaningful, resumable human decision before the protected action continues.
- **`[VOICE]`** — Buzz/local audio feature with explicit consent, device, and capture boundaries.
- **`[ACCEPTANCE]`** — final consolidated evidence required before publication or deployment claims.
- **`[BLOCKED]`** — cannot be called functional until the named dependency or user authorization exists.
- **`[DEFERRED]`** — intentionally not activated during construction; preserve the boundary rather than silently substituting another route.

### 19.3 Functional product contracts

1. **[AUDIT] Capability truth:** Every library entry has one of three honest states: a tested primary action, a bounded failure with a specific remediation, or a visible disabled/unavailable reason. No placeholder handlers, fake success payloads, silent no-ops, or catalog-only claims.
2. **[HITL] Human review:** Protected actions pause in a durable review state. The review surface shows the exact action, normalized arguments, affected files/targets, diff or impact preview, risk class, requesting node, and current run context. Drew can approve, deny, edit, cancel, or resume without losing the run.
3. **[AUDIT] Visible execution:** Each run exposes a chronological inspector timeline with run ID, graph/node IDs, start/finish timestamps, status, input/context references, selected model/runtime, tool calls, bounded arguments, approval events, outputs, failure classes, retries, branch/chunk lineage, and final result. Sensitive content remains out of logs while the UI still provides useful bounded previews.
4. **[NOW] Durable context:** Retained context includes the original workflow/input, graph snapshot, node configuration, per-step state, tool result metadata, approval decisions, user chat continuations, and model/runtime readiness evidence. Retention lasts until Drew explicitly performs a transactional delete; delete receipts must be visible.
5. **[AUDIT] Local-first boundary:** No cloud transcription, telemetry, implicit network fallback, credential leakage, raw audio logging, transcript logging, clipboard logging, or target-field logging. Explicitly selected remote model endpoints remain distinguishable from local routes and fail closed when unavailable.

### 19.4 Buzz transcription roadmap

- **[VOICE][NEXT] Record control:** Add a clear Record/Stop button to the Buzz transcription surface and/or Buzz node. The control must show `idle → requesting consent → preparing device → recording → transcribing → stopped/error`, disable duplicate starts, and allow an explicit cancel.
- **[VOICE][HITL] Consent and device gate:** Require explicit opt-in before microphone or call/system-audio capture. Show the selected endpoint/API, readiness, and failure reason without opening or changing devices implicitly. Synthetic UI success must not be reported as microphone acceptance.
- **[VOICE][AUDIT] Real event flow:** Verify one authorized utterance through bounded metadata events: capture start, frame/peak receipt, partial transcript, final transcript, stop, and reset. Never write raw audio or transcript text to logs or the tracker.
- **[VOICE][NEXT] Transcript handoff:** Make final Buzz text a real workflow input that can feed Planner, Coder, Chat Input, or a user-approved downstream node. Preserve the source run/context ID and distinguish transcript-derived input from typed input.
- **[VOICE][ACCEPTANCE] Device/model boundary:** Separate synthetic parser/lifecycle checks, local API checks, and explicitly authorized Windows microphone/model acceptance. A working endpoint or UI button alone is not proof that audio frames or local STT inference succeeded.
- **[VOICE][DEFERRED] Automatic capture:** No background capture, call recording, or participant/system-audio capture is enabled by default. These require their own explicit consent contract and acceptance receipt.

### 19.5 Text-to-speech roadmap

- **[VOICE][NEXT] TTS action:** Add a real Speak/Stop/Replay control and a workflow-capable TTS action. It must report provider, voice, readiness, duration/byte metadata, playback state, and bounded failure class.
- **[VOICE][AUDIT] Provider truth:** Support only providers that are actually installed/configured for the selected lane. Local TTS is preferred when available; Edge/remote providers are explicit choices, not silent fallbacks. Missing dependencies or credentials produce a visible disabled reason.
- **[VOICE][HITL] External audio boundary:** Playback is local and user initiated by default. No message send, call injection, broadcast, or external publication is implied by generating or playing speech. Any external send remains approval-gated.
- **[VOICE][ACCEPTANCE] Playback proof:** Verify generation and playback separately: text accepted, audio produced, player started, player stopped/replayed, and errors surfaced. Do not claim TTS works from a successful configuration read alone.

### 19.6 Hermes functionality roadmap

- **[NOW][AUDIT] Hermes catalog:** Reconcile every exposed Hermes skill/agent entry with its actual local adapter, allowlist, required environment, and safe workspace root. Record `functional`, `blocked`, `disabled`, or `failed` with a reason.
- **[NEXT] Hermes dispatch:** Make a selected Hermes skill/agent execute through the configured adapter and return bounded start/end/error events into the same Run Inspector timeline. The adapter must use the configured workspace root and never read or mutate profiles/credentials from graph JSON.
- **[HITL] Protected Hermes operations:** Skill dispatch, file mutation, terminal-like operations, credential use, external messaging, and irreversible actions require the appropriate review mode. Approval must be consumed exactly once and bound to the normalized action arguments.
- **[AUDIT] Context continuity:** Hermes receives the selected workflow context and returns a resumable run step, not an opaque success string. If a child session or process is created, its identity and continuity boundary are visible.
- **[BLOCKED] Provider/runtime gaps:** Missing Hermes runtime, missing adapter, unavailable provider, or invalid configuration must remain an explicit failure/disabled state. Do not route to an unrelated coder model or claim Hermes success from catalog discovery.
- **[ACCEPTANCE] Fresh-process proof:** Run a bounded Hermes smoke in a separate process/profile boundary, verify the exact response and session/run receipt, inspect durable session integrity read-only, and distinguish CLI, Desktop, gateway, and Buzz-managed ACP health.

### 19.7 Complete functionality-audit matrix

The final audit must produce a durable, exportable matrix with these columns:

| Surface | Resource/action | Primary handler | Preconditions | Approval mode | Context/run receipt | Observed result | Verdict | Remediation |
|---|---|---|---|---|---|---|---|---|
| Library | tool / agent / skill / model / runtime / template | exact local adapter or handler | dependencies, endpoint, workspace, device | none / preflight / per-action / step-through | run ID + step IDs | bounded output/failure | PASS / BLOCKED / DISABLED / FAIL | exact next action |
| Canvas | node type and edges | graph compiler/scheduler | schema, inputs, route readiness | graph policy | graph snapshot + lineage | event timeline | PASS / FAIL | source/API seam |
| Buzz | record/transcribe/handoff | local capture + STT adapter | consent, device, model | explicit capture consent | transcript input provenance | frame/event receipt | PASS / BLOCKED / FAIL | device/model step |
| Voice | speak/stop/replay | configured TTS adapter | provider/voice/player | local user action or explicit review | TTS step receipt | audio/playback receipt | PASS / BLOCKED / FAIL | dependency/config |
| Hermes | skill/agent dispatch | local Hermes adapter | allowlist, profile, runtime | policy-bound review | child/session/run identity | start/end/error | PASS / BLOCKED / FAIL | adapter/runtime step |

The audit must test both the happy path and the declared failure path for each category. A green inventory endpoint is not an execution receipt.

### 19.8 Implementation order after branch cut

1. **[NOW] Tracker and branch handoff:** Preserve this annotation before creating a separate branch/worktree. Record the branch, base SHA, ownership, and exact files before any worker edits. No worker has been started by this tracker update.
2. **[NEXT] Durable run/inspector vertical slice:** Finish run/event/approval persistence, resume/cancel/delete semantics, bounded context rendering, and one real protected tool flow from preview → review → resume → visible result.
3. **[NEXT] Capability audit:** Build a backend-owned capability report for all library entries and ensure the frontend renders disabled reasons and real action controls rather than assuming every catalog item is runnable.
4. **[NEXT] Voice lane:** Implement Buzz Record/Stop/consent/event state and the transcript handoff contract, then add TTS Speak/Stop/Replay with provider readiness and local playback boundaries.
5. **[NEXT] Hermes lane:** Complete allowlisted dispatch, bounded context transfer, visible child/session identity, and fresh-process acceptance without mutating live Hermes configuration or credentials.
6. **[ACCEPTANCE] Consolidated audit and publication:** Run focused source checks first, then one final batch covering backend compile/import, frontend typecheck/build, API capability matrix, durable HITL lifecycle, run inspector rendering, one authorized voice path if provisioned, Hermes smoke, loopback health, and clean Git/PR receipts. Deploy only after all required verdicts are PASS or an explicit BLOCKED reason is recorded.

### 19.9 Branch/worker handoff annotation

- The tracker is now safe to use as the parent handoff document if Drew creates a branch or separate worktree.
- Proposed disjoint lanes are **(A) durable runtime/Run Inspector**, **(B) Buzz transcription/TTS**, **(C) Hermes capability adapter/audit**, and **(D) read-only acceptance fixtures**. A lane must not edit another lane's owned files without recording an overlap and coordinating integration.
- The parent remains responsible for source-of-truth reconciliation, live-service boundaries, final tests, device/model acceptance, deployment, commit/push, and PR updates.
- Worker summaries are not completion evidence. Each handoff must include branch/worktree, base SHA, files changed, exact commands/results, deliberately skipped checks, blockers, live side effects, and integration status.
- Until Drew explicitly creates/assigns the branch/worktree, continue parent-only and do not start parallel edits merely to fill lanes.

### 19.10 Current status after this annotation

- **Implemented before this entry:** unified local library, Ollama-first inventory/preflight, approval-aware quick actions, resizable panels, initial graph/schema/database/file-mutation foundations, and the open PR #1 publication history above.
- **Not yet claimed:** complete functionality of all catalog entries, durable Run Inspector, resumable Human Review, Buzz record button, local STT acceptance, TTS playback, complete Hermes dispatch acceptance, or the final capability matrix.
- **Live services:** preserve the previously accepted loopback boundaries during construction; do not replace them with unfinished source until the final acceptance gate passes.
- **This entry's side effect:** tracker documentation only. No source implementation, branch creation, worker dispatch, service restart, model inference, audio capture, Hermes mutation, commit, push, or PR change was performed by this annotation.

### 19.11 Tracker-write verification and current worktree reconciliation — 2026-08-07 02:27 CDT

- The new roadmap section is present through line 899; the scoped `git diff --check -- PROJECT_TRACKER.md` passed with only Git's normal LF→CRLF warning.
- A repository-wide `git diff --check` remains non-clean because `README.md:1` has pre-existing trailing whitespace. The unrelated README line was not changed or reformatted.
- Current worktree inventory after the annotation: modified `PROJECT_TRACKER.md`, `README.md`, `backend/database.py`, `backend/graph.py`, `backend/library.py`, `backend/main.py`, `backend/schema.py`, and `backend/tools.py`; untracked `backend/execution_runtime.py` and `output/` are also present.
- The newly observed `README.md`, `backend/execution_runtime.py`, and `output/` state must be inspected and classified before branching or publication. No assumption is made that these artifacts are safe to stage.

## 20. Branch-aware implementation reconciliation — 2026-08-07 02:40 CDT

- **Authoritative checkout:** `C:\Users\Drew\Documents\Jarvis_Context\Projects\ai-workspace`.
- **Current branch:** `feat/shared-nanbeige-agentic-workspace`, currently at `d6f9616`, matching `origin/feat/shared-nanbeige-agentic-workspace`. `main` remains at `9b2c337`; no additional local branches or linked worktrees are present.
- **Parent ownership:** This session is continuing parent-owned integration. No delegated worker or sibling branch receipt is present. Any future branch must read this tracker before editing and append its base SHA, ownership, files, commands, blockers, and integration status before claiming work.
- **Current implementation found on disk:** durable runtime/API work is now present in `backend/execution_runtime.py`; model routing work is present in `backend/model_profiles.py` and `frontend/components/ModelRouteSettings.tsx`; Run Inspector and workflow-control node components are present in `frontend/components/RunInspector.tsx` and `frontend/components/nodes/WorkflowControlNodes.tsx`; Canvas and graph/schema/database/library/main files have additional uncommitted edits.
- **Current acceptance state:** these changes are unverified and not deployed. The live accepted loopback services remain the previous published build. No model, audio, Hermes, cloud, or external action is being activated during this reconciliation.
- **Next parent slice:** reconcile the durable runtime imports/API contract, wire the Run Inspector and workflow-control nodes into the canvas, then perform one bounded backend/frontend verification batch and record exact receipts before any branch or PR action.
- **Known classification boundary:** the modified `README.md`, untracked `output/`, and any generated/cache artifacts remain outside the implementation until inspected. They must not be staged by assumption.

## 21. Web search, deep research, and context ingestion roadmap — 2026-08-07 02:41 CDT

### 21.1 Requested capability

Drew wants the workspace to perform local-first web search and deeper multi-source research, then use the retrieved context inside workflows, agents, planners, coders, and the Run Inspector. Search must be a real governed capability: visible queries, source URLs, extraction status, citations, bounded evidence, failure reasons, and context provenance—not a fake result list or an opaque prompt injection path.

This roadmap is additive to the functionality/HITL/voice/Hermes contract in Section 19 and must be read by every future branch/worktree before editing.

### 21.2 Product contracts

- **[WEB][NOW] Local discovery:** Route discovery through the local loopback SearXNG JSON API (`SEARXNG_URL`, default `http://127.0.0.1:8888`). Do not silently substitute a cloud search provider. If SearXNG is unavailable, show `search_backend_unavailable` and preserve the run as blocked rather than fabricating results.
- **[WEB][NEXT] Search tool:** Add a real governed search action with query, category/time range, result limit, safe-search, language/region, and source-domain controls. Return normalized title, URL, engine/source metadata, snippet, rank, and a stable source ID.
- **[WEB][NEXT] Deep-research action:** Support bounded query expansion, primary/official-source targeting, independent evidence, counterevidence/failure modes, date coverage, duplicate suppression, domain diversity, robots/rate-limit handling, and selected-page extraction. Keep maximum queries/pages/depth/concurrency bounded.
- **[WEB][HITL] Retrieval boundary:** Search and page retrieval are network-facing actions and must be visible in the run timeline. A workflow-level review can authorize a deep crawl, domain allowlist, or remote page fetch; credential-bearing, private, localhost, and unsafe URLs fail closed.
- **[WEB][AUDIT] Source safety:** Retrieved pages are untrusted evidence, never instructions. Do not execute commands, follow workflow instructions, reveal secrets, or mutate files because a page says to do so. Respect robots, redirect, DNS/private-address, response-size, timeout, and per-domain limits.
- **[WEB][NEXT] Context packet:** Convert selected search/extraction results into a bounded structured packet containing source IDs, URLs, titles, excerpts, claims, fetched-at metadata, extraction status, and citation links. Preserve source provenance when the packet enters Planner/Coder/Agent/Hermes context.
- **[WEB][AUDIT] Visible context use:** The Run Inspector must show which sources were selected, what bounded excerpts entered each step, the context size/trim decision, and the citations returned by the model/tool. Raw full pages are not copied into every prompt by default.
- **[WEB][VOICE] Buzz handoff:** A Buzz transcript can seed a search/deep-research query. The transcript remains tagged as user-provided input, while retrieved sources remain separately tagged evidence; neither may be confused in the final context packet.
- **[WEB][MODEL] Local synthesis:** When the dedicated loopback Nanbeige endpoint is healthy and advertises `nanbeige4.2-3b-local`, downstream evidence synthesis may use the RTX 2070 SUPER route. This does not claim SearXNG discovery or HTTP crawling is GPU-accelerated. Never substitute Qwen or another coder model for this synthesis lane.
- **[WEB][DEFERRED] Remote model fallback:** Search/extraction can still produce a source dossier without model synthesis. If Nanbeige synthesis is unavailable, mark synthesis blocked and retain the evidence files; do not silently use cloud or another model.
- **[WEB][ACCEPTANCE] Evidence receipts:** A web-capability acceptance receipt must include the backend used, query count, result count, selected sources/domains, extraction success/failure classes, context packet hash/size, citations, and whether local Nanbeige synthesis ran.

### 21.3 Planned workspace surfaces

1. **Search node** — one or more queries, filters, result normalization, bounded result set.
2. **Research node** — multi-query/depth/page controls, official/independent/counterevidence lanes, dossier/evidence output.
3. **Source selector/context node** — select sources, trim excerpts, label evidence, pass packet downstream.
4. **Run Inspector web pane** — query events, source list, fetch/extraction outcomes, citations, context injection, and approval receipts.
5. **Library capability rows** — `Search web`, `Extract page`, `Deep research`, `Build context packet`, and `Synthesize evidence`, each with real readiness/disabled reasons.
6. **Chat/Buzz input bridge** — “Search this” / “Research this” uses the current approved input and keeps transcript/user text provenance visible.

### 21.4 Branch-aware implementation order

- **[NOW] Contract record:** this section is the authoritative web scope for future branches.
- **[NEXT] Backend adapters:** add loopback SearXNG discovery, bounded native extraction, normalized source/evidence records, and a context-packet builder behind explicit tool schemas.
- **[NEXT] Runtime integration:** persist web queries, source records, extraction events, selected evidence, context packet metadata, and citations in the durable run context; connect approval decisions and resumable execution.
- **[NEXT] Frontend:** add Search/Research/Source Context nodes, Library controls, and Run Inspector evidence views.
- **[NEXT] Functional audit:** exercise search-backend unavailable, result normalization, source selection, robots/private-URL rejection, extraction failure, context trimming, citation preservation, and Nanbeige synthesis/no-fallback paths.
- **[ACCEPTANCE] Final run:** execute one bounded local SearXNG search, extract at least one selected public source, build a context packet, feed it to a local workflow step, and verify the Run Inspector exposes provenance and citations without logging secrets/raw audio.

### 21.5 Current status

- **Not yet implemented/claimed:** web search node, deep-research node, SearXNG adapter, bounded extraction adapter, durable source/evidence records, context-packet injection, web capability audit, or web acceptance smoke.
- **Existing research policy:** local SearXNG discovery first, selected native extraction only, RTX 2070 SUPER Nanbeige for downstream synthesis when healthy, no Qwen/coder-model substitution.
- **Branch rule:** any branch that touches web search, deep research, context injection, Run Inspector, or library capability records must read Sections 19–21 and append its scope/ownership/base SHA/files/verification before editing.
- **This update:** tracker scope only. No network search, page crawl, model synthesis, service restart, source implementation, branch creation, commit, push, or PR change was performed by this annotation.

## 22. Decompose / Delegate worker node roadmap — 2026-08-07 02:44 CDT

### 22.1 Requested capability

Drew wants a canvas node that can take one larger request, decompose it into useful subtasks, assign those subtasks to an approved worker/agent/persona, and return the child work into the parent workflow with full context and visible results. This is a product workflow capability—not permission for the parent agent to silently spawn arbitrary workers.

### 22.2 Node contract

- **Node name:** `Decompose / Delegate` (working label; final UI label may be `Worker Decomposition`).
- **Input:** inherited workflow input plus selected context packet, including web evidence, Buzz transcript provenance, prior node outputs, project identity, and explicit user instructions.
- **Decomposition:** choose bounded strategy: model-assisted plan, fixed checklist, or user-provided subtasks. The node records the decomposition prompt, model/route, output schema, and generated subtask list.
- **Worker target:** select one approved configured local agent, Hermes skill/agent adapter, or a local model-backed worker profile. No arbitrary command, credential, unregistered plugin, or hidden provider substitution.
- **Assignment modes:** single worker, parallel fan-out, sequential handoff, round-robin approved pool, or parent-only plan with no dispatch.
- **Limits:** maximum subtasks, maximum concurrent workers, per-child timeout, retry count, context-character budget, and total child budget are explicit and bounded.
- **Context:** every child receives a child context packet tagged with `parent_run_id`, `parent_step_id`, `child_run_id`, `subtask_id`, source/provenance IDs, selected web citations, and the exact assignment. Credentials and sensitive stores remain excluded.
- **Merge:** child results return as ordered results, labeled object, JSON array, first-success, or a model-reduce request subject to the workflow's route and approval policy.
- **Human review:** creating/dispatching child workers pauses under `preflight`, `per_action`, or `step_through` policy as appropriate. Review shows the subtask list, worker targets, inherited context summary, route, limits, and expected side effects. Approve, edit, deny, cancel, and resume are durable.
- **Visibility:** the Run Inspector shows decomposition created, each child queued/running/waiting/completed/failed/cancelled, worker/session identity, input-context hash/size, tool/approval events, output preview, failure class, timing, and merge result. Child runs remain linked to the parent until explicit deletion.
- **No silent autonomy:** an empty worker registry, unavailable Hermes adapter, missing model route, or exceeded budget is a visible `delegate_unavailable`/`delegate_budget_exceeded` result—not a fallback to an unrelated agent.

### 22.3 Planned implementation surfaces

1. `backend/schema.py` — add `delegate` node type and bounded decomposition/assignment settings.
2. `backend/execution_runtime.py` — persist decomposition records, child lineage, dispatch approvals, bounded scheduling, cancellation, and merge barriers.
3. `backend/graph.py` — add validated node execution/preflight for the node and preserve legacy graph compatibility.
4. `backend/hermes_adapter.py` / worker registry — expose only concrete, allowlisted local targets with readiness reasons.
5. `frontend/components/nodes/DecomposeNode.tsx` — worker/strategy/context/budget/merge controls.
6. `frontend/components/RunInspector.tsx` — expandable parent/child tree and child context/citation view.
7. `frontend/components/LibraryPanel.tsx` — show the node as a real canvas capability and expose worker readiness/disabled reasons.
8. Capability audit — verify no worker option claims ready without a concrete handler and bounded smoke path.

### 22.4 Branch-aware handoff rules

- Any branch touching decomposition, worker dispatch, Hermes adapters, Run Inspector, web context, or graph schemas must read Sections 19–22 first.
- Before editing, append branch/worktree, base SHA, owner, claimed files, and non-overlap boundaries here or in the next tracker receipt.
- A worker/agent product node must not be confused with Hermes's own development-worker delegation. The node only dispatches configured product targets after the workflow's review policy permits it.
- Parent integration remains responsible for reconciling child-run persistence, source context, approvals, API contracts, final acceptance, and PR publication.

### 22.5 Current status

- **Not yet implemented/claimed:** `delegate` schema, node component, child-run persistence, worker target registry UI, decomposition/dispatch API, parent-child Run Inspector tree, or the final worker capability audit.
- **This update:** tracker scope only. No worker was spawned, no external action occurred, and no source/service/branch/PR mutation was performed by this annotation.

### 21.6 Parent implementation receipt — 2026-08-07 02:57 CDT

- Added `backend/web_research.py` with local SearXNG JSON search, bounded multi-query deep research, public-page extraction, redirect/DNS/private-address/robots/size checks, normalized stable source IDs, and citation-preserving context packets.
- Registered `search_web`, `extract_web_page`, `deep_research`, and `build_research_context` in `backend/tools.py`, the Library registry, approval catalog, and tool-node execution path.
- Empty `query`/`context_text` tool arguments inherit the previous workflow output, enabling `input → deep research → cited context → coder` composition.
- Added `deep-research-context` Library template. Remote page extraction/deep research remain approval-gated; the local search backend reports `search_backend_unavailable` instead of pretending to be ready.
- **Not yet verified:** live SearXNG availability, page extraction against a selected public source, robots/private URL rejection, source/context packet behavior, library disabled reasons, or downstream local-model use. No network search or model synthesis was run during this implementation receipt.

### 22.6 Parent implementation receipt — 2026-08-07 02:57 CDT

- Added `backend/delegation.py` with bounded checklist/line/paragraph/sentence decomposition, explicit subtask input, plan-only mode, single/sequential/parallel dispatch, max-subtask/max-parallel limits, child IDs, and visible queued/error receipts.
- Added the `delegate` graph/schema node and `frontend/components/nodes/DecomposeNode.tsx`; wired it into Canvas node types, palette metadata/defaults, CSS accents, graph execution, workflow approval preview, and the `decompose-worker-plan` template.
- Dispatch is restricted to configured agent targets or explicitly configured `hermes:<skill>` adapters; protected dispatch requires a durable approval. Plan-only mode is safe and does not start workers.
- **Known boundary:** this first slice records child assignment/queue receipts and returned PIDs/adapter output; durable parent/child run persistence, child completion collection, and expandable Run Inspector lineage remain outstanding and are still tracked in Section 22.
- **Not yet verified:** graph validation, plan-only execution, approval pause/resume, configured-worker dispatch, UI build, or live worker behavior. No product worker was spawned by this receipt.

## 23. Live deployment checkpoint — 2026-08-07 03:03 CDT

- **User request:** deploy the current workspace live for visual/manual inspection.
- **Target:** loopback only — frontend `http://127.0.0.1:3000`; backend `http://127.0.0.1:8000`.
- **Pre-deploy state:** neither port 3000 nor 8000 was listening at checkpoint time. No prior live process needed replacement.
- **Current worktree:** dirty and intentionally uncommitted; includes sibling-lane runtime/model/plugin/test files in addition to the web-research and delegate changes. No files are being staged or committed by this deployment.
- **Deployment sequence:** locate the working Python environment, run the frontend production build, start FastAPI without exposing secrets, start Next production server on loopback, verify readiness endpoints, then report the exact URL and any blocker.
- **Safety boundary:** no public bind, cloud call, model inference, audio capture, worker dispatch, or external send is part of this deploy. SearXNG and remote page retrieval remain user-visible feature actions, not implicit deploy actions.
- **Status:** superseded by the accepted deployment receipt below; the sibling deployment attempt raced the parent `.next` tree, returned HTTP 500, and exited. It was not accepted as the live build.

### 23.1 Accepted deployment and publication handoff — 2026-08-07 03:11 CDT

- **Accepted frontend:** loopback production server on `http://127.0.0.1:3000`, launched from the isolated verified `.next-hitl` artifact. The rejected sibling listener exited; the accepted root returns HTTP 200.
- **Accepted backend:** loopback Uvicorn on `http://127.0.0.1:8000`, refreshed after the final managed-runtime tool registration. Health returns HTTP 200.
- **Acceptance receipts:** backend compilation passed; frontend typecheck passed; isolated production build passed; `git diff --check` passed; credential-value scan found zero matches; seven focused durable-runtime tests passed; one deployed Start→Decompose(plan-only) smoke completed and its retained run was deleted.
- **Capability state:** durable approvals/run inspection, split/chunk/merge/context/plugin nodes, model endpoint/hardware profiles, governed file mutation, local SearXNG research tools, bounded Decompose/Delegate plan-only execution, and approval-gated app-owned Ollama lifecycle tools are implemented. Device/provider side effects remain unexercised unless explicitly approved/configured.
- **Rollback:** `.hermes/backups/hitl-predeploy-20260807_030051.zip` preserves the source-only predeployment state; `.hermes/` remains ignored.
- **Git/PR handoff:** 26 source/test/tracker files are staged on `feat/shared-nanbeige-agentic-workspace`; PR #1 is open but still carries the older 217-resource description. Parent publication is now the only active milestone: restore generated `next-env.d.ts`, commit, push, update the PR body with the verified 227-resource durable-runtime receipts, and verify the remote head.

### 23.3 Parent live deployment receipt — 2026-08-07 03:13 CDT

- **Accepted frontend listener:** PID `176704`, loopback `127.0.0.1:3000`, running `next start` from the freshly rebuilt production artifact. Host curl returned HTML `200` with Next static assets and the workspace marker.
- **Accepted backend listener:** PID `176664`, loopback `127.0.0.1:8000`, running from `backend/.venv` with `PYTHONPATH` cleared. `/api/health` returned `200` and reported the Nanbeige route ready.
- **Frontend build:** `cmd.exe /d /s /c "npm run build"` passed after the prior `.next` artifact reported a missing `vendor-chunks/d3-selection.js` module. The broken generated directory was preserved as `frontend/.next-predeploy-20260807-0303`; a clean `.next` was rebuilt and accepted.
- **Backend/API smoke:** `py_compile` and the focused import/graph/delegation/context/private-URL smoke passed in `backend/.venv`; `/api/projects`, `/api/library`, `/api/hardware/profiles`, and `/api/health` returned `200`.
- **Browser receipt:** `http://127.0.0.1:3000/?build=unified-library` loaded with title `M⊕ AI Visual Workspace`; refreshed snapshot shows backend health `nanbeige · nanbeige4.2-3b-local`, populated Library, `Decompose / Delegate` palette entry, and web tools with the real disabled reason `search_backend_timeout` because local SearXNG did not answer preflight.
- **Current status:** live for Drew’s review. No public bind, model inference, worker dispatch, audio capture, external send, commit, push, or PR mutation was performed by this parent deployment.
- **Important:** the browser-driver’s first snapshot briefly showed `API disconnected` while the backend was being replaced; after refresh it showed the live health/library state. The host-side backend log recorded successful frontend API requests throughout final acceptance.

### 23.2 GitHub publication completed — 2026-08-07 03:13 CDT

- Committed the verified durable-runtime change set as `0088f54` (`feat: add durable HITL workflow runtime`): 26 files, 3,149 insertions, and 99 deletions.
- Pushed `feat/shared-nanbeige-agentic-workspace`; fetched remote verification showed local and `origin/feat/shared-nanbeige-agentic-workspace` both at full SHA `0088f546098f1d8b49f2ceebe9073ca38f0ed7c2` with a clean tracked worktree.
- Updated PR #1 to **“feat: add durable HITL visual workflow runtime”** at `https://github.com/phoenixfire808/ai-workspace/pull/1`. Read-back verified the durable-runtime summary, seven-test receipt, explicit deferred-acceptance section, open state, and matching head SHA.
- Final live read-back after managed-runtime registration: frontend HTTP 200, backend health HTTP 200, capability audit HTTP 200 with **231 resources and zero invalid-ready entries**. The PR body was corrected from the earlier 227-resource pre-registration count to 231.
- Publication is complete. Remaining tracker roadmaps involving microphone/TTS device acceptance, real model/cloud calls, actual worker dispatch/child completion, and Hermes mutation remain separate approval/configuration-gated work—not hidden failures in this accepted publication.

### 23.4 Duplicate backend launcher clarification — 2026-08-07 03:15 CDT

- `proc_601ed209e4c3` exited with code 3 because it attempted to bind `127.0.0.1:8000` while the accepted backend listener was already serving on that port.
- This is an expected duplicate-launch collision, not a backend outage: `/api/health` returned HTTP 200 and listener PID `176664` remains active.
- The healthy backend and frontend were left untouched; no restart, kill, commit, push, or external action was performed for this clarification.

### 23.5 Duplicate frontend launcher clarification — 2026-08-07 03:16 CDT

- `proc_ccd687343650` exited with code 1 because it attempted to bind `127.0.0.1:3000` while the accepted Next production listener was already serving on that port.
- This is an expected duplicate-launch collision, not a frontend outage: the live page returned HTTP 200 with Next assets and the workspace marker; listener PID `176704` remains active.
- The healthy frontend and backend were left untouched; no restart, kill, commit, push, or external action was performed for this clarification.

### 23.6 Repeated stale frontend launcher notification — 2026-08-07 03:17 CDT

- `proc_00942844fba2` exited with code 1 after another attempt to bind the already-active `127.0.0.1:3000` listener.
- The accepted frontend remains healthy: HTTP 200, workspace HTML present, listener PID `176704`, accepted process `proc_f69ce0bf1709` still running.
- No restart or cleanup was performed; this is recorded as a stale duplicate notification.

## 24. Post-publication complete-functionality continuation — ACTIVE (2026-08-07 03:25 CDT)

### 24.1 Direction and ownership

- **User direction:** continue implementing everything recorded in the canonical tracker and keep this Markdown file current during work.
- **Authoritative branch/base:** `feat/shared-nanbeige-agentic-workspace` at published head `ebcbefecb7bc6654c6fa6d268d6385a616b75625` when this phase began; PR #1 remains the publication target.
- **Parent ownership:** primary session owns integration. No new worker is authorized or assigned by this entry. Existing live loopback listeners on ports 3000/8000 remain untouched until a later consolidated acceptance/deployment gate.
- **Safety boundary:** source implementation and synthetic/read-only checks may proceed. Microphone capture, TTS playback, public-page retrieval, model loading/inference, actual product-worker dispatch, Hermes dispatch/profile mutation, and external sends remain explicit approval/configuration-gated actions.

### 24.2 Reconciled remaining scope

1. **Web UI/provenance — IN PROGRESS:** backend SearXNG search, extraction, deep-research, and context-packet tools exist and are governed. Remaining work is dedicated Search/Research/Source Context nodes, persisted source/query/context metadata, and Run Inspector evidence/citation views. Historical Section 21.5 “not implemented” text is superseded only for the backend adapters—not for these remaining UI/receipt contracts.
2. **Voice lane — PENDING:** implement explicit Buzz Record/Stop consent states and transcript provenance handoff, then local TTS Speak/Stop/Replay provider/readiness contracts. Construction must not open a device or play audio implicitly.
3. **Delegate continuity — PENDING:** the node/schema and bounded plan-only adapter exist. Remaining work is durable parent/child run identity, completion/error collection, child context receipts, and expandable Run Inspector lineage. Actual dispatch remains separately reviewed.
4. **Hermes lane — PENDING:** existing skill inventory/read/dispatch adapters must gain an exportable truth audit plus durable bounded context/session receipts. Fresh-process execution will be run only against an explicitly configured safe adapter/profile boundary.
5. **Final audit — PENDING:** export the Section 19.7 matrix and run one consolidated compile/type/build/API lifecycle batch. Device/provider paths must end as PASS or an exact BLOCKED/DISABLED reason—never assumed green.

### 24.3 Current active slice

- Implement web-specific canvas nodes by composing the existing governed tool schemas rather than adding duplicate network clients.
- Extend durable run events/steps with bounded web provenance metadata and render queries, source IDs/URLs, extraction failures, context hashes/sizes, and citations in Run Inspector.
- Add focused tests for unavailable local SearXNG, private/loopback URL rejection, context-packet provenance, and graph serialization. Do not perform a public crawl during this slice.
- Update this section immediately when priorities, ownership, blockers, verification receipts, or deployed behavior change.

### 24.4 Web UI/provenance implementation progress — 2026-08-07 03:25 CDT

- Added dedicated `search`, `research`, and `source_context` graph/node types and `frontend/components/nodes/WebResearchNodes.tsx`; Canvas registration and palette metadata/defaults now expose them as first-class workflow nodes.
- The durable runtime normalizes these nodes into the existing `search_web`, `deep_research`, and `build_research_context` tools. Approval requirements therefore remain backend-owned and cannot be bypassed by the dedicated UI.
- Persisted web outputs now derive bounded provenance records containing backend/status, query/result/domain counts, source IDs/titles/URLs/ranks, extraction/failure classes, packet ID/hash/size/truncation, and citations. A metadata-only `web_provenance` event is emitted, while full bounded output remains stored once in the step.
- Run Inspector now renders a web-provenance section with selected citation links, extraction outcomes, packet hash, size, and explicit failure reason.
- Corrected inherited research-context handling so an incoming JSON source envelope is parsed into records without also being duplicated as a large `[USER-CONTEXT]` block.
- **Verification status:** implementation only; per Drew's batch-testing preference, compile/type/build and focused web failure/provenance tests remain deferred to the consolidated acceptance phase after the voice, Delegate, and Hermes slices. Live services have not been restarted and public retrieval/model synthesis has not run.

### 24.5 Voice implementation progress — 2026-08-07 03:25 CDT

- `BuzzNode` now exposes explicit microphone-consent, Record, Stop, and Cancel controls with visible `idle → requesting_consent → preparing_device → recording → transcribing → stopped/error` states. Duplicate starts are disabled, in-flight transcription is abortable, and recordings auto-stop at five minutes.
- Added loopback-only `POST /api/audio/transcribe`: consent is mandatory; payloads are capped at 50 MiB and five minutes; MIME/model values are bounded; random temporary artifacts live under ignored `.runtime/audio`; audio and Buzz transcript files are deleted in `finally` after the response is assembled.
- Successful capture stores transcript text as selected local workflow context plus provenance (`capture_id`, local provider/model, duration, byte count, source kind, deletion receipt). Durable `node_completed` events redact the transcript preview rather than copying speech text into event logs.
- The Buzz execution seam accepts the explicitly captured transcript as real node output, preserving its node/run source, while the existing workspace-file path remains available and guarded.
- Added a first-class `tts` node with manual Speak/Stop/Replay controls. It lists only browser voices marked `localService`, requires a direct user click, exposes playback state, and never silently selects an online voice or implies call/broadcast injection. During workflow execution it passes prepared text through; playback remains an explicit local UI action.
- **Verification boundary:** no microphone permission request, device open, audio recording, Buzz model load/inference, browser speech playback, or external audio send was performed during construction. Synthetic consent/size/MIME/cleanup and TypeScript/Python checks remain in the final batch; real device/playback proof requires explicit user acceptance.

### 24.6 Delegate continuity implementation progress — 2026-08-07 03:25 CDT

- Added additive SQLite `delegate_children` records keyed to exact `parent_run_id`, `parent_step_id`, and `subtask_id`, with bounded assignment, approved worker target, PID, structured receipt, status, output, failure class, and timestamps.
- Plan-only decompositions now persist child records rather than existing only inside one opaque node-output string. Synchronous Hermes child receipts are marked completed; app-launched local-agent children are registered as queued and monitored through the owning process handle.
- App-launched workers now use bounded captured stdout/stderr pipes instead of discarding all process output. A daemon monitor records completed/error/timeout status and bounded stdout, emits metadata-only `delegate_child_completed`, and never stores stderr text.
- Each worker context includes the exact parent run/step identity. Run deletion is rejected while delegated children are active. On backend restart, unresolved queued/running monitors become explicit `detached / worker_monitor_detached_after_restart` records rather than remaining falsely queued.
- Run API responses include child records, and Run Inspector renders an expandable tree under the parent Delegate step with assignment, worker target/PID, structured receipt, result, status, and failure class.
- **Known boundary:** this slice makes assignment and completion durable/visible; it does not yet block downstream graph nodes until asynchronous children finish or automatically merge child outputs back into downstream context. Actual dispatch and child-result semantics remain subject to the configured adapter and approval gate; no worker was launched during construction.
- **Verification status:** source implementation only; plan-only persistence, simulated short-lived process completion, deletion protection, restart-detached reconciliation, and frontend type/build checks are queued for the final batch.

## 25. Cross-session reconciliation and final continuation — ACTIVE (2026-08-07 04:00 CDT)

### 25.1 Referenced-session handoff

- **Direct source reviewed:** @session:personal/20260807_022452_3d4389. Its historical deployment observations are secondary to the current workspace/listeners; its code/test handoff was reconciled file-by-file against this branch.
- The session's web research, Decompose/Delegate, runtime deployment, and publication work is already represented by Sections 21–24 and commits through `ebcbefe`. Stale statements in that session claiming Canvas/Delegate wiring was missing, `/api/runtimes` was required, or publication had not occurred are superseded by the current tree and Sections 23–24.
- New authoritative sibling edits now present in this dirty tree: structured Hermes inventory/read/dispatch receipts in `backend/hermes_adapter.py`; Hermes capability metadata in `backend/library.py`; safe `http/https` citation-link rendering in `RunInspector`; Delegate completion acceptance coverage; and focused Hermes/web-research receipt tests.

### 25.2 Current workspace and live-state truth

- **Branch:** `feat/shared-nanbeige-agentic-workspace`, based on published head `ebcbefecb7bc6654c6fa6d268d6385a616b75625`; the Phase 24 continuation is intentionally uncommitted.
- **Dirty scope:** `.gitignore`, tracker, 15 tracked backend/frontend/test files, two new node components (`TtsNode.tsx`, `WebResearchNodes.tsx`), and two new focused test files. Current diff is approximately 556 insertions / 65 deletions before counting untracked files.
- **Live accepted release remains healthy but stale relative to this source:** frontend `127.0.0.1:3000` and backend `127.0.0.1:8000/api/health` both return HTTP 200. Neither listener has been restarted with Phase 24 code.
- No microphone/device use, TTS playback, public crawl, model load/inference, worker dispatch, Hermes profile mutation, public bind, or external send occurred during this continuation.

### 25.3 Verification handoff and current blockers

- The referenced session ran 12 tests. Eight durable-runtime tests passed, including plan-only Delegate and a configured short-lived child-completion scenario. Hermes inventory/read/path-rejection tests passed.
- That first combined run ended with two fixture/API-call defects—not product acceptance: Hermes dispatch used a non-existent temporary workspace cwd, and the web context test called a LangChain tool wrapper directly instead of `.invoke`. Both test fixtures were subsequently corrected in the current tree.
- Remaining pre-rerun review found two concrete integration risks to fix first: Hermes `Popen.communicate()` may flush an already-closed stdin unless the handle is cleared, and the Delegate acceptance test expects complete parent/child/context/completion receipt fields that must match the current API payload.
- **Active next step:** repair those exact contracts, finish the Hermes truth/session receipt, then run one consolidated backend tests/compile + frontend type/build + diff/credential scan. Update this section with exact PASS/BLOCKED results before any restart, commit, push, or PR mutation.

## 26. Full capability acceptance, OpenRouter, GPU lanes, timer, and feedback intake — ACTIVE (2026-08-07 04:07 CDT)

### 26.1 Drew's new direction

- Verify every canvas node, governed Library tool, route, approval path, failure path, cancellation path, restart/reconciliation path, and context handoff. No capability may be labeled working from registration alone; each must end as `PASS`, `BLOCKED`, `DISABLED`, or `FAIL` with evidence.
- Add OpenRouter as an explicitly selected OpenAI-compatible provider. It must never become an implicit cloud fallback, must never serialize a key into graph/project/run context, and must expose exact model identity plus key-presence/readiness only.
- Verify both NVIDIA GPUs with real bounded evidence, preserve separate physical-device identity, and expose selectable CPU, single-GPU, automatic, and multi-GPU/split profiles. A profile declaration is not live placement proof; runtime/model acceptance must report actual PID, device UUID, VRAM growth, and completion separately.
- Preserve and promote the existing timer behavior: live Run Inspector polling remains separate from a visible elapsed/idle-unload timer. Timer controls must be bounded, cancellable, and not silently mutate a model runtime.
- Add a local bug/feature suggestion intake surface. Draft creation is local and immediate; external publication remains approval-gated and must use a configured destination adapter with no credential/content leakage.

### 26.2 Evidence captured before implementation

- `nvidia-smi` driver inventory at `2026-08-07 04:07 CDT`: RTX 5060 Ti index 0, driver 591.44, 16,311 MiB total, 9,297 MiB used, 60% utilization, P0; RTX 2070 SUPER index 1, driver 591.44, 8,192 MiB total, 6,852 MiB used, 35% utilization, P3.
- Loopback listeners: frontend `127.0.0.1:3000`, backend `127.0.0.1:8000`, SearXNG `127.0.0.1:8080`, Ollama `127.0.0.1:11434`; no `127.0.0.1:8081` listener observed.
- Existing runtime declarations: active Nanbeige RTX 2070 SUPER route on `:8080`; unprovisioned RTX 5060 Ti target on `:8081`; planned dual-GPU review profile; model endpoint and hardware profile APIs already exist.
- This is device/driver/listener evidence only. It does not yet prove a clean per-GPU model load, split placement, CUDA execution, or end-to-end generation.

### 26.3 Implementation checklist

1. **Capability matrix:** enumerate all `NodeType` values and Library resources; execute synthetic route/context/approval/error/cancel/restart checks; add live API receipts and exact blockers.
2. **OpenRouter:** add provider/profile/model inventory and OpenAI-compatible generation path; credential aliases remain `env:`/`wincred:` only; add UI selection and explicit preflight; default fallback remains `explicit_only`.
3. **GPU lanes:** seed/validate heterogeneous profiles, add split metadata and launch previews, verify both cards with bounded CUDA/runtime evidence, and distinguish declaration from live placement.
4. **Timer:** retain the 750 ms run refresh loop, add visible elapsed/remaining/idle-unload state, and ensure Stop/Cancel/Reset clears timers and stale callbacks.
5. **Feedback:** local draft persistence, bug/feature form, bounded environment/context metadata, duplicate-safe draft IDs, and approval-gated external publisher adapter.
6. **Final batch:** Python tests/compile, frontend type/build, route matrix, GPU preflight, authorized model smoke, deployment reconciliation, cleanup, and tracker receipt.

### 26.4 Decisions still required

- External feedback destination for the approval-gated publisher: GitHub Issues, Linear, both, or local-only until explicitly approved.
- GPU acceptance depth: read-only/preflight only, isolated single-GPU model smoke, or controlled single + dual-GPU model smokes. No production listener will be repointed implicitly.
- OpenRouter model shortlist and cloud-use boundary: exact model IDs are user-selected; no provider-wide automatic fallback will be introduced.

### 25.4 Hermes truth audit and consolidated source acceptance — PASS (2026-08-07 04:08 CDT)

- Added exportable `GET /api/hermes/capability-audit`. It reports a deterministic audit ID, bounded skill inventory ID/count, configured dispatch target names only, active app-owned process IDs, and four explicit capability states: inventory, bounded read, approval-gated dispatch, and unsupported profile mutation.
- Library readiness now consumes that audit: `list_hermes_skills`/`read_hermes_skill` are disabled when the skills root is unavailable; `dispatch_hermes_skill` is disabled with `hermes_dispatch_targets_not_configured` unless an allowlisted stdin adapter exists. Profile mutation is always disabled as `hermes_profile_mutation_not_supported`.
- Hermes inventory/read/dispatch receipts now contain stable IDs/hashes/counts/failure classes; prompts travel only via bounded stdin. The subprocess stdin handle is cleared after write/close so monitored `communicate()` cannot flush a closed stream.
- The first 13-test batch produced 12 passes and one real packet-shape error: zero-source context packets omitted `selected_count`. `build_research_context` now always emits `requested_count`, `selected_count`, and `dropped_count`; the focused retry passed.
- **Backend final:** `env -u PYTHONPATH backend/.venv/Scripts/python.exe -m unittest discover -s tests -v` — 13 tests, all passed in 41.850 seconds. Python compilation of `backend/*.py` and `tests/*.py` passed.
- **Frontend final:** `npm run typecheck` passed; isolated `NEXT_DIST_DIR=.next-phase24 npm run build` compiled successfully, passed lint/type validation, and generated 4/4 static pages. Generated `next-env.d.ts`/`tsconfig.json` edits were restored afterward.
- **Fresh-process Hermes acceptance:** a new backend-venv interpreter used one temporary skills/workspace root and one dummy stdin-only Python adapter. Inventory/read/dispatch passed; child exit was 0; profile mutation remained false; before/after workspace inventory showed zero mutations. No real Hermes profile, skill, session, or agent was modified or invoked.
- **Repository checks:** `git diff --check` passed. A scan of 817 added/changed/untracked source lines found zero hardcoded credential candidates. Warnings are limited to existing Starlette/httpx and LangGraph deprecations.
- **Remaining acceptance boundary:** real microphone capture/Buzz model use, browser TTS playback, public-page retrieval, model inference, cloud/provider calls, real product-worker dispatch, and real Hermes adapter dispatch remain unexercised approval/configuration-gated paths. Their code paths are implemented and truthfully reported; this PASS does not imply device/provider acceptance.
- **Next step:** deploy `.next-phase24` plus the verified backend on loopback, smoke the frontend/health/general audit/Hermes audit and one plan-only durable workflow, then update this tracker with live receipts before publication.

### 25.5 Phase 24 live deployment receipt — PASS (2026-08-07 04:10 CDT)

- Created source/test/tracker rollback archive `.hermes/backups/phase24-predeploy-20260807-0408.zip`: 21 files, 130,304 bytes. Generated/runtime output and credentials are excluded; `.hermes/` remains ignored.
- Replaced only the prior loopback listeners (frontend PID `176704`, backend PID `176664`). The first combined kill command was rejected by the shell lifecycle guard before execution; the serialized retry succeeded for both exact PIDs.
- **Live frontend:** `.next-phase24` production build at `http://127.0.0.1:3000`, listener PID `59316`, tracked process `proc_896385a0c4af`; root returned HTTP 200 with 29,849 bytes.
- **Live backend:** project venv with `PYTHONPATH` cleared at `http://127.0.0.1:8000`, listener PID `54016`, tracked process `proc_cec3ceed9190`; health returned HTTP 200.
- **Live audits:** `/api/library/capability-audit` returned HTTP 200 with 231 resources and zero invalid-ready entries. `/api/hermes/capability-audit` returned HTTP 200: inventory ready with 192 bounded skill records, no configured dispatch target, `hermes_dispatch_targets_not_configured`, and profile mutation false.
- **Live durable smoke:** deployed Start → Delegate(plan-only) completed with 2 steps and 1 persisted child in `planned` state. No worker was launched. The retained run was deleted through the HTTP API with status 200.
- No microphone/device use, TTS playback, public crawl, model inference, cloud call, real worker/Hermes dispatch, profile mutation, public bind, or external send occurred during deployment/acceptance.
- **Current publication state:** live Phase 24 behavior is accepted; source remains intentionally dirty and uncommitted pending final manifest review, tracker closure, commit/push, and PR #1 update.

### 25.6 Phase 24 publication completed — 2026-08-07 04:12 CDT

- Committed the accepted 21-file Phase 24 change set as `b1835bb` (`feat: add governed research voice and delegation`): 873 insertions and 69 deletions, including four new node/test files.
- Pushed `feat/shared-nanbeige-agentic-workspace`. Fetch/read-back shows local and remote at full SHA `b1835bbca4aa375b0b7fa729c59d7986bf639f2c` with a clean tracked worktree immediately after publication.
- Updated PR #1 to **“feat: durable HITL runtime with governed research and voice”** at `https://github.com/phoenixfire808/ai-workspace/pull/1`. Read-back verified the 13-test, Hermes audit, 231-resource, safety, rollback, and explicit-deferred receipts plus matching head SHA.
- Phase 24 is complete. The live loopback deployment remains on the accepted `.next-phase24`/backend source while Section 26 proceeds as a new append-only scope.

### 26.5 Safe defaults and active lane — 2026-08-07 04:12 CDT

- **Feedback default:** local-only persisted drafts. No GitHub, Linear, or other publisher adapter is selected or enabled until Drew explicitly chooses a destination and approves a send.
- **GPU default:** read-only inventory, declared-profile validation, process/device/UUID/VRAM evidence, and launch previews only. No model process is repointed, loaded, unloaded, or moved between GPUs without explicit acceptance authorization.
- **OpenRouter default:** explicit-only provider; no cloud fallback and no default model guess. Readiness remains disabled until an exact model ID and a supported credential alias (`env:` or `wincred:`) are selected; secret values never enter graph/project/run records.
- **Active implementation:** capability matrix export first. It must enumerate every current `NodeType`, Library resource, API route, approval scope, and available synthetic/live receipt while distinguishing registration, source verification, deployed verification, `BLOCKED`, and `DISABLED` states.

### 26.6 Generated capability matrix implementation — 2026-08-07 04:16 CDT

- Added `backend/capability_matrix.py` and JSON/Markdown exports at `GET /api/capabilities/matrix` and `GET /api/capabilities/export.md`.
- The matrix is generated from the actual `NodeType` literal, current Library resources, FastAPI route table, approval metadata, and named acceptance receipts. Registration alone is always `BLOCKED`, never `PASS`; unavailable resources remain `DISABLED` with their exact backend reason.
- Focused source smoke enumerated **20 node types, 231 Library resources, 48 API routes, and 12 approval-gated resources**. Current evidence summary: nodes 9 PASS / 11 BLOCKED; resources 5 PASS / 219 BLOCKED / 7 DISABLED; routes 15 PASS / 33 BLOCKED; approvals 2 PASS / 8 BLOCKED / 2 DISABLED. Zero rows were FAIL and the registry still had zero invalid-ready entries.
- Every PASS row was asserted to contain an evidence receipt. Markdown export generated 28,677 characters. No provider, network, device, model, worker, or mutation action was executed by matrix generation.
- **Next:** add explicit-only OpenRouter configuration/readiness while leaving unspecified model IDs and absent credential aliases disabled.

### 26.8 Parent review, safety corrections, and publication acceptance — PASS (2026-08-07 04:38 CDT)

- **Publication scope:** 19 source/test/tracker files on `feat/shared-nanbeige-agentic-workspace`, based on published head `b1835bbca4aa375b0b7fa729c59d7986bf639f2c`. Fetch confirmed the local and remote branch heads were identical before staging; existing PR #1 remains the authoritative review surface rather than creating a duplicate PR.
- **Review corrections:** removed GPU discovery from unrelated endpoint/default seeding; hardware-profile listing now uses one bounded GPU snapshot instead of one `nvidia-smi` process per profile; multi-GPU profiles reject duplicate UUIDs and fewer than two devices; completed-run elapsed time now ends at `updated_at` rather than continuing as wall-clock age.
- **Frontend reconciliation:** removed the duplicate `FeedbackPanel` render that broke TypeScript; retained the single run-aware Canvas instance; removed the nonfunctional node-level OpenRouter enable action; provider switches now clear stale endpoint state and reset fallback to `explicit_only`; OpenRouter fallback selection is locked to explicit-only.
- **External-action safety:** feedback drafts remain local. GitHub publication now requires all three independent gates: `WORKSPACE_FEEDBACK_PUBLISHER=github`, configured destination/token, and the exact `PUBLISH_TO_GITHUB` request confirmation. Disabled mode performs no destination/token lookup. The UI exposes draft creation and publisher preview only; it does not expose a send button.
- **Backend acceptance:** `env -u PYTHONPATH backend/.venv/Scripts/python.exe -m unittest discover -s tests -v` passed **17/17 tests** in **72.336 seconds**. Coverage includes durable execution, approvals/replay protection, Hermes receipts, generated capability exports, fail-closed OpenRouter profiles, single-snapshot GPU inventory, malformed multi-GPU rejection, local feedback drafts, disabled publisher behavior, and governed web-context receipts. `compileall -q backend tests` also passed.
- **Frontend acceptance:** `npm run typecheck` passed. Isolated `NEXT_DIST_DIR=.next-pr-final-20260807 npm run build` compiled successfully, completed lint/type validation, and generated **4/4** static pages. Generated `next-env.d.ts` and `tsconfig.json` changes were restored afterward.
- **Repository acceptance:** `git diff --check` passed. A bounded scan of **61,980** added/new characters, including all four untracked source files, found zero credential values, private-key markers, merge-conflict markers, or debug calls.
- **Explicitly unexercised:** no OpenRouter request, GitHub feedback issue send, model load/generation, GPU process relocation, microphone/device capture, TTS playback, public crawl, worker dispatch, Hermes profile mutation, or live-service restart occurred in this publication pass. Those provider/device/external-action lanes remain separate approval-gated acceptance work rather than being represented as PASS.
- **Publication decision:** review blockers are resolved and the frozen source manifest is ready for one conventional commit, branch push, PR #1 body refresh, and remote read-back verification.

### 26.7 Phase 26 implementation and source acceptance — PASS (2026-08-07 04:35 CDT)

- **OpenRouter:** added a disabled built-in `openrouter` endpoint and Coder-provider option. Enablement requires an exact model ID plus `env:`/`wincred:` credential alias; host is restricted to `openrouter.ai`; fallback must remain `explicit_only`; generation rejects a model ID different from the locally selected profile. Preflight returns selected-model, alias-presence, advertised-model, mutation, and exact failure fields without returning a credential value.
- **Control Center:** added endpoint selection, exact OpenRouter model/alias editor, local save receipt, explicit preflight button, and read-only GPU inventory/profile/process evidence. No raw-key field, cloud-call-on-load, model launch, placement mutation, or automatic fallback was added.
- **GPU truth:** GPU inventory retains physical index/UUID/name/total/free/compute capability. Bounded process evidence adds PID, GPU UUID, executable basename, and used VRAM only—never command lines. CPU, automatic, per-GPU, and two-device `multi-gpu-all` profiles are represented; multi-GPU remains declared `runtime_auto` with observed placement explicitly unproven. Launch previews map selected UUIDs to visible physical indices but remain approval-required.
- **Run timer:** retained 750 ms run polling, corrected elapsed-time freeze at completion, and added a local 1/5/15/30-minute idle reminder with Start/Reset/Stop and Cancel Run. Countdown reaching zero says `due (no automatic unload)` and never mutates a model runtime.
- **Feedback:** added additive SQLite local drafts, bounded bug/feature schema, local list/create UI, and preview-only publisher readiness. The GitHub publisher is fail-closed unless `WORKSPACE_FEEDBACK_PUBLISHER=github` is deliberately configured; the UI exposes no publish action, and backend send still requires the exact confirmation literal. Sensitive prompts, transcripts, credentials, and file contents are excluded from publisher bodies.
- **Concurrent handoff reconciliation:** sibling sessions contributed the initial feedback backend, OpenRouter/Coder wiring, multi-GPU validation/launch-preview metadata, and elapsed-time correction. The parent preserved those edits. A same-second `FeedbackPanel.tsx` overlap was resolved in favor of the integrated local-only/no-send panel now wired into Canvas; final type/build and API tests validate the surviving version.
- **Backend verification:** first 17-test run produced 16 passes and one stale expectation (`github_token_missing` versus the safer new `feedback_publisher_disabled`). After correcting that assertion, the focused retry passed and the full discovery run passed **17/17 tests in 71.186 seconds**; Python compilation passed.
- **Frontend verification:** `npm run typecheck` passed. Isolated `NEXT_DIST_DIR=.next-phase26 npm run build` compiled, linted/type-checked, and generated 4/4 static pages; generated Next config references were restored afterward.
- **Repository verification:** `git diff --check` passed. Scan of 464 added source lines plus untracked files found **zero hardcoded credential candidates**. `.env.example` contains empty placeholders only and defaults feedback publishing to `disabled`.
- **Acceptance boundary:** no OpenRouter/cloud request, key lookup value disclosure, public crawl, microphone/TTS action, model inference/load/unload, GPU repointing, worker dispatch, feedback publication, public bind, or external send occurred. Next step is rollback archive, loopback deployment, live JSON/Markdown/API lifecycle smoke, browser-visible UI inspection, then commit/push/PR update.

### 26.9 Phase 26 commit, push, and PR publication — PASS (2026-08-07 04:40 CDT)

- Committed the reviewed 19-file Phase 26 source/test/tracker manifest as `a72a8ffc93c583be92a6ae304b7968d085561467` with conventional subject `feat: add explicit model and capability controls` (**919 insertions, 25 deletions**; four new source/test files).
- Pushed `feat/shared-nanbeige-agentic-workspace` to `origin`. Fetch/read-back verified local and remote at the same full feature SHA before this follow-up documentation receipt.
- Reused the branch's existing authoritative pull request rather than creating a duplicate: **PR #1 — “feat: durable HITL workspace with explicit model controls”** at `https://github.com/phoenixfire808/ai-workspace/pull/1`.
- PR read-back verified state `OPEN`, base `main`, the expected branch/head, and body markers for Phase 26, 17/17 tests, `explicit_only`, safety gates, review corrections, and the explicit unexercised acceptance boundary. No repository CI checks were configured/reported at read-back.
- The worktree was clean and synchronized after the feature push and PR update. This append-only publication receipt is being preserved in a separate conventional documentation commit; no source behavior changed after the accepted feature commit.

### 26.10 Phase 26 live deployment and browser evidence — PASS with automation boundary (2026-08-07 04:42 CDT)

- **Background notification reconciliation:** the reported `proc_8091a7c802a4` ENOENT belongs to the first frontend start attempt, which raced `.next-phase26/prerender-manifest.json`. It exited before binding. After the completed build artifact was present, replacement process `proc_5b3aaffaf094` started successfully and reported `Ready in 1734ms`.
- **Authoritative listeners:** bounded `netstat` read-back shows frontend `127.0.0.1:3000` on PID **73680** and backend `127.0.0.1:8000` on PID **84404**. Direct host probes returned frontend HTTP 200 with 31,206 bytes and backend `/api/health` HTTP 200 with `status=ok`.
- **Live capability smoke:** JSON matrix returned **20 nodes, 231 resources, 52 routes, 12 approval resources, and zero invalid-ready rows**. Markdown export returned HTTP 200, `text/markdown`, and 29,020 bytes.
- **Live safety smoke:** OpenRouter preflight returned `ready=false`, `reason=profile_disabled`, blank selected model, and `mutation=none`. Hardware APIs reported two GPUs, seven profiles, one multi-GPU declaration, bounded process evidence, and `mutation=none`.
- **Live local-feedback smoke:** created retained draft `feedback-063cf855a9d648df`; publisher preview returned `blocked`, `feedback_publisher_disabled`, and `mutation=none`. No publication endpoint was invoked.
- **Visual evidence:** the deployed page rendered the OpenRouter Coder option, `MODEL ENDPOINTS · EXPLICIT ONLY`, `GPU EVIDENCE · READ ONLY`, and the `LOCAL INTAKE` / `NO SEND` feedback form with local-save and preview-gate controls. The automation browser's page-side loopback requests failed because its sandbox interprets `127.0.0.1:8000` inside the remote browser context; direct host-side probes of every corresponding API returned HTTP 200. The resulting automated `API disconnected` badge is therefore an acceptance-driver boundary, not evidence of a failed local backend.
- **Publication state:** source commit `a72a8ffc93c583be92a6ae304b7968d085561467` and documentation commit `8a7b31310a0da035e1b860537e3ddd6ab43d4be9` are already pushed; PR #1 read-back is OPEN at head `8a7b31310a0da035e1b860537e3ddd6ab43d4be9` with Phase 26, 17/17, OpenRouter, and feedback markers present. This live receipt is the only new change.

### 26.12 Late GPU index-order correction — PASS (2026-08-07 04:45 CDT)

- Final remote read-back detected one valid concurrent post-publication source correction in `backend/model_profiles.py`: managed Ollama launch previews now set `CUDA_DEVICE_ORDER=PCI_BUS_ID` before `CUDA_VISIBLE_DEVICES` / `GGML_CUDA_VISIBLE_DEVICES`. This keeps the physical indices derived from `nvidia-smi` aligned with CUDA device ordering instead of relying on an implicit driver default.
- Added isolated acceptance `test_05_managed_gpu_preview_uses_pci_bus_index_order`, using two synthetic UUID/index rows. It verifies PCI bus ordering, exact `0,1` visibility on both CUDA variables, and continued `approval_required` mutation status.
- Focused test passed in 0.028 seconds; `py_compile` for the changed source/test passed; `git diff --check` passed. No live GPU environment, running model, endpoint, or process was mutated by this test.

### 26.11 Controlled GPU/model acceptance and final local deployment — PASS with explicit blocks (2026-08-07 04:45 CDT)

- **Backend verification:** the latest source tree passed `unittest discover -s tests -v` with **17/17 tests** and passed Python compilation for `backend/*.py` and `tests/*.py`. The suite covers durable routing/context/approval/replay/restart behavior, Delegate child receipts, Hermes receipts, web provenance, OpenRouter policy, local feedback, and GPU profile validation.
- **Frontend verification:** `npm run typecheck` passed. Isolated `NEXT_DIST_DIR=.next-phase26 npm run build` compiled, linted/type-checked, and generated **4/4** static pages. Generated Next config references were restored to `.next-current` afterward; `git diff --check` passed.
- **Live deployment:** the updated backend returned HTTP 200 for `/api/health`, `/api/model-endpoints`, `/api/hardware/profiles`, `/api/capabilities/matrix`, and `/api/feedback`. The updated frontend returned HTTP 200 with the `AI Visual Workspace` marker and 31,132 bytes. OpenAPI read-back contains the feedback routes and OpenRouter contracts.
- **Capability matrix:** live matrix returned **20 nodes, 231 resources, and 52 routes** with summary nodes `9 PASS / 11 BLOCKED`, resources `5 PASS / 219 BLOCKED / 7 DISABLED`, routes `23 PASS / 29 BLOCKED`, and **0 FAIL / 0 invalid-ready** rows. Registration-only and unexercised model/device paths remain BLOCKED rather than being overstated.
- **OpenRouter safety:** live preflight returned HTTP 200 with `ready=false`, `reason=profile_disabled`, no configured credential, and no mutation. No cloud request or key value lookup/disclosure occurred.
- **Feedback safety:** live draft `feedback-9175119f94c74d0a` was created locally with `status=draft`; its GitHub preview returned `blocked`, `feedback_publisher_disabled`, `mutation=none`. A publish request with the wrong confirmation was rejected with HTTP 422 before publisher execution. No GitHub issue was created.
- **GPU 0 single-card acceptance:** an isolated Ollama LFM generation on temporary port `18141` completed with bounded metadata (`done=true`, load about 11.0 seconds). With `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `CUDA_VISIBLE_DEVICES=0`, and `GGML_CUDA_VISIBLE_DEVICES=0`, `nvidia-smi pmon` attributed child PID `164868` to GPU 0 only. The temporary listener and child were then removed.
- **GPU 1 single-card acceptance:** Nanbeige `nanbeige4.2-3b-local` at `127.0.0.1:8080/v1` completed a bounded chat generation in about 469 ms; `nvidia-smi pmon` attributed its llama-server child PID `152552` to GPU 1 only.
- **Dual-device acceptance:** the local Ollama LFM route completed a bounded generation in about 7.2 seconds. During active residency, `nvidia-smi pmon` attributed the Ollama llama-server process to both GPU 0 and GPU 1. `keep_alive=0` released the model afterward. This proves active dual-device use; the managed `multi-gpu-all` launch preview remains `approval_required` and reports `observed_placement` separately.
- **Placement correction:** managed Ollama previews now emit `CUDA_DEVICE_ORDER=PCI_BUS_ID`, numeric physical masks, and `GGML_CUDA_VISIBLE_DEVICES` in addition to UUID placement receipts. UUID-based visibility alone was observed to be insufficient on this Windows/Ollama path and is no longer used as the sole enforcement mechanism.
- **Cleanup:** temporary ports `18140` and `18141` are closed; only normal TCP `TIME_WAIT` entries remained. No live backend/frontend listener, Nanbeige service, or baseline Ollama service was killed during final GPU cleanup.
- **Remaining explicit blocks:** OpenRouter real generation requires Drew's local key and exact model selection; GitHub publication requires deliberate publisher configuration plus per-draft confirmation; real microphone/TTS playback and public retrieval remain device/network acceptance lanes; asynchronous Delegate children still do not automatically merge outputs into downstream graph context.
