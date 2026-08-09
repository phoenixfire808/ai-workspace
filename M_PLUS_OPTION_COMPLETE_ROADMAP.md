# Refactor Workflow Studio Option-Complete Product Roadmap and Branch-Worker Integration Plan

> **For Hermes and branch workers:** This project remains parent-owned by default. Do not spawn or dispatch workers unless Drew explicitly authorizes them. When Drew adds branch workers, each worker must use a separate branch/worktree, claim disjoint files, read this roadmap plus `PROJECT_TRACKER.md`, and publish a complete handoff receipt before integration.

**Status:** PHASE 0 ACTIVE · PARENT-OWNED IMPLEMENTATION
**Roadmap baseline:** `feat/shared-nanbeige-agentic-workspace` at `2999857abe9645e4986d43e10e78864d86db1d68`; documentation checkpoint follows from this baseline
**Prepared:** 2026-08-07 04:49 CDT
**Product:** M⊕ AI Visual Workspace
**Goal:** Make every meaningful product capability explicitly selectable, honestly available or unavailable, locally inspectable, safely approval-gated, testable, and reversible without scattering inconsistent option logic across the application.

**Architecture:** Add one option-definition and option-resolution layer above the existing SQLite-backed durable runtime, capability registry, model endpoint profiles, hardware profiles, runtime profiles, Control Center, and node settings. The option layer becomes the source of truth for API schemas, UI controls, defaults, prerequisites, scope resolution, safety gates, evidence state, and rollback metadata. Existing working modules remain the implementation seams; this roadmap does not restart the application or fork parallel replacements.

**Tech stack:** Python 3.11, FastAPI, Pydantic, SQLAlchemy/SQLite, LangGraph, Next.js 15, React, TypeScript, React Flow, local SearXNG, Ollama, local OpenAI-compatible runtimes, Windows NVIDIA tooling.

**Testing policy:** Build in bounded batches. Defer broad tests until the end of each integrated phase, then run one consolidated backend/frontend batch and one focused real smoke. Real microphone, TTS, model/GPU, public network, worker dispatch, cloud, publisher, process-control, and upgrade mutations are separate approval-gated acceptance lanes.

---

## 0. Canonical artifact map

| Artifact | Purpose | Mutation rule |
|---|---|---|
| `M_PLUS_OPTION_COMPLETE_ROADMAP.md` | Current product specification, option catalog, phases, worker protocol, and acceptance gates | Update when requirements, ordering, defaults, or ownership rules change |
| `PROJECT_TRACKER.md` | Append-only execution history, Now/Done/Next/Blocked checkpoint, worker ledger, receipts, blockers, integration state | Never erase historical receipts; append corrections and superseding state |
| `.hermes/plans/2026-08-07_044931-option-complete-workspace-roadmap.md` | Hermes plan pointer and execution handoff | Keep synchronized with the tracked roadmap path and baseline |
| `/api/capabilities/matrix` | Live evidence state for nodes, resources, routes, and approvals | Generated from source/runtime evidence; registration alone is never PASS |
| PR #1 | Branch review and publication surface | Update after accepted scoped commits; do not open duplicate PRs for the same head branch |

### Source-of-truth order

1. Drew’s latest explicit direction.
2. This roadmap for current product contracts and phase ordering.
3. `PROJECT_TRACKER.md` for latest verified implementation and worker state.
4. Current source/API output for actual behavior.
5. Historical plan/README text only when it still matches the four sources above.

If two sources conflict, the parent records the conflict in `PROJECT_TRACKER.md`, verifies current source/runtime behavior, and updates this roadmap before assigning more workers.

---

## 1. What “options for everything” means

A feature is **option-complete** only when every meaningful choice is explicit and carries enough metadata to be used safely. A decorative dropdown that cannot enforce its selection does not count.

### 1.1 Required option metadata

Every option definition must expose:

| Field | Meaning |
|---|---|
| `option_id` | Stable machine identifier |
| `category` / `subgroup` | Navigation and filtering |
| `label` / `description` | User-facing purpose and consequence |
| `scope` | Global, user, project, workflow, node, run, endpoint, hardware profile, or one-shot action |
| `kind` | Boolean, enum, number, text, secret alias, ordered list, capability reference, or action |
| `choices` | Allowed values with labels; dynamic choices identify their inventory source |
| `default` | Explicit safe default, never an implicit provider guess |
| `current_value` | Resolved value after scope inheritance |
| `source_scope` | Where the resolved value came from |
| `status` | `ready`, `blocked`, `disabled`, `experimental`, or `deprecated` |
| `prerequisites` | Exact missing runtime, model, credential alias, device, listener, approval, or evidence |
| `effect` | Read-only, local state write, file mutation, process mutation, device action, network retrieval, cloud request, or external publication |
| `approval_scope` | Required approval class, if any |
| `persistence` | Ephemeral, run, workflow, project, profile, or global |
| `evidence` | Source, synthetic test, live API, device, provider, or external receipt |
| `privacy_cost` | Local/private, sends content, estimated/known cost, or unknown |
| `rollback` | Reset, restore snapshot, stop process, unload model, revert file, or not applicable |
| `requires_restart` | None, frontend, backend, isolated runtime, or full app |
| `conflicts_with` | Mutually exclusive options or active profiles |

### 1.2 Standard control pattern

Where technically meaningful, controls should present:

1. **Off / Disabled** — capability cannot act.
2. **Auto** — application selects only from an explicitly bounded local set and reports the resolved choice.
3. **Explicit selection** — exact provider/model/device/profile/tool/strategy.
4. **Custom / Advanced** — only when validation and enforcement exist.
5. **Reset to safe default** — restores the documented default and shows the affected scope.

Do not add Auto when the selection could silently cross local/cloud, safe/unsafe, or read/write boundaries. Those transitions require explicit policy plus receipts.

### 1.3 Required UI behavior

- Basic controls show the safest commonly used choices.
- Advanced controls expose complete applicable options without pretending server-global settings are per-request.
- Disabled choices remain visible with exact reasons when that helps diagnosis.
- Every mutating choice shows effect, approval, and rollback before application.
- Every externally sending choice shows destination, content class, credential alias presence, cost status, and confirmation mode.
- Every model/device choice shows requested route separately from observed route/placement.
- Every selection can be inspected in the Run Inspector and retained context without storing credentials or sensitive raw content.

---

## 2. Current verified baseline

### 2.1 Repository and live evidence

