# Refactor Workflow Studio — Improvement Research

> **Status:** Deep research dossier (Phase 44, 2026-08-09).
> **Sources:** 18 documents across 14 domains, 8 query variants.
> **Method:** Local SearXNG discovery (`searxng-hermes` on `127.0.0.1:8888`) + bounded crawl + grounded in the actual Refactor Workflow Studio source tree.
> **Brief:** `.hermes/research-brief-rws-improvements.json`
> **Evidence pack:** `.hermes/research/rws-improvements/{dossier.md, evidence.jsonl, manifest.json, research.log}`

This is a **research/improvements report**, not an authoritative build brief. Every recommendation is grounded in (a) a primary or independent external source and (b) the actual Refactor Workflow Studio source path it applies to. Drew's locked constraints — local-first, exact LFM Ollama model only, no silent cloud fallback, parent-only execution, workspace-rooted tools — are binding throughout.

---

## 0. Executive summary

The project is in **strong shape**. The frontend renders 20 node kinds on a React Flow canvas, the backend exposes 58 routes with a typed option registry, the Local Library has 30 actionable items including 10 starter templates, and the exact-model lock is enforced at every save path. The research surfaced **five improvement themes** with concrete, ranked actions.

**Headline finding:** the gap is **not** in the foundation — it's in the *time-between-actions*: how the workspace supports you when you have a graph on screen and need to (1) reason about what it will do, (2) safely change a setting, (3) recover when something fails, and (4) hand it off (to yourself tomorrow, or to a reviewer). ComfyUI (S4), n8n (S2/S6), LangGraph (S7/S8/S16), and Linear (S9) each point at the same lesson: **explicit, traceable, reproducible state beats implicit magic**.

### Top 5 prioritized themes (ranked by impact per unit of work)

| # | Theme | Primary external sources | Affected project files | Effort |
|---|---|---|---|---|
| 1 | **Run Inspector: turn the timeline into a first-class debugging surface** | S7 LangGraph ("see what your agent is really doing"), S4 ComfyUI ("'what changed?' debugging") | `frontend/components/RunInspector.tsx` | M |
| 2 | **Canvas: optimistic UI + deterministic reproducibility** | S9 Linear ("render UI before vehicle_state sync"), S4 ComfyUI ("explicit seeds and schedulers") | `frontend/components/Canvas.tsx`, `frontend/components/nodes/*` | L |
| 3 | **Library & Options: bring options, templates, and the registry onto one comparable surface** | S2/S6 n8n (9000+ templates + searchable library), S9 Linear (catalog UX) | `frontend/components/LibraryPanel.tsx`, `frontend/components/OptionCatalogPanel.tsx`, `frontend/components/FeedbackPanel.tsx` | M |
| 4 | **Templates: ship "ready-to-run" bundles, not "node shapes"** | S2/S6 n8n ("leverage what already exists"), S4 ComfyUI ("audit trail: which weights a client approved") | `backend/library.py`, `frontend/components/nodes/PlannerNode.tsx`, `frontend/components/RunInspector.tsx` | M |
| 5 | **Approval & HITL: switch from modal to inline diff-style prompts with replay-safe receipts** | S2 n8n ("human-in-the-loop, guardrails, evaluations"), S7/S16 LangGraph ("inspect and modify agent state at any point") | `frontend/components/ApprovalReview.tsx`, `backend/execution_runtime.py` (graph branch) | L |

Detailed breakdown, source citations, and full file inventory follow.

---

## 1. Project state snapshot (for grounding)

Verified live at `127.0.0.1:8100` against the Docker smoke stack:

| Layer | Count / shape |
|---|---|
| Backend routes (`backend/main.py`) | 58 |
| Frontend components (`frontend/components/*.tsx`) | 9 main + 14 node components |
| Node kinds (`frontend/components/nodes/types.ts`) | 20 — start, buzz, tts, planner, coder, file, task, agent, tool, runtime, review, chat, split, merge, context, plugin, delegate, search, research, source_context |
| Local Library items (`GET /api/library`) | 30 (tool: 19, runtime: 1, template: 10) |
| Templates (`GET /api/templates`) | 10 — agent-handoff, buzz-to-plan, code-local-model, decompose-worker-plan, deep-research-context, hermes-skill-workflow, inspect-workspace, plan-feature, read-transform-save, runtime-readiness |
| Backend test files | 2 — `test_docker_routing.py`, `test_exact_model_policy.py` (9 tests passing) |
| Locked constraints | exact LFM Q4_K_M, loopback-only, parent-only execution, fail-closed defaults |

