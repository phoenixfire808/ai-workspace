# M⊕ AI Visual Workspace

A local-first visual workflow builder for connecting Start, Buzz transcription, coder-model, file I/O, task, and allowlisted agent-reaction nodes. The frontend is Next.js 15 + React Flow; the backend is FastAPI + LangGraph + SQLite.

## Runtime boundary

- Windows 10/11 is the supported target.
- The workspace root is `ai-workspace/`; the backend constrains file reads/writes to `WORKSPACE_ROOT`.
- Run events contain node IDs, types, statuses, bounded timings, and failure classes only. Do not put transcript text, audio, file contents, credentials, or prompt contents in logs.
- Buzz/Whisper and the Nanbeige coder route share the RTX 2070 SUPER listener; the small model is served once and reused by SearXNG synthesis and M⊕ workflows.
- Agent Reaction nodes accept only named commands from `WORKSPACE_AGENT_COMMANDS`; canvas text is sent over stdin and is never treated as shell syntax.
- No implicit cloud or credential fallback is enabled.

Nanbeige4.2-3B is the selected local coder route because Drew explicitly rejected Qwen 2.5 Coder. M⊕ reuses the exact alias `nanbeige4.2-3b-local` through the shared loopback listener at `127.0.0.1:8080` on the RTX 2070 SUPER. MiniMax-M3 and Ollama remain explicit alternates, not silent fallbacks.

## Directory layout

```text
ai-workspace/
├── backend/
│   ├── .env.example
│   ├── agent_engine.py
│   ├── database.py
│   ├── graph.py
│   ├── hermes_adapter.py
│   ├── main.py
│   ├── runtime_control.py
│   ├── terminal_control.py
│   ├── tools.py
│   ├── upgrade_control.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── ChatPanel.tsx
│   │   ├── Canvas.tsx
│   │   ├── ControlCenterPanel.tsx
│   │   └── nodes/
│   ├── package.json
│   └── tailwind.config.ts
├── PROJECT_TRACKER.md
├── START_BACKEND.cmd
└── START_FRONTEND.cmd
```

## Setup

### 1. Backend environment

From the workspace root in a Windows terminal:

```cmd
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The project does not read secrets from source-controlled files. Set provider values in the terminal that launches FastAPI, or copy `backend\.env.example` to the ignored local file `backend\.env` and fill it there:

```cmd
set WORKSPACE_MODEL_PROVIDER=nanbeige
set WORKSPACE_MODEL_TIMEOUT_SECONDS=180
set NANBEIGE_BASE_URL=http://127.0.0.1:8080/v1
set NANBEIGE_MODEL=nanbeige4.2-3b-local
```

Ensure the shared Nanbeige/SearXNG listener is running before executing a real Coder workflow:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File D:\AI\Runtimes\nanbeige-launcher\Start-NanbeigeDeepResearch.ps1
```

For an explicitly configured MiniMax route instead:

```cmd
set WORKSPACE_MODEL_PROVIDER=minimax
set MINIMAX_MODEL=MiniMax-M3
set MINIMAX_BASE_URL=<your explicit OpenAI-compatible MiniMax endpoint>
set MINIMAX_API_KEY=<enter locally; do not commit or paste into chat>
```

For an Ollama-only local run, use the explicit alternate instead:

```cmd
set WORKSPACE_MODEL_PROVIDER=ollama
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=<an explicitly configured local model>
```

Changing provider variables never creates automatic fallback. Nanbeige endpoint/model failures stay Nanbeige failures; missing MiniMax configuration returns `minimax_not_configured`; Ollama failures stay local Ollama failures.

Optional local settings are documented in `backend\.env.example`. `backend\.env` is loaded automatically without overriding values already present in the process environment, and is excluded by `.gitignore`.

### 2. Frontend environment

```cmd
cd frontend
npm install
```

The frontend defaults to `http://127.0.0.1:8000`. To point it at another local backend before building, set:

```cmd
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Run

Start the shared on-demand Nanbeige listener, then use two terminals from the workspace root:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File D:\AI\Runtimes\nanbeige-launcher\Start-NanbeigeDeepResearch.ps1
START_BACKEND.cmd
START_FRONTEND.cmd
```

Or run directly:

```cmd
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://localhost:3000`. The backend health endpoint is `http://127.0.0.1:8000/api/health`.

## First workflow

1. Keep the default Start → Coder graph or drag nodes from the palette.
2. Select the Coder provider/model in the Coder node. Nanbeige4.2-3B is the default; MiniMax and Ollama must be selected explicitly.
3. Use **Validate** before running.
4. Use **Save Workspace** to persist the React Flow `nodes`/`edges` JSON in SQLite.
5. Use **Execute Flow**. The canvas consumes `POST /api/execute` as an SSE stream and shows metadata-only node progress in the floating terminal.
6. Read the final output in the right-hand panel.

## Agent chat, Planner, and cyclic execution

The right-hand **Local coding loop** panel is an opt-in LFM chat surface over `POST /api/chat/stream`. It streams visible answer tokens plus bounded tool lifecycle metadata. The agent state persists conversation and tool results across a bounded LangGraph cycle:

```text
agent → approved tool → tool-output capture → agent → finish / approval / loop-limit
```

Read-only workspace inspection tools can run without a prompt approval. Python computation and Hermes skill dispatch pause the stream and show an **Approve and resume** action. The approval action currently resubmits the prompt with the selected tool allowlisted for that turn; durable checkpoint/time-travel resume is a later milestone.

The **Planner** node can be placed between Buzz and Coder (or used with typed Start input) to convert conversational intent into a structured goal, assumptions, ordered steps, risks, and verification checklist. Planner generation uses the explicit local Nanbeige route and does not write files or execute commands.

The LFM route is separate and opt-in. Configure its loopback endpoint and exact model identity only when an LFM listener has been intentionally provisioned:

```cmd
set LFM_BASE_URL=http://127.0.0.1:8082/v1
set LFM_MODEL=LFM2.5-2.6B
```

Every LFM generation performs `/v1/models` preflight and fails closed on an unavailable endpoint or mismatched model. It never silently falls back to Nanbeige.

## Runtime Control, Terminal Preview, and Upgrade Center

The right-hand **Control Center** exposes named GPU/model profiles and read-only preflight. The `ollama-local-models` profile is the priority selection lane and lists exact IDs from local Ollama; the verified `nanbeige-rtx2070-super` profile remains the protected baseline. The approved RTX 5060 Ti M⊕ workspace target (`:8081` / `nanbeige4.2-3b-workspace`), dual-GPU review profile, and LFM experimental profile are data-only until an explicit activation workflow is designed and approved.

The current terminal surface is intentionally a **preview/classifier**, not a command runner. `POST /api/terminal/preview` rejects credentials, shell chaining, redirection, network commands, process-control commands, destructive commands, and out-of-workspace working directories. It never executes the submitted command. A future interactive terminal must add explicit process ownership, approval, cancellation, output caps, and environment filtering before execution is enabled.

The Upgrade Center is also read-only in this slice. It inventories local manifests/artifacts and checks disk, manifest, and active-baseline readiness. Downloads, builds, service changes, activation, and rollback require a separate explicit mutation workflow with backup and verification receipts.

Useful API routes:

- `GET /api/health`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `POST /api/workflows/validate`
- `POST /api/workflows/run` — bounded JSON execution response
- `POST /api/execute` — SSE execution stream
- `GET /api/chat/tools` — governed local/Hermes tool catalog
- `POST /api/chat/stream` — opt-in cyclic LFM chat/tool SSE stream
- `GET /api/ollama/models` — exact installed Ollama inventory from loopback `/api/tags` + `/v1/models`
- `POST /api/ollama/preflight` — exact Ollama model readiness check; no pull/delete/start action
- `GET /api/runtime/profiles` — named data-only GPU/model profiles
- `GET /api/runtime/profiles/{id}/preflight` — exact local identity/readiness check
- `POST /api/terminal/preview` — bounded no-execution command classification
- `GET /api/upgrades/inventory` — local upgrade inventory, no downloads
- `GET /api/upgrades/preflight` — manifest/disk/baseline readiness check
- `GET /api/tasks`
- `GET /api/agents`

## Local integrations

Buzz nodes accept a workspace-relative audio path. The backend invokes:

```text
buzz add --task transcribe --model-type whispercpp --model-size <size> --txt <file_path>
```

The Buzz executable can be configured with `BUZZ_EXECUTABLE`. The backend will fail closed if the file is outside `WORKSPACE_ROOT`, the extension is unsupported, Buzz is unavailable, or the transcript output is missing.

Agent reactions require a JSON object in `WORKSPACE_AGENT_COMMANDS`, for example:

```cmd
set WORKSPACE_AGENT_COMMANDS={"local-coder":["python","tools\\local_coder.py"]}
```

Only configured target names can run. Never place credentials or arbitrary shell text in this variable.

Hermes integration is read-only by default. Skill discovery reads only local `SKILL.md` files under `HERMES_SKILLS_ROOT` (or the active personal profile's skills directory); it does not expose Hermes auth, sessions, memory, or config. Optional dispatch requires an explicit `HERMES_SKILL_COMMANDS` JSON map and a per-run approval:

```cmd
set HERMES_SKILLS_ROOT=C:\Users\Drew\AppData\Local\hermes\profiles\personal\skills
set HERMES_SKILL_COMMANDS={"software-development/local-realtime-application-hardening":["python","tools\\run_skill_adapter.py"]}
```

The Python computation tool is a bounded same-user subprocess policy layer, not a VM or container security boundary. It has an allowlisted standard-library import set, filtered environment, workspace CWD, output cap, timeout, and approval gate. It must not be treated as unrestricted computer access.

## Verification

After installation, perform the final consolidated pass:

```cmd
backend\.venv\Scripts\python.exe -m py_compile backend\database.py backend\schema.py backend\graph.py backend\main.py
cd frontend
npm run typecheck
npm run build
```

Then start both services and smoke:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File D:\AI\Runtimes\nanbeige-launcher\Status-NanbeigeDeepResearch.ps1
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8000/api/health
```

Use the browser UI to validate, save, load, and execute a Start-only or Start → File workflow before attempting a real Nanbeige, MiniMax, Ollama, Buzz, microphone, or GPU acceptance. Real Buzz/GPU acceptance is separate and must not be inferred from synthetic graph smoke.

## Troubleshooting

- **API disconnected:** start FastAPI on port 8000 and check `/api/health`.
- **`nanbeige_unavailable` / `nanbeige_model_mismatch`:** start the shared SearXNG Nanbeige listener and verify that `/v1/models` advertises `nanbeige4.2-3b-local`.
- **`minimax_not_configured`:** set `MINIMAX_BASE_URL`, `MINIMAX_API_KEY`, and `MINIMAX_MODEL` in the launching terminal, or select Nanbeige/Ollama explicitly.
- **Ollama timeout:** verify the local Ollama server and `/api/tags`; the workspace does not silently switch providers.
- **Buzz unavailable:** configure `BUZZ_EXECUTABLE` or add Buzz to the backend process PATH. The GUI will report `buzz_unavailable`.
- **CORS:** use `http://localhost:3000` or `http://127.0.0.1:3000`, both included in the default CORS list.
- **Path denied:** move the requested file under `WORKSPACE_ROOT`; arbitrary Windows paths are intentionally rejected.

The detailed roadmap and append-only implementation history live in `PROJECT_TRACKER.md`.