| Area | Current evidence | Status |
|---|---|---|
| Branch | Local and remote synchronized at `2999857abe9645e4986d43e10e78864d86db1d68` | PASS |
| Nodes | 20 registered; 9 PASS, 11 BLOCKED, 0 FAIL | Mixed |
| Library resources | 231 total; 5 PASS, 219 BLOCKED, 7 DISABLED, 0 FAIL | Mixed |
| API routes | 52 total; 23 PASS, 29 BLOCKED, 0 FAIL | Mixed |
| Approval resources | 12 total; 2 PASS, 8 BLOCKED, 2 DISABLED | Mixed |
| Durable runtime | Run persistence, approvals, replay protection, branch/merge, context retention, plan-only delegation, and deletion accepted | PASS |
| GPU inventory | RTX 5060 Ti and RTX 2070 SUPER visible with stable physical index/UUID evidence | PASS |
| GPU execution | GPU 0, GPU 1, and active dual-device Ollama generation have bounded live receipts | PASS with profile limitations |
| OpenRouter | Profile/UI/preflight fail closed; no exact model/key configured; no cloud generation accepted | BLOCKED |
| Feedback | Local drafts and preview gate accepted; publication disabled by default; no external send accepted | PASS local / BLOCKED external |
| Terminal | Preview/classification only; no command execution | PASS preview / BLOCKED execution |
| Upgrade Center | Inventory and preflight only; no stage/activate/rollback execution | PASS read-only / BLOCKED mutation |
| Voice | File/local contracts implemented; real microphone and TTS playback not accepted | BLOCKED device acceptance |
| Research | Bounded fixtures and local SearXNG architecture exist; public retrieval/synthesis acceptance remains gated | BLOCKED live network acceptance |
| Delegate | Plan-only and child receipt paths exist; asynchronous child output does not automatically merge downstream | PARTIAL |

### 2.2 Current node inventory

`start`, `buzz`, `tts`, `planner`, `coder`, `file`, `task`, `agent`, `tool`, `runtime`, `review`, `chat`, `split`, `merge`, `context`, `plugin`, `delegate`, `search`, `research`, `source_context`.

Current PASS nodes: Start, File, Human Review, Chat Input, Split, Merge, Context, Plugin, and plan-only Delegate.
Current evidence-blocked nodes: Buzz, TTS, Planner, Coder, Task, Agent, Tool (varies by resource), Runtime (declaration is not placement proof), Search, Research, and Source Context live behavior.

### 2.3 Current endpoint/provider inventory

| Profile/provider | Current state | Default policy | Next honest option |
|---|---|---|---|
| Local Ollama | Enabled; exact installed models inventoried | Explicit route | Add explicit model chooser, placement policy, and observed-load receipt per node/workflow |
| Local Nanbeige | Enabled, exact `nanbeige4.2-3b-local` baseline | Explicit route | Preserve baseline and expose it as a protected profile |
| Local LFM | Disabled/not provisioned consistently across legacy/runtime declarations | Explicit route | Reconcile exact model/port identity before enabling |
| MiniMax | Existing explicit Coder option through legacy environment route | No fallback | Fold into endpoint-profile registry with secret alias and exact-model preflight |
| Ollama Cloud | Disabled; credential alias missing | Explicit route | Keep disabled until Drew selects it and approves real cloud acceptance |
| OpenRouter | Disabled; exact model blank; credential alias not configured | `explicit_only` | User selects exact model and local credential alias before one approved smoke |
| Custom Ollama/OpenAI-compatible | Backend profile kinds exist | Explicit route | Add governed create/edit/delete UI with URL/TLS/credential validation |

**Model selection rule:** Nanbeige remains the selected local deep-research synthesis model. Do not silently substitute Qwen or another installed Ollama model. Dynamic Ollama inventory is an option source, not permission to choose a model implicitly.

### 2.4 Current hardware/runtime inventory

Supported declarations: Auto, CPU, each discovered single GPU, ordered multi-GPU, local Ollama, protected Nanbeige RTX 2070 baseline, unprovisioned Nanbeige RTX 5060 target, planned Nanbeige dual-GPU profile, and unprovisioned LFM route.

Required distinction:

- **Split one model across both GPUs** and **independent model servers on separate GPUs** are different modes and must never share one ambiguous “dual GPU” switch.
- Requested visibility/profile and observed process placement are separate fields.
- User-managed baseline listeners are never treated as app-owned.

### 2.5 P0 data-hygiene finding

The live hardware-profile database currently contains acceptance artifacts `gpu-one`, `gpu-two`, and `test-pci-order` alongside real profiles. These are not valid user choices. Planning must include a backed-up, exact-ID cleanup/migration and stronger test isolation; this roadmap does **not** delete live data.

---

## 3. Product-wide option catalog

Status keys: **NOW** = enforced today; **NEXT** = first option-registry release; **LATER** = later phase; **GATED** = requires explicit approval/evidence.

### 3.1 Workspace, projects, and persistence

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Workspace action | New, Open, Save, Save As, Duplicate, Archive, Export, Import, Delete | Save manually; delete requires confirmation | Save/load NOW; rest NEXT/LATER |
| Save behavior | Manual, local autosave interval, save-on-run, snapshot-before-mutation | Manual + snapshot before protected mutation | NEXT |
| Project template | Empty, starter Coder, research, voice intake, file transformation, governed agent, custom template | Empty or explicit starter | NEXT |
| Run retention | Keep until delete, keep last N, age-based, archive/export then delete | Keep until explicit delete | NOW + NEXT options |
| Context retention | Full bounded, outputs only, metadata only, ephemeral | Full bounded local, sensitive classes excluded | NOW, expose NEXT |
| Export format | Project JSON, run JSON, Markdown report, capability Markdown, portable bundle | Project JSON + Markdown | LATER |
| Import conflict | New copy, replace after preview, merge graphs, cancel | New copy | LATER |
| Database maintenance | Inspect, backup, compact, restore, migrate | Backup before mutation | LATER/GATED |