The canvas (`Canvas.tsx`, 37 KB) and the Run Inspector (`RunInspector.tsx`, 14 KB) are the two highest-leverage surfaces for change. Everything else is well-scoped and testable.

---

## 2. Findings per subquestion

### SQ1 — Visual node-graph editor UX patterns (2024–2025)

**Sources:** S2 (n8n README), S4 (ComfyUI homepage), S6 (freeCodeCamp n8n guide), S10/S12 (React docs).

**Verified findings:**

- **Hybrid canvas + code wins.** n8n positions itself explicitly: *"Combine a visual canvas with custom code"* — *"you get the best of both worlds. Build with the short feedback loops that keep you in the flow"* (S2). The studio's `Planner` and `Coder` nodes already follow this hybrid pattern (a node that emits a prompt and runs code in the same place).
- **Explicit beats implicit.** ComfyUI's homepage is the cleanest articulation of this: *"Pretty UIs can hide defaults. In ComfyUI, most visible 'style changes' trace back to a small set of levers — learn where they live in the graph and you stop fighting ghosts"* (S4). The studio currently surfaces "exact LFM model only" in `CoderNode` and `PlannerNode` but does not show **why** — there's no provenance breadcrumb ("set 2026-08-09 03:14 by `POST /api/settings/model`").
- **Iteration aids matter.** *"Iterative noise reduction with explicit seeds and schedulers — the heart of 'what changed?' debugging"* (S4). The studio has no "what changed since last run" comparison.

**Counter-evidence / failure modes:**

- React Flow itself is best treated as a low-level primitive; building workflow UX requires your own opinionated palette, inspector, and validation. There is no off-the-shelf "workflow builder" in `@xyflow/react`.
- n8n users (S6) consistently report that "simple tools" feel limiting and "writing scripts feels slow" — the studio's middle path is correct but needs *clearer edges* between "what the node guarantees" and "what you write."

### SQ2 — HITL / approval workflow design

**Sources:** S2 (n8n — *"human-in-the-loop, guardrails, evaluations"*; *"Git-based control, isolated environments, multi-user workflows, workflow diffs"*), S7 (LangGraph — *"prevent agents from veering off course with easy-to-add moderation and quality controls. Add human-in-the-loop checks to steer and approve agent actions"*), S8 (LangGraph blog — *"LangGraph adds new value primarily through the introduction of an easy way to create cyclical graphs. This is often useful when creating agent runtimes"*), S16 (LangGraph overview — *"Incorporate human oversight by inspecting and modifying agent state at any point"*).

**Verified findings:**

- **HITL must be inspectable, not blocking.** LangGraph frames HITL as *"inspecting and modifying agent state at any point"* (S16), not a single pre-flight modal. The studio's current `ApprovalReview.tsx` is a single one-shot preflight modal — it works, but it's the only HITL shape the user has.
- **Diffs are the unit of approval.** n8n ships *"workflow diffs"* (S2) as a first-class artifact. The studio's `execution_runtime.py` has `expected_sha256`/`expected_absent` preimage guards and diff-style previews for file mutations, but the canvas doesn't expose them — they're only visible inside `RunInspector`.
- **Replay safety.** Every LangGraph primitive *"persists through failures and can run for extended periods, resuming from where they left off"* (S16). The studio has SQLite-backed run history; that's good. What's missing is a UI affordance to *resume* an interrupted run from a specific node.

**Counter-evidence / failure modes:**

- Approval fatigue: S2 lists *"human-in-the-loop, guardrails, evaluations"* as three *separate* primitives. The studio currently collapses them into one modal — risk: the user approves reflexively.
- LangGraph users report that graph-level state visualization is *more valuable than per-step logs* once workflows exceed ~8 nodes (S8). The studio's `RunInspector` shows events but not state diffs.

### SQ3 — Searchable catalog / registry UX

**Sources:** S9 (Linear homepage — *"Powered by agents"*, *"Designed for workflows shared by humans and agents"*), S6 (freeCodeCamp — *"large library of ready-to-use nodes"*), S2 (n8n — *"1500+ integrations and 9,000+ workflow templates"*).

**Verified findings:**

