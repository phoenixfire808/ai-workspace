from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "hf.co/DavidAU/Qwen3.6-27B-Fable-Fusion-711-Uncensored-Heretic-NM-DAU-NEO-MAX-MTP-GGUF:Q4_K_M"


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
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("OLLAMA_BASE_URL must be an unauthenticated http://127.0.0.1:<port> URL")
    return f"http://127.0.0.1:{parsed.port}"


def _failure_result(base_url: str, status: str, failure_class: str) -> dict[str, Any]:
    return {
        "status": status,
        "failure_class": failure_class,
        "base_url": base_url,
        "models": [],
        "openai_models": [],
        "default_model": os.getenv("OLLAMA_MODEL", "").strip() or DEFAULT_OLLAMA_MODEL,
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
    configured = os.getenv("OLLAMA_MODEL", "").strip()
    default_model = configured if configured in names else (names[0] if names else DEFAULT_OLLAMA_MODEL)
    return {
        "status": "ready",
        "failure_class": None,
        "base_url": base_url,
        "models": models,
        "openai_models": sorted(openai_ids),
        "default_model": default_model,
        "mutation": "none",
    }


def preflight_ollama_model(model: str | None = None) -> dict[str, Any]:
    inventory = list_ollama_models()
    requested = (model or os.getenv("OLLAMA_MODEL", "").strip() or inventory.get("default_model") or DEFAULT_OLLAMA_MODEL).strip()
    names = {item["name"] for item in inventory.get("models", []) if isinstance(item, dict) and isinstance(item.get("name"), str)}
    openai_names = set(inventory.get("openai_models", []))
    if inventory.get("status") != "ready":
        return {**inventory, "model": requested, "exact_model": False}
    if requested not in names:
        return {**inventory, "status": "model-mismatch", "failure_class": "ollama_model_mismatch", "model": requested, "exact_model": False}
    if openai_names and requested not in openai_names:
        return {**inventory, "status": "openai-model-mismatch", "failure_class": "ollama_openai_model_mismatch", "model": requested, "exact_model": False}
    return {**inventory, "status": "ready", "failure_class": None, "model": requested, "exact_model": True}


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "OllamaPreflightPayload",
    "list_ollama_models",
    "preflight_ollama_model",
    "safe_ollama_base_url",
]