### 3.2 Canvas and graph construction

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Node placement | Palette click, drag, double-click Library, template insertion | All enabled | NOW |
| Connection mode | Single edge, multiple fan-out, conditional route | Multiple validated edges | NOW |
| Branch mode | Parallel, sequential, conditional, chunked | Sequential for side effects; parallel for read-only | NOW |
| Edge priority | Integer order, manual reorder | Creation order | NOW |
| Condition type | Equals, contains, regex, route label | Route label / equals | NOW |
| Chunk strategy | Lines, paragraphs, JSON items, files, characters, estimated tokens | Paragraphs | PARTIAL/NEXT |
| Chunk size/overlap | Bounded numeric values | 2,000 chars / zero overlap | NOW |
| Merge strategy | Ordered concatenate, labeled object, JSON array, first success, model reduce | Ordered concatenate | PARTIAL/NEXT |
| Validation level | Schema only, schema + readiness, full preflight | Schema + readiness | NEXT |
| Canvas layout | Manual, auto-layout horizontal, vertical, fit selection | Manual | LATER |
| Node configuration view | Basic, Advanced, raw read-only JSON | Basic | PARTIAL/NEXT |
| Undo/redo | Canvas edit stack, saved snapshot restore | Local edit stack | LATER |

### 3.3 Run execution and failure behavior

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Run mode | Validate only, preflight, dry run, live | Preflight for protected workflows | NEXT |
| Approval policy | Preflight, per action, step through | Per action | NOW |
| Parallelism | 1–8 | 4, reduced by hardware lane | NOW |
| Error policy | Fail fast, continue independent branches, first success, collect all failures | Fail fast for mutations; collect for research | NEXT |
| Retry policy | None, fixed, bounded exponential, provider-guided | None for mutations; bounded for reads | NEXT |
| Timeout | Workflow, node, provider, tool-specific | Explicit bounded defaults | PARTIAL/NEXT |
| Cancellation | Cancel pending, cancel running cooperative, kill app-owned child after grace | Cooperative then app-owned kill | PARTIAL/NEXT |
| Resume | Resume pending approval/chat, retry failed node, fork from checkpoint | Resume pending only | PARTIAL/LATER |
| Idempotency | Strict replay rejection, explicit safe retry | Strict | NOW |
| Run priority | FIFO, user-priority, hardware-lane queue | FIFO | LATER |

### 3.4 Human review and approvals

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Decision | Approve once, deny, edit/re-preview, cancel run | Approve once | NOW |
| Reuse | None, approve remaining identical subject hashes | None | NOW |
| Approval expiry | Run lifetime, time bound, one action | One action + bounded expiry | NEXT |
| Scope | File mutation, process, model lifecycle, device, network retrieval, cloud inference, worker dispatch, external publication, profile change | Explicit per class | PARTIAL/NEXT |
| Reviewer | Drew only, named local role, policy engine plus Drew final | Drew only | NOW |
| Preview detail | Arguments, diff, endpoint/model, destination, content class, cost, rollback | Full applicable preview | PARTIAL/NEXT |
| Standing mandate | Off, exact allowlist, workflow-scoped, time-bounded | Off | LATER/GATED |

### 3.5 Model providers, models, and routing

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Provider | Nanbeige, Ollama, LFM, MiniMax, OpenRouter, Ollama Cloud, custom Ollama-compatible, custom OpenAI-compatible | Explicit local Nanbeige/Ollama | PARTIAL/NEXT |
| Exact model | Profile default, inventoried exact ID, validated custom ID | Exact ID | PARTIAL/NEXT |
| Endpoint profile | Saved endpoint list with readiness | Local explicit profile | NOW |
| Fallback policy | Explicit only, approved ordered list, cloud-enabled automatic | Explicit only | NOW default; others PARTIAL |
| Route strategy | User ordered, local preferred, cloud preferred, latency, VRAM fit, cost, quality benchmark | User ordered | PARTIAL/NEXT |
| Context length | Valid provider/runtime range | Profile default | NOW control / validation NEXT |
| Output tokens | 1–65,536 within model limit | 4,096 | NOW |
| Sampling | Temperature, top-p, top-k, min-p, repeat penalty, seed, stop strings | Profile defaults | PARTIAL/NEXT |
| Output format | Text, Markdown, JSON, JSON schema | Text | NOW |
| Thinking | Off, on, provider-native, budgeted | Provider/profile default | PARTIAL/NEXT |
| Keep-alive | Unload, bounded duration, persistent app-owned | 5 minutes | PARTIAL/NEXT |
| Request queue | Reject, FIFO, bounded priority | Bounded FIFO | LATER |
| Cost limit | None, per request, per run, per day | None; unknown cost cannot pass a constrained route | LATER/GATED |
| Privacy route | Local only, approved LAN, approved cloud | Local only | NEXT |

### 3.6 GPU, CPU, and runtime placement

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Hardware profile | Auto, CPU, RTX 5060 Ti, RTX 2070 SUPER, ordered both, custom saved | Auto or explicit protected local profile | NOW declarations |
| Placement strictness | Best effort, strict visible set, strict observed placement | Strict for named GPU profiles | NEXT |
| Dual-GPU meaning | Runtime auto split, explicit tensor/layer split when supported, independent servers, independent concurrent jobs | Independent servers for predictable ownership; runtime auto only when labeled | PARTIAL/NEXT |
| Device order | Physical PCI bus order, user order | PCI bus order | NOW |
| VRAM reserve | Per device numeric reserve | 1,024 MiB minimum, profile-specific | NOW field / enforcement NEXT |
| Max loaded models | Per runtime/profile | 1 | NOW field / enforcement NEXT |
| Concurrency | Per lane, per model, global | 1 model generation per constrained lane | NEXT |
| Context target | Profile/model-specific | Verified safe value | NEXT |
| Server ownership | User-managed, app-managed isolated, external LAN/cloud | Preserve user-managed; app owns only explicitly created processes | NEXT |
| Start mode | Manual, on-demand after approval, startup | Manual/on-demand | LATER/GATED |
| Unload mode | Manual, idle reminder, automatic approved policy | Reminder only until policy accepted | NOW reminder / LATER mutation |
| Observed evidence | PID, UUID, index, VRAM delta, processor split, endpoint/model | Required for PASS | PARTIAL/NEXT |

### 3.7 Node-specific options

Every one of the 20 node types gets an option sheet with defaults, constraints, readiness, and acceptance status.