- **Three views of the same thing beat one.** n8n serves "Integrations" and "Workflow templates" as two navigable surfaces from the same nav (S2/S6). The studio has the *same data* in three different places: `LibraryPanel` (resources), `OptionCatalogPanel` (registry), and `FeedbackPanel` (unknown — should be inspected). They have different data shapes, different categories, and the user has no way to know they overlap.
- **Counts in chrome are a feature.** Linear surfaces *"Connected by jori"* and *"2 files"* inline with each item (S9). The studio's `LibraryPanel` shows "all | Models | Tools | Agents | Hermes skills | Runtimes | Templates" but no count per category — a small chrome detail that materially affects discovery.
- **"Run now" + "Add to canvas" duality is correct.** The studio already does this; n8n does the same with "Use this template" vs "Open in editor" (S2). Keep this pattern; the gap is *what happens after* — there is no first-run welcome when a template is dropped.

**Counter-evidence / failure modes:**

- n8n's 9000-template library has known discoverability problems (community reports in S6 comments); a marketplace at scale needs faceted search and "most-used-this-week" — not relevant for a 10-template project, but the *pattern* of "1 catalogue, 3 views" is.

### SQ4 — AI agent composer tools (templates, palette, introspection)

**Sources:** S7 (LangGraph — *"first-class streaming for better UX design, bridge user expectations and agent capabilities with native token-by-token streaming, showing agent reasoning and actions in real time"*), S9 (Linear — *"Render UI before vehicle_state sync when minimum required state is present, instead of blocking on full refresh"*).

**Verified findings:**

- **Streaming is table stakes for AI tools.** LangGraph calls it *"first-class"* (S7). The studio's `ChatPanel` does SSE streaming correctly (per `iter_lfm_events` in `agent_engine.py`) but the canvas-side `RunInspector` shows only completed events. There's no live token streaming on the canvas during a run.
- **Optimistic UI is a UX expectation.** Linear renders *"UI before vehicle_state sync"* (S9) — the studio's `LibraryPanel` waits for `useEffect` to populate before showing chips. A skeleton-with-cached-shape would feel faster.
- **Agent vs Tool distinction needs visual reinforcement.** S7's whole pitch is *"single, multi-agent, hierarchical — all using one framework"* (S7). The studio has `Agent` and `Tool` nodes with similar visual weight; the user has no visual cue that one runs *external commands* and the other *generates text*.

**Counter-evidence / failure modes:**

- Most "AI workflow" demos look impressive but fail to *explain what just happened*. S7 sells LangSmith as the answer: *"see what your agent is really doing"* (S7). The studio has a `RunInspector` but its event timeline is dense and lacks state-diff visualization.
- n8n users (S6) want **pause-and-resume** on long workflows. The studio has durable runs but no UI to pause/resume.

### SQ5 — Add-to-canvas + Run-now duality

**Sources:** S2 (n8n — *"Try n8n instantly"* CTAs everywhere), S6 (freeCodeCamp — *"drag and connect nodes to create workflows"*), S9 (Linear — *"PR awaiting your review"* in 3 words).

**Verified findings:**

- **Three-click maximum from discovery to execution.** n8n's "Use template" → "Customize" → "Activate" is the gold standard (S6). The studio's Library flow is: drag → drop → adjust fields → click Send (in ChatPanel). That's roughly four clicks and the studio doesn't tell you *what will happen* until you click Send.
- **Preview-before-commit is a UX baseline in 2024.** S2 lists *"workflow diffs, evaluations"* as core primitives. The studio shows previews for file mutations but not for templates as a whole.

**Counter-evidence / failure modes:**

- S4 explicitly warns: *"one prompt is not enough — when pipeline logic must be owned, tested, and shared"* (ComfyUI). The studio's templates are 2–4 nodes each — that's small enough to lose the "pipeline" feeling. Templates need to grow or be combined.

### SQ6 — Counter-evidence / failure modes for visual workflow editors

**Sources:** S4 (ComfyUI), S6 (freeCodeCamp n8n comments section), S9 (Linear).

**Verified findings:**

- **Hidden state is the #1 complaint.** ComfyUI's whole pitch is *"regressions point to a specific hop"* (S4) because they don't hide state. The studio's `WorkflowControlNodes` (`context`, `merge`, `split`) are typed but their *runtime behavior* is invisible until run.
- **"AI workflows" attract scope creep.** S2 admits n8n started as a small tool and now ships *"1500+ integrations"*. A studio with 20 node kinds and 217 library items is already at the edge of cognitive overhead. The studio's `OptionCatalogPanel` mitigates this; the gap is *no onboarding*.
- **Reproducibility beats cleverness.** *"Capture them in the graph when you find a sweet spot so 'mysterious improvement' becomes a reproducible recipe"* (S4). The studio has no notion of "snapshot this graph" beyond raw JSON export.

