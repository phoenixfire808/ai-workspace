# Refactor Workflow Studio Docker Runbook

## Status

- **Target:** Docker Compose for the Refactor Workflow Studio frontend, FastAPI backend, and exact local Ollama model.
- **SearXNG is intentionally OUT of this compose.** SearXNG runs as its own standalone container (`searxng-hermes`, image `searxng/searxng:latest`) on the host loopback at `127.0.0.1:8888`. The backend reaches it via `host.docker.internal:8888` from inside its container.
- **Local-only boundary:** all published ports are bound to `127.0.0.1`; no cloud model fallback is enabled.
- **Exact model:** `hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M`.
- **Rollback baseline:** the verified native frontend/backend/Ollama launch remains available until Docker acceptance completes.
- **Separate native boundary:** Buzz/GlitchScribe microphone and Windows-native integration are not claimed as Linux-containerized. A full WSL/audio migration is a separate high-risk project.

## Services

| Service | Container | Internal port | Default host port | Persistence |
|---|---|---:|---:|---|
| Frontend | `rws-frontend` | 3000 | 3000 | image build |
| FastAPI | `rws-backend` | 8000 | 8000 | `./` mounted at `/workspace` |
| Ollama | `rws-ollama` | 11434 | 11434 | host Ollama store `C:/Users/Drew/.ollama` |
| SearXNG (standalone) | `searxng-hermes` | 8080 | 8888 | its own container, not this compose |

For non-disruptive acceptance while native services occupy the default ports, use a temporary env file with host ports `3100`, `8100`, and `11435`. SearXNG is independent of this compose and stays on its existing host port `8888`. Do not stop `searxng-hermes` unless an explicit approval is given.

## First launch

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker config
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail=100 backend frontend ollama
```

The `ollama-model` one-shot service verifies the exact model in the host-bound Ollama store before the backend starts. It must finish successfully; no alternate model is permitted.

## Acceptance

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8888/search?q=local+AI\&format=json
curl http://127.0.0.1:3000
```

SearXNG on `:8888` is the standalone `searxng-hermes` container — it is not
started or stopped by this compose. If you want to manage it explicitly, use
the standalone file at `docker/searxng/compose.yml`.

Then verify the browser UI reports `ollama` plus the exact LFM tag, run one controlled `/api/debug/llm-test`, validate one one-node graph, and inspect `docker compose ps` for healthy services. Do not treat a container being `Up` as model acceptance.

## Cutover and rollback

1. Record exact native PIDs and confirm the Docker smoke is green.
2. Stop only the native Refactor Workflow Studio frontend/backend owners; the standalone `searxng-hermes` container is unrelated to this compose and must stay running.
3. Start Compose with the default ports and re-run the acceptance batch.
4. Roll back with `docker compose --env-file .env.docker down` (do not add `--volumes`), restart the preserved native launchers, and recheck the original health/model receipts.

Never run `docker compose down --volumes` during ordinary rollback: it deletes any persisted volumes. The Ollama model store is a host bind mount and is preserved independently. SearXNG runs in its own container (`searxng-hermes`) and is unaffected by this compose.

## Research receipts

- Docker Compose GPU reservations: <https://docs.docker.com/compose/gpu-support/>
- Ollama Docker and NVIDIA guidance: <https://docs.ollama.com/docker>
- NVIDIA Container Toolkit: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>
- SearXNG container deployment: <https://docs.searxng.org/admin/installation-docker.html>
- Next.js deployment: <https://nextjs.org/docs/app/building-your-application/deploying>

## Receipts

- 2026-08-07: Docker Engine 29.3.1, Compose v5.1.0, NVIDIA 591.44, RTX 5060 Ti + RTX 2070 SUPER visible.
- 2026-08-07: Existing `searxng-hermes` healthy at loopback `127.0.0.1:8888`; direct JSON search returned HTTP 200.
- 2026-08-07: Compose rendered successfully with five services on smoke ports; native services intentionally preserved.
- 2026-08-07: First frontend image build reached a successful Next.js production build but failed on an invalid copy of absent `frontend/public/`; the Dockerfile was corrected to omit that optional directory.
- 2026-08-08: Docker Ollama detected both host GPUs with CUDA. The initial model init command was corrected from `ollama ollama pull` to the image's proper `pull` entrypoint.
- 2026-08-08: SearXNG now starts with a Docker-specific non-default secret; the native `SearXNG-Hermes/config` remains untouched.
- 2026-08-08: Exact LFM manifest/blob verified in `C:/Users/Drew/.ollama/models`; Compose now binds that existing local store to avoid a redundant 1.7 GB pull.
- 2026-08-08: Backend now routes SearXNG to the Compose `searxng` service on the private Compose network; the native SearXNG network is not a Docker dependency.
- 2026-08-08: Exact-model-only policy added across Ollama preflight, persisted workspace settings, graph execution, endpoint execution, runtime preflight, and frontend controls. Alternate installed models remain non-routable.
- 2026-08-08: First model acceptance attempt closed the host ports after the request; container state reported backend/SearXNG exit 137 with `OOMKilled=false` and frontend exit 143. Treat this as a lifecycle/runtime receipt requiring a persistent Compose-managed retry, not as model success.
- Pending: rebuild corrected backend/frontend images, persistent smoke startup, service health, browser hydration, exact-model smoke, workflow smoke, and cutover.