- **Start:** input schema, required/optional fields, text/JSON/file-reference mode.
- **Buzz:** workspace file or live microphone, consent, model size, language, max duration, transcript retention, cancellation.
- **TTS:** off/manual, local voice, rate, pitch, volume, replay, output device, no automatic playback.
- **Planner:** provider/model, planning template, assumptions, output schema, tool visibility, context selectors.
- **Coder:** provider/model/endpoint/hardware, system prompt, generation controls, output contract, fallback.
- **File:** read/create/patch/rename/delete, path, encoding, size bounds, diff/approval behavior.
- **Task:** create/update/complete/archive, project scope, priority, notes, dependency.
- **Agent:** named adapter, plan-only/dispatch, timeout, workspace scope, approval, receipt.
- **Tool:** registry resource, generated argument controls, capability status, approval scope.
- **Runtime:** profile, preflight, inventory, app-owned lifecycle actions, strict placement.
- **Review:** prompt, required reviewer, timeout, default deny/cancel behavior.
- **Chat:** prompt, response schema, max chars, timeout, retry/skip policy.
- **Split:** branch/chunk mode, strategy, size, overlap, max chunks, concurrency.
- **Merge:** strategy, ordering, missing branch behavior, model reduce profile.
- **Context:** selector, fields, max chars, sensitive-class exclusion.
- **Plugin:** registered plugin, plugin-specific schema, approval class.
- **Delegate:** strategy, plan-only/approved dispatch, named worker target, max subtasks, concurrency, merge policy.
- **Search:** local SearXNG endpoint, query, categories, language, safe search, result/domain limits.
- **Research:** query set, page/domain limits, extraction toggle, synthesis model, citations, failure policy.
- **Source Context:** source selection, max chars, citation format, ranking, dedupe, truncation.

### 3.8 Research and web options

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Discovery | Local SearXNG only; explicitly supplied URL bypasses search | Local SearXNG | Architecture NOW; live acceptance gated |
| Search category | General and supported SearXNG categories | General | NOW |
| Safe search | 0, 1, 2 | 1 | NOW |
| Language | Exact supported code | `en` | NOW |
| Result/page/domain limits | Bounded numeric | 10 results, 12 pages, 2/domain | NOW |
| Extraction | Off, selected results, all within cap | Selected within cap | PARTIAL/NEXT |
| Private URL policy | Block, explicit local integration allowlist | Block public-research path | NOW |
| Synthesis | None, local Nanbeige, explicitly selected local model | Nanbeige | GATED live |
| GPU analysis | Off, rerank, embeddings, OCR, synthesis | Explicit selected task | LATER |
| Citations | Inline, footnote, evidence table, JSON | Evidence table + inline links | NEXT |
| Crawl cache | Off, session, project, TTL | Project TTL with clear/delete | LATER |

### 3.9 Voice and audio options

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Input | Workspace audio file, push-to-talk microphone, toggle recording | File until device acceptance | PARTIAL/GATED |
| Consent | Per capture, per session, disabled | Per capture | NOW contract |
| STT model | Installed local Buzz/WhisperCPP models | Explicit exact local model | PARTIAL |
| Language | Auto, exact language | Auto with visible result | LATER |
| Limits | Duration, byte size, MIME, silence timeout | Existing bounded caps | NOW |
| Transcript retention | Workflow context, project note, ephemeral, explicit delete | Workflow context + delete | NEXT |
| TTS | Off, manual Speak, Replay, Stop | Off/manual | NOW contract |
| Voice | Local browser voices only, exact selected URI | Explicit local voice | PARTIAL/GATED |
| Playback | Manual, node button, approved workflow action | Manual only | NOW |
| Output device | System default, exact local device | System default until device manager exists | LATER |

### 3.10 Tools, plugins, and Hermes

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Library presentation | All, ready, blocked, disabled, favorites, recent, category | Ready + blocked reason | NEXT |
| Tool invocation | Preview, add to canvas, run governed, disabled | Preview/add | PARTIAL |
| Argument editor | Generated controls, advanced JSON read-only, import saved preset | Generated controls | PARTIAL/NEXT |
| Plugin source | Built-in registry, signed local package, disabled manifest | Built-in only | NOW |
| Hermes skill action | Inventory, bounded read, named approved dispatch | Inventory/read | NOW/PARTIAL |
| Python tool | Disabled, bounded approved computation | Approval-gated | NOW |
| Agent adapter | Plan only, named local command, Hermes adapter, Codex adapter | Plan only | PARTIAL/GATED |
| Result merge | Manual review, concatenate, structured object, downstream context | Manual review initially | NEXT |

### 3.11 Branch workers and delegated execution

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Parent mode | Parent only, explicit branch workers | Parent only until Drew authorizes | NOW policy |
| Worker type | Read-only audit, backend writer, frontend writer, test/evidence, docs/integration | Exact named lane | NEXT workflow |
| Isolation | Separate worktree/branch, same worktree | Separate required | NEXT workflow |
| Dispatch | Plan only, explicit named worker, queued continuation | Plan only by default | PARTIAL |
| Session continuity | Resume same persisted session, explicit continued-from replacement | Resume same | Required |
| Merge strategy | Parent cherry-pick, parent merge, patch handoff | Parent-controlled | Required |
| Child output handling | Manual review, auto-merge after schema/evidence, reject | Manual review | PARTIAL/NEXT |
| Publication lock | Free, freeze requested, frozen, published | Parent-controlled | NEXT workflow |

### 3.12 Terminal and process control

| Mode | Behavior | Default approval | Roadmap state |
|---|---|---|---|
| Off | No terminal UI/action | None | Option NEXT |
| Preview | Classify command/cwd; no execution | None | NOW |
| Read-only execution | Strict allowlist, workspace cwd, capped output/time | None or workflow policy | Phase 4 |
| Governed task | Exact executable/argv/env profile, preview, approval, cancellation | Per action | Phase 4 |
| Managed process | Start/status/stop only app-owned process with PID receipt | Per lifecycle action | Phase 4 |
| Interactive PTY | Bounded session with explicit controls | Per session + blocked dangerous classes | Optional later phase |
| Network/process-control commands | Named adapters only, never raw shell passthrough | Per action | Optional/GATED |

All modes must expose output cap, timeout, environment filter, cwd, cancellation behavior, ownership, active PID, exit receipt, and rollback/cleanup.

### 3.13 Upgrade Center

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Channel | Stable, candidate, custom local artifact | Stable | LATER |
| Scope | App, backend deps, frontend deps, runtime, model, plugin | Explicit one scope | NEXT inventory |
| Source | Local artifact, approved download, package manager | Local first | LATER/GATED |
| Preflight | Disk, manifests, compatibility, active baseline, backup target | All required | NOW read-only |
| Backup | Source-only, config/data, runtime artifact, full rollback bundle | Scope-appropriate verified bundle | LATER |
| Stage | Download/copy/build without activation | Explicit | LATER |
| Activate | Immediate, maintenance window, next restart | Maintenance window | LATER/GATED |
| Rollback | Automatic on failed smoke, manual, keep current | Automatic on failed smoke + manual | LATER |
| Cleanup | Keep N, age-based, manual | Keep last two verified bundles | LATER |