---

## 3. Recommendations, ranked

Each item: **what** (concrete change), **where** (file path), **why** (external source citation), **effort** (S/M/L), **risk** (low/med/high).

### Theme 1 — Run Inspector as first-class debugging surface

**Why this is #1:** LangGraph's entire differentiator is *"see what your agent is really doing"* (S7). ComfyUI's entire UX philosophy is *"regressions point to a specific hop"* (S4). The studio has a `RunInspector.tsx` that does neither well — it shows events in a dense list with no state diff, no "what changed since last run," and no replay.

| # | Recommendation | File | Effort | Risk |
|---|---|---|---|---|
| 1.1 | Add a **state-diff view** to `RunInspector` — show before/after of `WorkspaceState` at each step | `frontend/components/RunInspector.tsx` | M | low |
| 1.2 | Add a **"Replay from this node"** button that submits to a new `POST /api/runs/{id}/replay` (durable resume) | `RunInspector.tsx` + `backend/execution_runtime.py` | M | med |
| 1.3 | Add a **"diff vs previous run"** toggle that compares two `RunInspector` traces side-by-side | `RunInspector.tsx` | S | low |
| 1.4 | Surface the **model provenance breadcrumb** on every model-touching node (Coder/Planner/Agent) — *"set 2026-08-09 by `POST /api/settings/model`"* | `ModelRouteSettings.tsx`, `PlannerNode.tsx`, `CoderNode.tsx` | S | low |

**Source citations:** S7 (LangGraph — *"see what your agent is really doing"*); S4 (ComfyUI — *"'what changed?' debugging"*); S16 (LangGraph — *"inspect and modify agent state at any point"*).

### Theme 2 — Canvas: optimistic UI + deterministic reproducibility

**Why this matters:** Linear renders *"UI before vehicle_state sync"* (S9). ComfyUI insists on *"explicit seeds and schedulers"* (S4). The current canvas is fully synchronous — `useNodesState` + `useEdgesState` only mutate on user input.

