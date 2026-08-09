from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from .ollama_control import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, safe_ollama_base_url


class GpuLane(BaseModel):
    lane_id: str
    label: str
    physical_gpu_index: int | None = None
    compute_capability: str | None = None
    cuda_visible_devices: str | None = None
    endpoint: str | None = None
    model: str | None = None
    slots: int | None = Field(default=None, ge=0, le=16)


class RuntimeProfile(BaseModel):
    schema_version: int = 1
    profile_id: str
    label: str
    provider: str
    model: str
    mode: str
    state: str
    context: int | None = Field(default=None, ge=0, le=1_000_000)
    limits: dict[str, int] = Field(default_factory=dict)
    activation_allowed: bool = False
    lanes: list[GpuLane]
    notes: str


PROFILES: tuple[RuntimeProfile, ...] = (
    RuntimeProfile(
        profile_id="ollama-local-models",
        label="M⊕ workspace model · Ollama",
        provider="ollama",
        model=DEFAULT_OLLAMA_MODEL,
        mode="local-server",
        state="active-local",
        context=32_768,
        limits={"max_tokens": 8_192, "timeout_seconds": 180},
        activation_allowed=True,
        lanes=[
            GpuLane(
                lane_id="ollama-local",
                label="Ollama local model server",
                endpoint=f"{DEFAULT_OLLAMA_BASE_URL}/v1",
                model=DEFAULT_OLLAMA_MODEL,
                slots=1,
            )
        ],
        notes="Persistent global model selection comes from installed Ollama inventory. Node and workflow overrides remain explicit; no Nanbeige or cloud fallback is permitted.",
    ),
)


def _profile(profile_id: str) -> RuntimeProfile:
    for profile in PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(profile_id)


def list_runtime_profiles() -> list[dict[str, Any]]:
    return [profile.model_dump(mode="json") for profile in PROFILES]


def _safe_loopback_endpoint(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("endpoint must be an unauthenticated http://127.0.0.1:<port>/v1 URL")
    return f"http://127.0.0.1:{parsed.port}/v1"


def _model_preflight(endpoint: str | None, expected_model: str) -> dict[str, Any]:
    if not endpoint:
        return {"status": "not-provisioned", "exact_model": False, "model_ids": []}
    try:
        if endpoint.rstrip("/") == f"{DEFAULT_OLLAMA_BASE_URL}/v1":
            safe_endpoint = f"{safe_ollama_base_url()}/v1"
        else:
            safe_endpoint = _safe_loopback_endpoint(endpoint)
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            response = client.get(f"{safe_endpoint}/models")
            response.raise_for_status()
            payload = response.json()
        model_ids = [
            item["id"]
            for item in payload.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        exact = expected_model in model_ids
        return {"status": "ready" if exact else "model-mismatch", "exact_model": exact, "model_ids": model_ids[:20]}
    except httpx.TimeoutException:
        return {"status": "timeout", "exact_model": False, "model_ids": []}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {"status": "unavailable", "exact_model": False, "model_ids": []}


def preflight_runtime_profile(profile_id: str) -> dict[str, Any]:
    try:
        profile = _profile(profile_id)
    except KeyError:
        return {"profile_id": profile_id, "status": "profile-not-found", "checks": []}
    checks: list[dict[str, Any]] = [
        {"name": "activation_policy", "ok": profile.activation_allowed, "detail": profile.state},
        {"name": "gpu_lane_declaration", "ok": bool(profile.lanes), "detail": f"{len(profile.lanes)} declared lane(s)"},
    ]
    endpoints = []
    for lane in profile.lanes:
        if lane.endpoint:
            endpoint_result = _model_preflight(lane.endpoint, lane.model or profile.model)
            endpoints.append({"lane_id": lane.lane_id, **endpoint_result})
            checks.append({"name": f"endpoint:{lane.lane_id}", "ok": endpoint_result["exact_model"], "detail": endpoint_result["status"]})
    status = "ready" if all(check["ok"] for check in checks) else "not-ready"
    return {
        "profile_id": profile.profile_id,
        "provider": profile.provider,
        "model": profile.model,
        "state": profile.state,
        "status": status,
        "checks": checks,
        "endpoints": endpoints,
        "mutation": "none",
    }


def active_baseline_profile_id() -> str:
    return "ollama-local-models"


__all__ = ["active_baseline_profile_id", "list_runtime_profiles", "preflight_runtime_profile"]