### 3.14 Feedback, issues, and external publishing

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Draft type | Bug, feature, task, note | Bug/feature now | NOW |
| Storage | Local only, Markdown export | Local only | NOW/NEXT |
| Destination | Disabled, GitHub Issues, Linear, both sequentially | Disabled | GitHub backend gated; Linear LATER |
| Send mode | Never, per draft, approved batch | Per draft | GATED |
| Content | Summary only, include bounded steps, attach redacted receipt | Summary + bounded steps | NOW contract |
| Duplicate handling | Allow, warn by title/hash, link existing | Warn | LATER |
| Status sync | None, manual refresh, webhook | None | LATER |

### 3.15 UI, accessibility, and observability

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Settings depth | Basic, Advanced, Expert read-only raw view | Basic | PARTIAL/NEXT |
| Layout | Canvas focus, Inspector focus, split, compact | Split | LATER |
| Theme | System, dark, light, high contrast | System | LATER |
| Density | Comfortable, compact | Comfortable | LATER |
| Text scale | 90–150% bounded | 100% | LATER |
| Motion | Full, reduced, off | Respect system | LATER |
| Run timeline | Summary, full events, approvals only, errors only | Summary | PARTIAL/NEXT |
| Timer | Off, 1/5/15/30/custom reminder | Off | NOW |
| Notifications | In-app, Windows toast, sound off/on | In-app only | LATER |
| Logs | Metadata only, diagnostics bundle, verbose sensitive-content-forbidden | Metadata only | NOW |

### 3.16 Security, privacy, and network boundaries

| Option group | Choices | Recommended default | Status |
|---|---|---|---|
| Bind | Loopback, explicit LAN | Loopback | NOW |
| Credential source | Environment alias, Windows Credential Manager alias | Windows Credential Manager where supported | NOW/PARTIAL |
| Secret entry | Local Notepad/OS credential flow, local settings dialog | Local secret-safe flow | NEXT |
| Public HTTP | Disabled; HTTPS required | Disabled | NOW |
| LAN HTTP | Explicit trusted host/profile | Disabled until configured | NOW backend / UI NEXT |
| Redirects | Off, bounded same-policy | Off | NOW |
| Sensitive retention | Never store credentials, auth, audio, transcript logs, arbitrary prompt/file logs | Never | NOW |
| Diagnostic export | Metadata summary, redacted bundle | Redacted bundle | LATER |
| Destructive action | Preview + approval + exact target + rollback where possible | Required | NOW/PARTIAL |

---

## 4. Option-registry architecture

### 4.1 New source-of-truth module

Create `backend/options_registry.py` with static definitions and dynamic choice providers. Do not store secret values or runtime-heavy inventory in static definitions.

Proposed supporting contracts:

- `OptionDefinition` — immutable metadata and validation.
- `OptionChoice` — value, label, status, reason, evidence, effect.
- `ResolvedOption` — definition + inherited current value + source scope.
- `OptionContext` — user/project/workflow/node/run/profile identity.
- `OptionEffect` — read-only/local-write/file/process/device/network/cloud/external.
- `OptionEvidence` — source/synthetic/live/device/provider/external status.

### 4.2 Persistence model

Add an additive `option_values` table only for user/project/workflow/global selections that are not already authoritative in a specialized profile.

Suggested fields:

- `id`, `option_id`, `scope_type`, `scope_id`
- `value_json`, `value_hash`
- `created_at`, `updated_at`
- `source`, `schema_version`

Do **not** duplicate endpoint-profile, hardware-profile, graph-node, or run-specific values. The resolver reads those existing stores and reports their source.

Resolution order:

1. One-shot run override.
2. Node setting.
3. Workflow setting.
4. Project setting.
5. User/global setting.
6. Safe registry default.

Crossing a safety boundary cannot be inherited silently. Cloud, external publication, device capture, process mutation, and destructive actions require an explicit selection at the applicable workflow/run/action scope.

### 4.3 API plan

- `GET /api/options` — definitions filtered by category/scope/status.
- `GET /api/options/resolved` — resolved values and source scopes for a context.
- `POST /api/options/validate` — validate candidate changes without mutation.
- `POST /api/options/apply` — apply local settings only after effect/approval validation.
- `POST /api/options/reset` — reset one scope to inherited/default value.
- `GET /api/options/export.md` — current option catalog and evidence.

Existing specialized APIs remain authoritative for endpoints, hardware, runs, terminal, upgrades, and feedback. The option API links to them instead of becoming a bypass.

### 4.4 Frontend plan

Create reusable controls:

- `frontend/components/options/OptionControl.tsx`
- `frontend/components/options/OptionGroup.tsx`
- `frontend/components/options/OptionStatus.tsx`
- `frontend/components/options/OptionImpactPreview.tsx`
- `frontend/components/options/ResolvedValueBadge.tsx`

Integrate them incrementally into `ControlCenterPanel`, `ModelRouteSettings`, node editors, Run Inspector, Terminal, Upgrade Center, and project settings. Preserve existing specialized UI until each replacement passes parity checks.

### 4.5 Capability-matrix integration

The capability matrix should derive option status dynamically:

- Registered option with no implementation/evidence → BLOCKED.
- Prerequisite unavailable → DISABLED with exact reason.
- Synthetic acceptance only → PASS at synthetic tier, live tier BLOCKED.
- Live/device/provider/external acceptance → PASS only for that exact profile/action.
- Stale receipt after source/profile change → BLOCKED until revalidated.

Replace hard-coded test-name maps gradually with versioned evidence receipts tied to source/profile hashes.

---

## 5. Implementation roadmap

### Phase 0 — Governance, option inventory, and data hygiene

**Status:** NEXT
**Objective:** Freeze the option contract and remove sources of misleading choices before adding controls.

Tasks:

1. Add this roadmap and tracker link.
2. Add a generated inventory test proving all 20 node kinds and every visible Control Center/node setting are represented or explicitly exempted.
3. Define the option schema and effect taxonomy in `backend/options_registry.py`.
4. Add `tests/test_options_registry.py` with duplicate-ID, invalid-default, missing-effect, unsafe-inheritance, and evidence-state checks.
5. Add a backed-up migration/cleanup plan for exact acceptance artifacts `gpu-one`, `gpu-two`, and `test-pci-order`; do not wildcard-delete user profiles.
6. Ensure standalone and combined test discovery always use temporary databases before importing `backend.main`.
7. Add a worker ledger and publication-lock section to `PROJECT_TRACKER.md`.
8. Reconcile README claims that predate Phase 26 live GPU acceptance.

