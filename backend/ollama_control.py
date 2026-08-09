from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M"


class OllamaModel(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    size: int | None = Field(default=None, ge=0)
    digest: str | None = Field(default=None, max_length=128)
    modified_at: str | None = Field(default=None, max_length=80)
    openai_advertised: bool = False


class OllamaPreflightPayload(BaseModel):
    model: str = Field(default="", max_length=500)


def safe_ollama_base_url(raw: str | None = None) -> str:
    value = (raw if raw is not None else os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)).strip().rstrip("/")
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    docker_service = (
        os.getenv("WORKSPACE_DOCKER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        and hostname == "ollama"
    )
    # host.docker.internal is allowed regardless of docker_mode because it
    # resolves to the Docker Desktop host loopback. Ollama and SearXNG both
    # run as standalone containers on the host (rws-ollama on :11435,
    # searxng-hermes on :8888) and are reached via this hostname from inside
    # the backend container.
    host_docker_internal = hostname == "host.docker.internal"
    if (
        parsed.scheme != "http"
        or (hostname != "127.0.0.1" and not docker_service and not host_docker_internal)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "OLLAMA_BASE_URL must be an unauthenticated loopback URL, host.docker.internal, "
            "or the Docker ollama service when WORKSPACE_DOCKER_MODE=1"
        )
    return f"http://{hostname}:{parsed.port}"


def _failure_result(base_url: str, status: str, failure_class: str) -> dict[str, Any]:
    return {
        "status": status,
        "failure_class": failure_class,
        "base_url": base_url,
        "models": [],
        "openai_models": [],
        "default_model": DEFAULT_OLLAMA_MODEL,
        "approved_model": DEFAULT_OLLAMA_MODEL,
        "allowed_models": [DEFAULT_OLLAMA_MODEL],
        "model_policy": "exact_only",
        "mutation": "none",
    }


def list_ollama_models() -> dict[str, Any]:
    try:
        base_url = safe_ollama_base_url()
    except ValueError:
        return _failure_result("", "invalid-endpoint", "ollama_endpoint_invalid")

    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            tags_response = client.get(f"{base_url}/api/tags")
            tags_response.raise_for_status()
            tags_payload = tags_response.json()
            models_payload: dict[str, Any] = {}
            try:
                models_response = client.get(f"{base_url}/v1/models")
                models_response.raise_for_status()
                candidate = models_response.json()
                if isinstance(candidate, dict):
                    models_payload = candidate
            except httpx.HTTPError:
                # Tags remain the canonical local inventory; OpenAI compatibility is reported per model.
                models_payload = {}
    except httpx.TimeoutException:
        return _failure_result(base_url, "timeout", "ollama_timeout")
    except httpx.ConnectError:
        return _failure_result(base_url, "unavailable", "ollama_unavailable")
    except (httpx.HTTPError, TypeError, ValueError):
        return _failure_result(base_url, "invalid-response", "ollama_inventory_invalid")

    if not isinstance(tags_payload, dict) or not isinstance(tags_payload.get("models"), list):
        return _failure_result(base_url, "invalid-response", "ollama_inventory_invalid")
    openai_ids = {
        item.get("id")
        for item in models_payload.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    models: list[dict[str, Any]] = []
    for item in tags_payload["models"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        try:
            model = OllamaModel(
                name=item["name"],
                size=item.get("size"),
                digest=item.get("digest"),
                modified_at=item.get("modified_at"),
                openai_advertised=item["name"] in openai_ids,
            )
        except Exception:
            continue
        models.append(model.model_dump(mode="json"))
    names = [item["name"] for item in models]
    return {
        "status": "ready",
        "failure_class": None,
        "base_url": base_url,
        "models": models,
        "openai_models": sorted(openai_ids),
        "default_model": DEFAULT_OLLAMA_MODEL,
        "approved_model": DEFAULT_OLLAMA_MODEL,
        "allowed_models": [DEFAULT_OLLAMA_MODEL],
        "model_policy": "exact_only",
        "mutation": "none",
    }


def preflight_ollama_model(model: str | None = None) -> dict[str, Any]:
    requested = (model or os.getenv("OLLAMA_MODEL", "").strip() or DEFAULT_OLLAMA_MODEL).strip()
    if requested != DEFAULT_OLLAMA_MODEL:
        return {
            "status": "model-policy-mismatch",
            "failure_class": "ollama_exact_model_required",
            "base_url": "",
            "models": [],
            "openai_models": [],
            "default_model": DEFAULT_OLLAMA_MODEL,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "allowed_models": [DEFAULT_OLLAMA_MODEL],
            "model_policy": "exact_only",
            "model": requested,
            "exact_model": False,
            "mutation": "none",
        }
    inventory = list_ollama_models()
    names = {item["name"] for item in inventory.get("models", []) if isinstance(item, dict) and isinstance(item.get("name"), str)}
    openai_names = set(inventory.get("openai_models", []))
    if inventory.get("status") != "ready":
        return {**inventory, "model": requested, "exact_model": False}
    if requested not in names:
        return {**inventory, "status": "model-mismatch", "failure_class": "ollama_model_mismatch", "model": requested, "exact_model": False}
    if openai_names and requested not in openai_names:
        return {**inventory, "status": "openai-model-mismatch", "failure_class": "ollama_openai_model_mismatch", "model": requested, "exact_model": False}
    return {**inventory, "status": "ready", "failure_class": None, "model": requested, "exact_model": True}


def list_ollama_running_models() -> dict[str, Any]:
    """Return models currently loaded in VRAM (read-only Ollama /api/ps).

    Returns a structured dict with status, base_url, models list (each with
    name, size_vram, expires_at), and the default / approved model markers.
    Never mutates Ollama state. If Ollama is unreachable, returns an
    explicit unavailable status instead of raising.
    """
    try:
        base_url = safe_ollama_base_url()
    except ValueError:
        return {
            "status": "invalid-endpoint",
            "failure_class": "ollama_endpoint_invalid",
            "base_url": "",
            "models": [],
            "default_model": DEFAULT_OLLAMA_MODEL,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "model_policy": "exact_only",
        }
    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            response = client.get(f"{base_url}/api/ps")
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "failure_class": "ollama_timeout",
            "base_url": base_url,
            "models": [],
            "default_model": DEFAULT_OLLAMA_MODEL,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "model_policy": "exact_only",
        }
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "failure_class": "ollama_unavailable",
            "base_url": base_url,
            "models": [],
            "default_model": DEFAULT_OLLAMA_MODEL,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "model_policy": "exact_only",
        }
    except (httpx.HTTPError, TypeError, ValueError):
        return {
            "status": "invalid-response",
            "failure_class": "ollama_ps_invalid",
            "base_url": base_url,
            "models": [],
            "default_model": DEFAULT_OLLAMA_MODEL,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "model_policy": "exact_only",
        }
    raw_models = payload.get("models", []) if isinstance(payload, dict) else []
    models: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        models.append(
            {
                "name": item["name"],
                "model": item.get("model", item["name"]),
                "size_vram": item.get("size_vram"),
                "size": item.get("size"),
                "digest": item.get("digest"),
                "details": item.get("details", {}),
                "expires_at": item.get("expires_at"),
            }
        )
    return {
        "status": "ready",
        "failure_class": None,
        "base_url": base_url,
        "models": models,
        "default_model": DEFAULT_OLLAMA_MODEL,
        "approved_model": DEFAULT_OLLAMA_MODEL,
        "model_policy": "exact_only",
    }


def preload_ollama_model(model: str, keep_alive: str = "5m") -> dict[str, Any]:
    """Load an exact Ollama model into VRAM via Ollama /api/generate with keep_alive.

    Uses an empty prompt + keep_alive to force the model to load without
    producing a generation. The exact-model policy is honored: the
    requested model must equal DEFAULT_OLLAMA_MODEL. Unrecognized tags
    return a structured failure rather than loading anything.
    """
    requested = (model or "").strip()
    if not requested:
        return {
            "status": "invalid-model",
            "failure_class": "ollama_exact_model_required",
            "model": requested,
            "exact_model": False,
            "mutation": "none",
        }
    if requested != DEFAULT_OLLAMA_MODEL:
        return {
            "status": "model-policy-mismatch",
            "failure_class": "ollama_exact_model_required",
            "model": requested,
            "exact_model": False,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "mutation": "none",
        }
    try:
        base_url = safe_ollama_base_url()
    except ValueError:
        return {
            "status": "invalid-endpoint",
            "failure_class": "ollama_endpoint_invalid",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    payload = {
        "model": requested,
        "prompt": "",
        "stream": False,
        "keep_alive": keep_alive,
    }
    try:
        with httpx.Client(timeout=180.0, trust_env=False) as client:
            response = client.post(f"{base_url}/api/generate", json=payload)
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "failure_class": "ollama_timeout",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "failure_class": "ollama_unavailable",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    if response.status_code >= 400:
        return {
            "status": "error",
            "failure_class": f"ollama_http_{response.status_code}",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
            "detail": response.text[:500],
        }
    return {
        "status": "preloaded",
        "failure_class": None,
        "model": requested,
        "exact_model": True,
        "keep_alive": keep_alive,
        "mutation": "preload",
        "base_url": base_url,
    }


def unload_ollama_model(model: str) -> dict[str, Any]:
    """Unload an exact Ollama model from VRAM immediately (keep_alive=0).

    Symmetric counterpart to preload_ollama_model. The exact-model policy
    still applies: only the approved exact tag is accepted for unload.
    Ollama accepts unload requests for any currently-loaded model, but
    the policy here mirrors preload so the UI never silently operates on
    a non-exact tag.
    """
    requested = (model or "").strip()
    if not requested:
        return {
            "status": "invalid-model",
            "failure_class": "ollama_exact_model_required",
            "model": requested,
            "exact_model": False,
            "mutation": "none",
        }
    if requested != DEFAULT_OLLAMA_MODEL:
        return {
            "status": "model-policy-mismatch",
            "failure_class": "ollama_exact_model_required",
            "model": requested,
            "exact_model": False,
            "approved_model": DEFAULT_OLLAMA_MODEL,
            "mutation": "none",
        }
    try:
        base_url = safe_ollama_base_url()
    except ValueError:
        return {
            "status": "invalid-endpoint",
            "failure_class": "ollama_endpoint_invalid",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    payload = {
        "model": requested,
        "prompt": "",
        "stream": False,
        "keep_alive": "0",
    }
    try:
        with httpx.Client(timeout=60.0, trust_env=False) as client:
            response = client.post(f"{base_url}/api/generate", json=payload)
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "failure_class": "ollama_timeout",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "failure_class": "ollama_unavailable",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
        }
    if response.status_code >= 400:
        return {
            "status": "error",
            "failure_class": f"ollama_http_{response.status_code}",
            "model": requested,
            "exact_model": True,
            "mutation": "none",
            "detail": response.text[:500],
        }
    return {
        "status": "unloaded",
        "failure_class": None,
        "model": requested,
        "exact_model": True,
        "keep_alive": "0",
        "mutation": "unload",
        "base_url": base_url,
    }


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "OllamaPreflightPayload",
    "list_ollama_models",
    "list_ollama_running_models",
    "preflight_ollama_model",
    "preload_ollama_model",
    "safe_ollama_base_url",
    "unload_ollama_model",
]
