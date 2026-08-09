from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .database import HardwareProfile, SessionLocal, WorkspaceModelSetting, utc_now
from .ollama_control import DEFAULT_OLLAMA_MODEL, preflight_ollama_model


class WorkspaceModelPayload(BaseModel):
    provider: Literal["ollama"] = "ollama"
    model: str = Field(default=DEFAULT_OLLAMA_MODEL, min_length=1, max_length=500)
    hardware_profile_id: str = Field(default="auto", min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    fallback_policy: Literal["explicit_only"] = "explicit_only"


def _public(row: WorkspaceModelSetting | None) -> dict[str, Any]:
    if row is None:
        return {
            "provider": "ollama",
            "model": DEFAULT_OLLAMA_MODEL,
            "hardware_profile_id": "auto",
            "fallback_policy": "explicit_only",
            "persisted": False,
            "updated_at": None,
            "mutation": "none",
        }
    return {
        "provider": "ollama",
        "model": row.model if row.model == DEFAULT_OLLAMA_MODEL else DEFAULT_OLLAMA_MODEL,
        "hardware_profile_id": row.hardware_profile_id,
        "fallback_policy": row.fallback_policy,
        "persisted": True,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "mutation": "none",
        "model_policy": "exact_only",
        "legacy_model_rejected": row.model != DEFAULT_OLLAMA_MODEL,
    }


def get_workspace_model_setting() -> dict[str, Any]:
    with SessionLocal() as db:
        return _public(db.get(WorkspaceModelSetting, "global"))


def save_workspace_model_setting(payload: WorkspaceModelPayload) -> dict[str, Any]:
    model = payload.model.strip()
    preflight = preflight_ollama_model(model)
    if preflight.get("status") != "ready" or preflight.get("exact_model") is not True:
        failure = str(preflight.get("failure_class") or "ollama_model_mismatch")
        raise ValueError(f"selected model is not an exact installed Ollama model ({failure})")
    with SessionLocal() as db:
        if payload.hardware_profile_id != "auto" and db.get(HardwareProfile, payload.hardware_profile_id) is None:
            raise ValueError("selected hardware profile does not exist")
        row = db.get(WorkspaceModelSetting, "global")
        if row is None:
            row = WorkspaceModelSetting(id="global", model=model)
            db.add(row)
        row.provider = "ollama"
        row.model = model
        row.hardware_profile_id = payload.hardware_profile_id
        row.fallback_policy = "explicit_only"
        row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        result = _public(row)
    result["mutation"] = "workspace_model_setting_saved"
    result["preflight"] = {
        "status": preflight.get("status"),
        "exact_model": preflight.get("exact_model"),
        "base_url": preflight.get("base_url"),
    }
    return result


def resolve_workspace_model(
    *,
    node_provider: str | None = None,
    node_model: str | None = None,
    workflow_settings: dict[str, Any] | None = None,
) -> dict[str, str]:
    global_setting = get_workspace_model_setting()
    workflow = workflow_settings or {}
    provider = (node_provider or str(workflow.get("model_provider") or "") or str(global_setting["provider"])).strip().lower()
    model = (node_model or str(workflow.get("model") or "") or str(global_setting["model"])).strip()
    if provider == "nanbeige":
        raise ValueError("nanbeige_retired_from_workspace")
    if provider != "ollama":
        raise ValueError("workspace_model_provider_not_supported")
    if not model:
        raise ValueError("workspace_model_missing")
    if model != DEFAULT_OLLAMA_MODEL:
        raise ValueError("workspace_exact_model_required")
    source = "node" if node_model else "workflow" if workflow.get("model") else "global"
    return {"provider": provider, "model": model, "source": source, "fallback_policy": "explicit_only"}


__all__ = [
    "WorkspaceModelPayload",
    "get_workspace_model_setting",
    "resolve_workspace_model",
    "save_workspace_model_setting",
]