Likely files:

- Create `backend/options_registry.py`
- Create `tests/test_options_registry.py`
- Modify `backend/database.py`, `backend/schema.py`, `backend/capability_matrix.py`
- Modify `README.md`, `PROJECT_TRACKER.md`

Acceptance:

- Every option has one stable ID, safe default, scope, effect, status, prerequisites, evidence tier, and rollback.
- No test fixture appears as a live user profile.
- Existing 17+ acceptance tests remain green in the final Phase 0 batch.
- Capability matrix and option inventory report zero invalid-ready rows.

### Phase 1 — Option API and reusable settings UI

**Status:** PLANNED
**Objective:** Make one registry drive API and UI without breaking existing specialized controls.

Tasks:

1. Add additive `option_values` persistence and migration.
2. Implement scope resolver and safety-boundary inheritance rules.
3. Add read/validate/apply/reset/export APIs.
4. Build reusable Option controls with ready/blocked/disabled reason display.
5. Add Basic/Advanced grouping and resolved-source badges.
6. Add impact preview for local mutations and links to specialized approval flows.
7. Migrate a low-risk slice first: timer, UI preferences, run retention, and default approval policy.
8. Keep endpoint/hardware/profile mutation in existing APIs until later parity tests pass.

Likely files:

- Modify `backend/database.py`, `backend/main.py`, `backend/schema.py`
- Create `frontend/components/options/*`
- Modify `frontend/components/ControlCenterPanel.tsx`, `frontend/components/RunInspector.tsx`
- Create focused backend/frontend option tests

Acceptance:

- Resolved values identify source scope.
- Reset restores inheritance safely.
- Cloud/external/device/process options never activate through inherited global defaults.
- UI and Markdown export render from the same definitions.

### Phase 2 — Complete canvas/node options and blocked-node evidence

**Status:** PLANNED
**Objective:** Give each of 20 node types a complete editor and honest evidence status.

Work lanes:

- Node editors and defaults.
- Runtime execution contracts.
- Capability evidence and fixtures.

Tasks:

1. Generate an option sheet per node.
2. Add missing Task, Tool, Runtime, Planner, Coder, Buzz, TTS, Search, Research, and Source Context controls.
3. Complete merge strategies and branch failure options.
4. Add execution-mode, error, retry, timeout, cancellation, and retention settings.
5. Persist frozen resolved option values in each run.
6. Add source/synthetic evidence for every node before device/provider acceptance.
7. Keep live/device/network-only rows BLOCKED until actually exercised.

Acceptance:

- All 20 nodes have schema-aligned controls.
- Graph save/load round-trips every option.
- No node displays a runnable control without a concrete executable path and evidence state.

### Phase 3 — Model endpoint, exact model, and hardware/runtime control

**Status:** PARTIAL
**Objective:** Finish enforceable provider/model/device choices and app-owned runtime lifecycle.

Tasks:

1. Reconcile legacy provider variables and endpoint profiles into one visible route resolution.
2. Add MiniMax to the endpoint-profile registry; preserve explicit aliases and no fallback.
3. Add governed custom endpoint create/edit/delete with URL/TLS/credential validation.
4. Add exact model inventory and custom-ID validation per provider.
5. Implement strict requested-versus-observed placement receipts.
6. Distinguish runtime-auto split, explicit split where supported, independent servers, and concurrent independent jobs.
7. Add app-owned isolated Ollama/Nanbeige start/status/stop/restart/preload/unload actions.
8. Add VRAM reserve, lane queue, loaded-model cap, keep-alive, and idle-unload policies.
9. Preserve user-managed listeners and baseline rollback.
10. Add approved ordered fallback and cloud-enabled fallback only after explicit policy tests.

Acceptance:

- Exact endpoint, model, hardware profile, and fallback appear in run receipts.
- Strict placement fails closed on observed mismatch.
- App can only stop processes it owns.
- Local-to-cloud transitions require explicit policy and receipt.

### Phase 4 — Governed terminal and managed processes

**Status:** PREVIEW ONLY
**Objective:** Progress from classifier to useful execution without exposing arbitrary unbounded shell access.

Subphases:

1. Read-only allowlisted execution.
2. Governed exact executable/argv task execution.
3. App-owned process lifecycle.
4. Optional interactive PTY after the first three are accepted.

Tasks:

- Define command profiles, argv schemas, environment allowlists, cwd policy, timeout/output caps, cancellation, and ownership.
- Add preview hashes and single-use approvals.
- Persist metadata-only receipts; never log secret values or unbounded output.
- Add visible active-process list with stop only for app-owned PIDs.
- Keep network/destructive/process-control commands behind named adapters.

Acceptance:

- Preview and execution use the same normalized request hash.
- Cancellation and timeout leave no orphan app-owned child.
- Restart reconciliation marks detached processes honestly.
- No raw command path bypasses schemas/approval.

### Phase 5 — Upgrade Center stage, activate, and rollback

**Status:** INVENTORY/PREFLIGHT ONLY
**Objective:** Add reliable upgrades with verified backups and automatic failed-smoke rollback.

Tasks:

1. Define upgrade manifest and channel contracts.
2. Add scope-specific backup builders and hashes.
3. Add local-artifact staging first.
4. Add approved download adapters later.
5. Add build progress and bounded logs.
6. Add maintenance-window activation.
7. Run health/behavior smoke after activation.
8. Roll back automatically on failed smoke.
9. Keep N verified bundles and provide manual restore.

Acceptance:

- No activation without a verified rollback bundle.
- Existing baseline continues until staged candidate passes.
- Interrupted upgrade resumes or rolls back deterministically.

### Phase 6 — Research and voice/device acceptance

**Status:** CONTRACTS PARTIAL / LIVE GATED
**Objective:** Convert blocked nodes to profile-specific PASS without overstating network/device behavior.

Research tasks:

- Accept local SearXNG discovery with bounded live evidence.
- Accept selected-page extraction with source/citation receipts.
- Use Nanbeige for selected local synthesis; do not use Qwen for this lane.
- Add rerank/embedding/OCR options only when the local model/runtime is measured.

Voice tasks:

- Add explicit input-mode selector and consent receipt.
- Accept one bounded live microphone capture with no transcript/audio logging.
- Add local voice inventory and one manual TTS playback acceptance.
- Add cancellation, duration, device-disconnect, and cleanup evidence.

