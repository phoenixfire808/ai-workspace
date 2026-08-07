from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from .ollama_control import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL

DEFAULT_NANBEIGE_MODEL = "nanbeige4.2-3b-local"
DEFAULT_NANBEIGE_ENDPOINT = "http://127.0.0.1:8080/v1"
DEFAULT_LFM_MODEL = "LFM2.5-2.6B"
DEFAULT_LFM_ENDPOINT = "http://127.0.0.1:8082/v1"


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
        label="Ollama · installed local models",
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
        notes="Priority local model lane. Select an exact installed ID from the Ollama inventory; no pull, delete, or server mutation is exposed.",
    ),
    RuntimeProfile(
        profile_id="nanbeige-rtx2070-super",
        label="Nanbeige · RTX 2070 SUPER",
        provider="nanbeige",
        model=DEFAULT_NANBEIGE_MODEL,
        mode="single-gpu",
        state="active-baseline",
        context=20_480,
        limits={"max_tokens": 8_192, "timeout_seconds": 180},
        activation_allowed=True,
        lanes=[
            GpuLane(
                lane_id="gpu-1",
                label="NVIDIA GeForce RTX 2070 SUPER",
                physical_gpu_index=1,
                compute_capability="SM75",
                cuda_visible_devices="1",
                endpoint=DEFAULT_NANBEIGE_ENDPOINT,
                model=DEFAULT_NANBEIGE_MODEL,
                slots=2,
            )
        ],
        notes="Verified shared SearXNG/M⊕ listener. Preserve this route unless a replacement passes preflight and rollback gates.",
    ),
    RuntimeProfile(
        profile_id="nanbeige-rtx5060-ti-workspace-target",
        label="Nanbeige M⊕ workspace · RTX 5060 Ti",
        provider="nanbeige",
        model="nanbeige4.2-3b-workspace",
        mode="single-gpu",
        state="target-not-provisioned",
        context=20_480,
        limits={"max_tokens": 8_192, "timeout_seconds": 180},
        activation_allowed=False,
        lanes=[
            GpuLane(
                lane_id="gpu-0",
                label="NVIDIA GeForce RTX 5060 Ti",
                physical_gpu_index=0,
                compute_capability="SM120",
                cuda_visible_devices="0",
                endpoint="http://127.0.0.1:8081/v1",
                model="nanbeige4.2-3b-workspace",
                slots=1,
            )
        ],
        notes="Approved split target for M⊕ while SearXNG remains on :8080. Endpoint :8081 is currently unavailable; no migration or listener mutation has occurred.",
    ),
    RuntimeProfile(
        profile_id="nanbeige-dual-gpu-review",
        label="Nanbeige · dual-GPU review",
        provider="nanbeige",
        model=DEFAULT_NANBEIGE_MODEL,
        mode="dual-gpu",
        state="planned",
        context=20_480,
        limits={"max_tokens": 8_192, "timeout_seconds": 180},
        activation_allowed=False,
        lanes=[
            GpuLane(lane_id="gpu-0", label="RTX 5060 Ti", physical_gpu_index=0, compute_capability="SM120", cuda_visible_devices="0"),
            GpuLane(lane_id="gpu-1", label="RTX 2070 SUPER", physical_gpu_index=1, compute_capability="SM75", cuda_visible_devices="1"),
        ],
        notes="Design placeholder only. Split-model and independent-server meanings remain separate decisions; no implicit dual-GPU activation.",
    ),
    RuntimeProfile(
        profile_id="lfm2-agent-experimental",
        label="LFM2.5-2.6B · explicit agent route",
        provider="lfm",
        model=DEFAULT_LFM_MODEL,
        mode="unassigned-local",
        state="not-provisioned",
        context=32_768,
        limits={"max_tokens": 8_192, "timeout_seconds": 180},
        activation_allowed=False,
        lanes=[
            GpuLane(
                lane_id="unassigned",
                label="Separate local LFM runtime required",
                endpoint=DEFAULT_LFM_ENDPOINT,
                model=DEFAULT_LFM_MODEL,
            )
        ],
        notes="Opt-in only. The endpoint must advertise the exact model before activation; no Nanbeige fallback is permitted.",
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

    if profile.state in {"active-baseline", "active-local"}:
        status = "ready" if all(check["ok"] for check in checks) else "not-ready"
    elif profile.state == "artifact-only":
        status = "artifact-only"
    elif profile.state == "planned":
        status = "planned"
    else:
        status = "not-provisioned"
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
    return "nanbeige-rtx2070-super"


__all__ = ["active_baseline_profile_id", "list_runtime_profiles", "preflight_runtime_profile"]