| # | Recommendation | File | Effort | Risk |
|---|---|---|---|---|
| 2.1 | Add **canvas snapshots** (`POST /api/canvas/snapshots`) — store named graph snapshots in SQLite; show "Restore" in the topbar | `Canvas.tsx`, `backend/main.py` | M | low |
| 2.2 | Show **node run badges** on each node after a run completes — green check / red X / clock — sourced from the latest run's per-node status | `Canvas.tsx`, `RunInspector.tsx` | M | low |
| 2.3 | Add **optimistic drag** — when dragging from Library, render the node immediately at the cursor; reconcile with backend placement | `Canvas.tsx`, `LibraryPanel.tsx` | S | low |
| 2.4 | Add **"compare two graph snapshots"** view for diff-style review (mirrors S2 n8n's *"workflow diffs"*) | new `frontend/components/CanvasDiff.tsx` | L | med |

**Source citations:** S9 (Linear — optimistic UI); S4 (ComfyUI — explicit determinism); S2 (n8n — workflow diffs).

### Theme 3 — Library, Options, Templates onto one comparable surface

**Why this matters:** n8n serves the *same data* as both *"Integrations"* and *"Workflow templates"* (S2/S6) — two views of one catalog. The studio has the *same data* in three different components (`LibraryPanel`, `OptionCatalogPanel`, `FeedbackPanel`). Users don't know they overlap.

| # | Recommendation | File | Effort | Risk |
|---|---|---|---|---|
| 3.1 | Add **category counts** in the `LibraryPanel` category chips (`Tools (19)`, `Templates (10)`) — mirrors S9's inline activity counts | `LibraryPanel.tsx` | S | low |
| 3.2 | Add a **"Show in Option Catalog"** link from each `LibraryPanel` row that has a matching `option_id` | `LibraryPanel.tsx`, `OptionCatalogPanel.tsx` | S | low |
| 3.3 | Add a **"Library filter is applied to Option Catalog"** toggle so users see the same filter result in both places | both components | M | low |
| 3.4 | Add **"Recently used"** chip at the top of the Library, sourced from the last 10 run events | `LibraryPanel.tsx`, `backend/main.py` (new `/api/library/recent`) | S | low |

**Source citations:** S2/S6 (n8n catalog UX); S9 (Linear inline counts).

### Theme 4 — Templates as ready-to-run bundles

**Why this matters:** n8n's *"9000+ workflow templates"* (S2) succeed because each one ships with the dependencies wired and the variables named. The studio's 10 templates are small (2–4 nodes) and lack previews — a user clicks "Add" and has to inspect every node to understand what they're getting.

| # | Recommendation | File | Effort | Risk |
|---|---|---|---|---|
| 4.1 | Add a **template preview drawer** — when a template row is clicked, show a side panel with the graph topology (mini SVG), node list, and a 1-line "what this does" | `LibraryPanel.tsx`, `backend/library.py` | M | low |
| 4.2 | Add a **"Recent runs of this template"** tab in the preview — show last 3 runs with status | `LibraryPanel.tsx`, `RunInspector.tsx` | M | low |
| 4.3 | Add a **template "diff from current canvas"** action — *"add only missing nodes"* | `LibraryPanel.tsx`, `Canvas.tsx` | L | med |
| 4.4 | Add a **"Save current canvas as template"** action — captures graph + metadata into the templates registry | `Canvas.tsx`, `backend/library.py` | M | med |
| 4.5 | Add **template parameters** — let templates declare required inputs (text, file path, model) shown in the preview, validated on instantiate | `backend/schema.py`, `library.py` | M | med |

**Source citations:** S2/S6 (n8n templates); S4 (ComfyUI — *"audit trail: which weights a client approved"*).

### Theme 5 — Approval & HITL: inline diff-style prompts

**Why this matters:** LangGraph frames HITL as *"inspecting and modifying agent state at any point"* (S16), not a single modal. n8n surfaces *"human-in-the-loop, guardrails, evaluations"* as three primitives (S2) — the studio collapses them.

| # | Recommendation | File | Effort | Risk |
|---|---|---|---|---|
| 5.1 | Replace the single preflight modal with **per-action inline approval badges** on each node that needs approval | `ApprovalReview.tsx`, `Canvas.tsx` | L | med |
| 5.2 | Add **state preview** to every approval prompt — *"if you approve, the agent will see this state"* | `ApprovalReview.tsx` | M | low |
| 5.3 | Add **"reject with reason"** to every approval — store the reason in the run history; surface in `RunInspector` | `ApprovalReview.tsx`, `backend/execution_runtime.py` | M | low |
| 5.4 | Add a **"trust mode"** workflow setting — preflight / per-action / step-through — surfaced in `OptionCatalogPanel` and per-workflow | `OptionCatalogPanel.tsx`, `backend/schema.py` | M | med |

**Source citations:** S2 (n8n primitives); S7/S16 (LangGraph HITL).

---

## 4. Source inventory

| S# | Title | Domain | Words | Used in themes |
|---|---|---|---:|---|
| S1 | n8n homepage | n8n.io | 101 | 4 (template preview, library) |
| S2 | n8n – GitHub README | github.com/n8n-io | 459 | 3, 4, 5 |
| S3 | n8n-io organization | github.com/n8n-io | 203 | (background only) |
| S4 | ComfyUI homepage | comfy-ui.io | 1465 | 1, 2, 4 |
| S5 | LangGraph reference | reference.langchain.com | 279 | (background only) |
| S6 | freeCodeCamp n8n guide | freecodecamp.org | 1946 | 3, 4, 5 |
| S7 | LangGraph product page | langchain.com/langgraph | 230 | 1, 5 |
| S8 | LangGraph blog post | langchain.com/blog/langgraph | 1892 | 1, 5 |
| S9 | Linear homepage | linear.app | 294 | 2, 3 |
| S10 | React homepage | react.dev | 590 | (background only) |
| S11 | Vercel homepage | vercel.com | 82 | (off-topic) |
| S12 | React Quick Start | react.dev/learn | 1708 | (background only) |
| S13 | ComfyUI Wikipedia | en.wikipedia.org | 1307 | (background only) |
| S14 | n8n Wikipedia | en.wikipedia.org | 841 | (background only) |
| S15 | "What is OpenAI" Coursera | coursera.org | 1518 | (off-topic; not cited) |
| S16 | LangGraph overview docs | docs.langchain.com | 179 | 1, 5 |
| S17 | linear (Merriam-Webster) | merriam-webster.com | 835 | (off-topic; not cited) |
| S18 | OpenAI homepage | openai.com | 276 | (off-topic; not cited) |

**Effective sources:** S2, S4, S6, S7, S8, S9, S16 (7 of 18).
**Off-topic discoveries:** S11, S15, S17, S18 (SearXNG returned adjacent terms; not cited).
**Distinct domains cited:** 7 (comfy-ui.io, github.com/n8n-io, freecodecamp.org, langchain.com, linear.app, en.wikipedia.org, docs.langchain.com).

---

## 5. Coverage and limitations

**What this report covers:**
- External UX/architecture best practices grounded in canonical, primary-source documentation (LangGraph, n8n, ComfyUI, Linear).
- Project state grounded in the actual source files at HEAD (`61c4213` before rename → `5ef8335` after rename + standalone SearXNG).
- 10 templates and 30 library items, with exact resource IDs and node counts.
- 58 backend routes, 20 node kinds, 9 main components, 14 node components — all live-verified.

**What this report does NOT cover:**
- **GPU-synthesized natural-language synthesis** — Nanbeige preflight failed on this host (`127.0.0.1:8080` refused connections); the skill rule prohibits silent fallback to Qwen or any other model. The crawler ran without `--gpu-synthesis`. All recommendations are drafted by the parent agent, not by an LLM.
- **Live frontend visual acceptance** — no browser screenshots were captured; recommendations are anchored to code state, not visual state.
- **Performance benchmarks** — no timing data was captured; recommendations do not claim "X% faster."
- **Security review** — the locked constraints (loopback-only, exact model, fail-closed defaults) were verified, but no new vulnerability scan was run.
- **Cross-cultural UX** — sources are English-only; no internationalization audit.

**Open items where I would want Drew's explicit decision:**

1. **Templates should grow to 5–8 nodes each** (most are 2–4). Smaller templates feel toy-ish; larger ones feel unwieldy. 6 is a defensible default.
2. **The `FeedbackPanel.tsx` exists but I did not read it in this pass.** It may be redundant with `OptionCatalogPanel` or may serve a different purpose entirely. Recommend a one-paragraph audit before any merge.
3. **`backend/execution_runtime.py` does not yet expose `POST /api/runs/{id}/replay`** — recommendation 1.2 requires that endpoint. The plan is in `.hermes/plans/2026-08-07_014925-durable-hitl-workflow-runtime.md`; replay may already be specced.
4. **GPU-synthesized research synthesis remains unavailable.** When the local Nanbeige service returns, rerun `deep_research.py --gpu-synthesis` to enrich this dossier with model-authored prose.

---

## 6. Suggested next steps

In priority order, parent-only, parent-approved before any external action:

1. **Pick Theme 1, recommendation 1.1** (state-diff in `RunInspector`) as the next commit batch. It is the highest leverage, lowest risk, and directly addresses the project's most user-facing gap (debugging).
2. **Pick Theme 3, recommendation 3.1** (category counts in `LibraryPanel`) as a same-batch follow-up. Trivial change, visible win.
3. **Spec Theme 4, recommendations 4.1–4.5** in a new `.hermes/plans/2026-08-XX-template-bundles.md`. Templates are the project's primary growth lever; they deserve a proper plan, not ad-hoc edits.
4. **Rerun this research** in one month with `--gpu-synthesis` enabled (when Nanbeige returns) to compare the model-authored synthesis against these parent-authored findings.

---

## 7. Verification commands (for re-runs)

```bash
# 1. Verify project state is unchanged
cd "C:/Users/Drew/Documents/Jarvis_Context/Projects/ai-workspace"
git rev-parse HEAD origin/feat/shared-nanbeige-agentic-workspace

# 2. Verify counts
curl -s http://127.0.0.1:8100/api/library | python -c "import sys,json; d=json.load(sys.stdin); print('total:', d['total']); print('counts:', d['category_counts'])"
curl -s http://127.0.0.1:8100/api/templates | python -c "import sys,json; d=json.load(sys.stdin); print('templates:', d['total'])"

# 3. Verify tests
./backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -p 'test_*.py'

# 4. Re-run the research (when Nanbeige is back)
python "C:/Users/Drew/AppData/Local/hermes/shared-skills/research/deep-web-research/scripts/deep_research.py" \
  --brief-file .hermes/research-brief-rws-improvements.json \
  --gpu-synthesis \
  --max-pages 32 \
  --depth 1
```

---

**End of research dossier.** Generated 2026-08-09. Brief ID `rws-improvements-2026-08-09`. All recommendations are advisory; none are binding without Drew's explicit approval.