Acceptance:

- PASS is scoped to exact device/model/provider profile.
- No silent typed/LLM fallback for voice-only contracts.
- Public network and device actions remain explicit.

### Phase 7 — Agents, branch workers, and Delegate result merging

**Status:** PLAN-ONLY/PARTIAL
**Objective:** Make parallel work durable, visible, resumable, and safe.

Tasks:

1. Persist exact worker/session/branch/worktree ownership and continued-from identity.
2. Add worker target profiles and readiness.
3. Add approval-gated named dispatch.
4. Track child lifecycle and bounded completion receipts.
5. Add manual child-output review/merge first.
6. Add automatic downstream merge only for validated schemas and accepted workers.
7. Add branch diff/status/verification receipts without exposing secrets.
8. Add parent publication lock and stale-worker rebase gate.
9. Reject overlapping writer claims unless the parent explicitly serializes them.

Acceptance:

- Same agent/project/channel/thread resumes the same persisted session where supported.
- Unavoidable replacement records `continued_from` and reason.
- Child claims are parent-verified against the authoritative worktree.
- No worker can publish/merge independently unless Drew explicitly grants it.

### Phase 8 — External providers, feedback destinations, and optional integrations

**Status:** GATED
**Objective:** Add real external actions one destination/profile at a time.

Candidate lanes:

- OpenRouter exact-model smoke.
- Ollama Cloud exact-model smoke.
- MiniMax endpoint-profile migration/smoke.
- GitHub feedback issue publication.
- Linear feedback publication.
- Optional LAN endpoints.

Each lane requires:

- Exact destination/provider/model.
- Credential alias presence without value disclosure.
- Content-class preview.
- Cost/privacy statement.
- One-shot approval.
- Success/failure receipt.
- No fallback outside the selected lane.

### Phase 9 — Product polish, packaging, and release readiness

**Status:** LATER
**Objective:** Turn accepted controls into a cohesive Windows product.

Tasks:

- Settings search, presets, export/import, reset, and conflict display.
- Accessibility, theme, density, motion, and keyboard navigation.
- Native Windows packaging/startup options.
- Diagnostics bundle and recovery mode.
- Release notes generated from tracker receipts.
- Clean fresh-install and upgrade-from-prior-version acceptance.
- Security/release audit before public distribution.

---

## 6. Branch-worker operating protocol

### 6.1 Default policy

No workers are active or authorized by this roadmap alone. The parent remains the integration authority until Drew explicitly assigns or authorizes branch workers.

### 6.2 Required branch/worktree isolation

Each writer must have:

- Unique worker/session ID.
- Unique branch: `worker/<lane>/<short-scope>` or another parent-approved name.
- Unique worktree outside the parent checkout.
- Exact base SHA.
- Exact owned files/directories.
- Explicit non-owned shared files.
- One tracker row before the first mutation.

Same-worktree concurrent writers are prohibited. Phase 26 demonstrated that same-worktree sessions can change files during review/build and invalidate evidence.

### 6.3 Suggested non-overlapping lanes

| Lane | Suggested scope | Primary ownership | Shared files parent integrates |
|---|---|---|---|
| A — Option registry backend | Definitions, resolver, option APIs | `backend/options_registry.py`, new option tests | `backend/main.py`, `backend/database.py`, `backend/schema.py` |
| B — Settings frontend | Reusable option controls and settings views | `frontend/components/options/`, focused UI tests | `ControlCenterPanel.tsx`, global CSS |
| C — Model/runtime | Endpoint/profile/hardware/runtime lifecycle | `backend/model_profiles.py`, `backend/runtime_control.py`, new runtime modules/tests | `backend/main.py`, model UI |
| D — Terminal/upgrade | Governed process and upgrade workflows | `backend/terminal_control.py`, `backend/upgrade_control.py`, focused tests | `backend/main.py`, Control Center |
| E — Node completion | Node editors and runtime option wiring | New node-specific components/tests | `types.ts`, `Canvas.tsx`, `execution_runtime.py` |
| F — Evidence/acceptance | Capability evidence, fixtures, audits | New test/evidence modules | `capability_matrix.py`, tracker |
| G — Docs/UX inventory | README, option catalog review, accessibility spec | Documentation and new isolated UX docs | This roadmap/tracker only through parent |

A worker should not own `backend/main.py`, `Canvas.tsx`, `types.ts`, `PROJECT_TRACKER.md`, or this roadmap concurrently with another writer. These are integration hotspots and normally stay parent-owned.

### 6.4 Worker context packet

Every worker receives:

1. Goal and acceptance outcome.
2. Baseline commit and branch/worktree path.
3. This roadmap path and relevant section.
4. Tracker path and latest worker ledger.
5. Allowed files and forbidden shared files.
6. Existing contracts/APIs/types to preserve.
7. Privacy, approval, local-first, and no-secret rules.
8. Test policy and exact final checks.
9. Active sibling lanes and dependencies.
10. Handoff template and stop conditions.

### 6.5 Live worker ledger schema

The tracker must maintain one row per active or completed worker:

| Field | Required content |
|---|---|
| Worker/session | Stable agent/session identity and `continued_from` when applicable |
| Lane/scope | One bounded outcome |
| Branch/worktree | Exact branch and absolute worktree |
| Base SHA | Commit worker started from |
| Owned files | Exact paths/globs |
| Shared dependencies | Files/contracts the parent must integrate |
| Status | queued, active, blocked, ready-for-review, integrated, superseded, cancelled |
| Latest checkpoint | Timestamp plus Now/Done/Next/Blocked |
| Changed files | Exact list |
| Verification | Commands and real outputs |
| Commit(s) | Worker SHA(s), if any |
| Blockers/risks | Exact boundary |
| Integration | Parent reviewer, target SHA, conflict resolution, final status |

### 6.6 Worker handoff template

```markdown
#### Worker handoff — <worker/session> — <timestamp>
- Lane / goal:
- Branch / worktree:
- Base SHA / latest SHA:
- Owned files:
- Files changed:
- Contracts preserved:
- Verification commands and results:
- Unverified or approval-gated paths:
- Blockers / known risks:
- Integration order / dependencies:
- Continued-from session (if any):
- Recommended parent next action:
```

### 6.7 Parent integration protocol

1. Freeze new writer assignments for overlapping files.
2. Fetch/read the worker branch and verify branch/worktree identity.
3. Compare worker base with current integration head.
4. Read diff and handoff; do not accept a summary as proof.
5. Run focused checks for the worker contract only if needed.
6. Integrate in dependency order.
7. Reconcile shared files parent-side.
8. Update tracker with conflict decisions and integration SHA.
9. Run one consolidated final test/build batch after all lanes land.
10. Establish a publication lock; ensure no active writer targets the frozen manifest.
11. Commit/push/update PR and read back remote head.
12. Append publication receipt.

### 6.8 Publication lock states

- `OPEN` — workers may mutate only claimed disjoint scopes.
- `FREEZE_REQUESTED` — workers stop after safe checkpoint and hand off.
- `FROZEN` — no source writes; parent reviews and verifies exact manifest.
- `PUBLISHING` — parent-only commit/push/PR actions.
- `PUBLISHED` — remote head and PR read back; new work starts from that head.

---

## 7. Decision queue with recommended defaults

These are choices, not blockers to writing Phase 0 foundation unless marked otherwise.

| Decision | Options | Recommended default | Needed by |
|---|---|---|---|
| First implementation phase | Option registry/hygiene; terminal; upgrades; model control; node completion | Option registry + hygiene | Before workers code options |
| Worker authorization | Parent only; named workers; broad delegation | Parent only until Drew names/authorizes lanes | Before dispatch |
| Settings scope | Global only; project; workflow; node; full hierarchy | Full hierarchy with safety-boundary non-inheritance | Phase 1 |
| Terminal ceiling | Preview; read-only; governed tasks; managed processes; PTY | Read-only + governed tasks first | Phase 4 |
| Dual-GPU default meaning | Runtime split; independent servers; independent jobs | Independent servers/jobs; label runtime split separately | Phase 3 |
| Runtime ownership | User-managed; app-managed; hybrid | Hybrid with explicit ownership | Phase 3 |
| Automatic unload | Off; reminder; approved idle policy | Reminder only initially | Phase 3 |
| OpenRouter model | Exact Drew-selected model; shortlist; disabled | Disabled until exact selection | Phase 8 |
| Feedback destination | Local; GitHub; Linear; both | Local until selected | Phase 8 |
| Public retrieval | Disabled; per-run approval; standing workflow policy | Per-run approval first | Phase 6 |
| Run retention | Explicit delete; age/N; archive | Explicit delete now; configurable later | Phase 1 |
| Upgrade channel | Stable; candidate; custom | Stable/local artifact first | Phase 5 |
| UI complexity | Basic/Advanced; expert raw | Basic/Advanced | Phase 1 |

---

## 8. Acceptance evidence ladder

A capability can advance only through applicable tiers:

1. **Registered** — schema/handler/control exists. Status remains BLOCKED.
2. **Source verified** — compile/type/static contract passes. Still BLOCKED for behavior.
3. **Synthetic accepted** — bounded temporary DB/workspace tests pass.
4. **Live local accepted** — deployed loopback API/UI behavior passes.
5. **Device accepted** — exact microphone/GPU/speaker/process profile exercised.
6. **Provider accepted** — exact local/LAN/cloud model/provider exercised with identity receipt.
7. **External accepted** — exact destination mutation/send succeeds with approval receipt.

Evidence expires or becomes stale when relevant source, profile, model, endpoint, device identity, or safety policy changes.

### Standard final batch

```bash
env -u PYTHONPATH backend/.venv/Scripts/python.exe -m unittest discover -s tests -v
env -u PYTHONPATH backend/.venv/Scripts/python.exe -m compileall -q backend tests
cd frontend
npm run typecheck
NEXT_DIST_DIR=.next-roadmap-acceptance npm run build
```

Then restore generated Next metadata, run `git diff --check`, scan added/new content for credential/conflict/debug residue, and perform one focused smoke appropriate to the phase. Do not repeat expensive builds after a successful accepted artifact unless source changes.

---

## 9. Phase completion and release gates

Every phase must leave:

- Working source with no parallel forked implementation.
- Updated option definitions and status/evidence.
- Updated roadmap if requirements/defaults changed.
- Append-only tracker receipts.
- Worker handoffs and integration state reconciled.
- Exact blocked/deferred paths.
- Final batch output.
- One real smoke where authorized.
- Clean branch or explicit listed dirty scope.
- Conventional commit(s), pushed branch, and PR update only when Drew requests/authorizes publication.

No phase is “done” because the UI renders. The selected option must be validated, enforced, persisted at the correct scope, visible in receipts, and reversible or explicitly irreversible.

---

## 10. Immediate next tasks

1. Review this roadmap with Drew and record corrections.
2. Establish the tracker’s worker ledger/publication-lock section.
3. Create the Phase 0 option-definition contract.
4. Add inventory coverage for all current visible controls and 20 node kinds.
5. Fix test-database isolation at import boundaries.
6. Back up and remove only exact known acceptance hardware-profile artifacts.
7. Reconcile README runtime/GPU statements with current accepted evidence.
8. Implement option registry validation before adding more dropdowns.
9. Assign any explicit branch workers to disjoint lanes using Section 6.
10. Run the Phase 0 consolidated batch only after all assigned lanes integrate.

---

## 11. Current checkpoint

**GOAL:** Make Refactor Workflow Studio option-complete across workflow, model, hardware, tools, research, voice, terminal, upgrades, feedback, UI, security, and worker orchestration while preserving local-first safety, explicit external approvals, and parent-controlled integration.

### Done

- Durable HITL runtime and Phase 26 model/GPU/feedback controls are published on the active feature branch.
- Current repository/live capability, endpoint, runtime, and hardware inventories were inspected.
- Product-wide option taxonomy, architecture, phase order, decision queue, and worker protocol are defined in this roadmap.
- Durable user preference for option-complete roadmaps and worker-ready tracking was saved.

### Now

- Parent-owned Phase 0 implementation: option registry/validation, inventory coverage, import-time test isolation, exact acceptance-profile cleanup after backup, and capability/README synchronization.
- No delegated implementation worker is active; integration hotspots remain parent-owned.

### Next

- Publish the documentation checkpoint, implement the typed registry and generated inventory, perform exact-ID data hygiene, run the consolidated Phase 0 batch, deploy one focused smoke, then publish the accepted source manifest.

### Blocked / approval-gated

- OpenRouter exact model/key and cloud generation.
- GitHub/Linear feedback publication.
- Real microphone/TTS acceptance.
- Public retrieval/synthesis acceptance.
- App-owned process/runtime mutation and Upgrade Center activation.
- Worker dispatch until Drew explicitly authorizes or assigns workers.
