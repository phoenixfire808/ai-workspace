from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import uuid
from ctypes import wintypes
from ipaddress import ip_address
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select

from .database import HardwareProfile, ModelEndpointProfile, SessionLocal
from .ollama_control import DEFAULT_OLLAMA_MODEL, safe_ollama_base_url

ProviderKind = Literal["ollama", "ollama_cloud", "ollama_compatible", "openai_compatible", "openrouter"]
HardwareMode = Literal["auto", "cpu", "single_gpu", "multi_gpu"]


class EndpointProfilePayload(BaseModel):
    id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=160)
    provider_kind: ProviderKind
    base_url: str = Field(min_length=1, max_length=1000)
    credential_alias: str = Field(default="", max_length=160)
    settings: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    managed: bool = False


class HardwareProfilePayload(BaseModel):
    id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=160)
    mode: HardwareMode = "auto"
    device_ids: list[str] = Field(default_factory=list, max_length=8)
    settings: dict[str, Any] = Field(default_factory=dict)


_DEFAULT_ENDPOINTS = (
    {"id": "local-ollama", "name": "Refactor Workflow Studio local Ollama", "provider_kind": "ollama", "base_url": "http://127.0.0.1:11434", "credential_alias": "", "settings": {"model": DEFAULT_OLLAMA_MODEL, "fallback_policy": "explicit_only", "keep_alive": "5m"}, "enabled": True, "managed": False},
    {"id": "ollama-cloud", "name": "Ollama Cloud direct", "provider_kind": "ollama_cloud", "base_url": "https://ollama.com", "credential_alias": "env:OLLAMA_API_KEY", "settings": {"fallback_policy": "explicit_only"}, "enabled": False, "managed": False},
    {"id": "openrouter", "name": "OpenRouter · explicit cloud route", "provider_kind": "openrouter", "base_url": "https://openrouter.ai/api/v1", "credential_alias": "env:OPENROUTER_API_KEY", "settings": {"model": "", "fallback_policy": "explicit_only", "x_title": "Refactor Workflow Studio"}, "enabled": False, "managed": False},
)
_DEFAULT_HARDWARE = (
    {"id": "auto", "name": "Automatic placement", "mode": "auto", "device_ids": [], "settings": {"vram_reserve_mb": 1024, "max_loaded_models": 1}},
    {"id": "cpu", "name": "CPU only", "mode": "cpu", "device_ids": [], "settings": {"max_loaded_models": 1}},
)


def _seed_defaults() -> None:
    with SessionLocal() as db:
        for item in _DEFAULT_ENDPOINTS:
            if db.get(ModelEndpointProfile, item["id"]) is None:
                db.add(ModelEndpointProfile(**item))
        for item in _DEFAULT_HARDWARE:
            if db.get(HardwareProfile, item["id"]) is None:
                db.add(HardwareProfile(**item))
        db.commit()


def _normalized_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("endpoint must be an HTTP(S) URL without embedded credentials")
    hostname = parsed.hostname.lower()
    try:
        address = ip_address(hostname)
    except ValueError:
        address = None
    local = hostname in {"localhost", "127.0.0.1", "::1"} or bool(address and (address.is_loopback or address.is_private))
    if parsed.scheme == "http" and not local:
        raise ValueError("public remote endpoints require HTTPS")
    return value.strip().rstrip("/")


def _credential(alias: str) -> str:
    if not alias:
        return ""
    if alias.startswith("env:"):
        return os.getenv(alias.split(":", 1)[1], "")
    if alias.startswith("wincred:") and os.name == "nt":
        return _read_windows_credential(alias.split(":", 1)[1])
    return ""


def _read_windows_credential(target: str) -> str:
    class CREDENTIALW(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

    pointer = ctypes.POINTER(CREDENTIALW)()
    advapi = ctypes.WinDLL("Advapi32.dll")
    if not advapi.CredReadW(target, 1, 0, ctypes.byref(pointer)):
        return ""
    try:
        size = int(pointer.contents.CredentialBlobSize)
        blob = ctypes.string_at(pointer.contents.CredentialBlob, size)
        try:
            return blob.decode("utf-16-le")
        except UnicodeDecodeError:
            return blob.decode("utf-8")
    finally:
        advapi.CredFree(pointer)


def _endpoint_dict(item: ModelEndpointProfile, *, include_readiness: bool = False) -> dict[str, Any]:
    result = {"id": item.id, "name": item.name, "provider_kind": item.provider_kind, "base_url": item.base_url, "credential_alias": item.credential_alias, "credential_configured": bool(_credential(item.credential_alias)) if item.credential_alias else True, "settings": item.settings or {}, "enabled": item.enabled, "managed": item.managed, "updated_at": item.updated_at.isoformat() if item.updated_at else None}
    if include_readiness:
        result["preflight"] = preflight_endpoint(item.id)
    return result


def list_endpoint_profiles(include_readiness: bool = False) -> list[dict[str, Any]]:
    _seed_defaults()
    with SessionLocal() as db:
        items = list(db.scalars(select(ModelEndpointProfile).order_by(ModelEndpointProfile.name)).all())
        return [_endpoint_dict(item, include_readiness=include_readiness) for item in items if item.provider_kind == "ollama"]


def save_endpoint_profile(payload: EndpointProfilePayload) -> dict[str, Any]:
    if payload.provider_kind != "ollama":
        raise ValueError("Refactor Workflow Studio is locked to the exact local Ollama endpoint")
    profile_id = payload.id or f"endpoint-{uuid.uuid4().hex[:12]}"
    base_url = _normalized_url(payload.base_url)
    if payload.provider_kind == "openrouter" and urlsplit(base_url).hostname not in {"openrouter.ai", "www.openrouter.ai"}:
        raise ValueError("OpenRouter profiles must use openrouter.ai")
    if payload.credential_alias and not payload.credential_alias.startswith(("env:", "wincred:")):
        raise ValueError("credential alias must use env: or wincred: and must not contain a secret")
    if payload.provider_kind == "openrouter":
        model = str(payload.settings.get("model") or "").strip()
        if len(model) > 300:
            raise ValueError("OpenRouter model ID is too long")
        if payload.settings.get("fallback_policy", "explicit_only") != "explicit_only":
            raise ValueError("OpenRouter fallback policy must remain explicit_only")
        if payload.enabled and not model:
            raise ValueError("an exact OpenRouter model ID is required before enabling the profile")
        if payload.enabled and not payload.credential_alias:
            raise ValueError("an OpenRouter credential alias is required before enabling the profile")
    settings = dict(payload.settings)
    selected_model = str(settings.get("model") or DEFAULT_OLLAMA_MODEL).strip()
    if selected_model != DEFAULT_OLLAMA_MODEL:
        raise ValueError("only the exact approved local Ollama model is enabled")
    settings["model"] = DEFAULT_OLLAMA_MODEL
    settings["fallback_policy"] = "explicit_only"
    with SessionLocal() as db:
        item = db.get(ModelEndpointProfile, profile_id)
        values = payload.model_dump(exclude={"id"})
        values["base_url"] = base_url
        values["settings"] = settings
        if item is None:
            item = ModelEndpointProfile(id=profile_id, **values)
            db.add(item)
        else:
            for key, value in values.items():
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return _endpoint_dict(item)


def delete_endpoint_profile(profile_id: str) -> None:
    if profile_id in {item["id"] for item in _DEFAULT_ENDPOINTS}:
        raise ValueError("built-in endpoint profiles cannot be deleted")
    with SessionLocal() as db:
        item = db.get(ModelEndpointProfile, profile_id)
        if item is None:
            raise KeyError(profile_id)
        db.delete(item)
        db.commit()


def preflight_endpoint(profile_id: str) -> dict[str, Any]:
    _seed_defaults()
    with SessionLocal() as db:
        item = db.get(ModelEndpointProfile, profile_id)
        if item is None:
            raise KeyError(profile_id)
        profile = _endpoint_dict(item)
    provider = str(profile["provider_kind"])
    selected_model = str((profile.get("settings") or {}).get("model") or DEFAULT_OLLAMA_MODEL).strip()
    baseline = {"profile_id": profile_id, "provider_kind": provider, "selected_model": selected_model, "fallback_policy": str((profile.get("settings") or {}).get("fallback_policy") or "explicit_only"), "credential_alias": str(profile.get("credential_alias") or ""), "credential_configured": bool(profile.get("credential_configured")), "models": [], "mutation": "none"}
    if provider != "ollama":
        return {**baseline, "ready": False, "reason": "exact_local_ollama_only", "exact_model_available": False}
    if selected_model != DEFAULT_OLLAMA_MODEL:
        return {**baseline, "ready": False, "reason": "exact_model_policy_rejected", "exact_model_available": False}
    if not profile["enabled"]:
        return {**baseline, "ready": False, "reason": "profile_disabled", "exact_model_available": False}
    if provider == "openrouter" and not selected_model:
        return {**baseline, "ready": False, "reason": "exact_model_not_selected", "exact_model_available": False}
    secret = _credential(str(profile["credential_alias"]))
    if profile["credential_alias"] and not secret:
        return {**baseline, "ready": False, "reason": "credential_alias_not_configured", "exact_model_available": False}
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    path = "/api/tags"
    base_url = safe_ollama_base_url() if profile_id == "local-ollama" else str(profile["base_url"])
    try:
        with httpx.Client(timeout=3.0, trust_env=False, follow_redirects=False) as client:
            response = client.get(f"{base_url}{path}", headers=headers)
            response.raise_for_status()
            body = response.json()
        models = [str(item.get("name") or item.get("model")) for item in body.get("models", []) if isinstance(item, dict)]
        exact_model_available = selected_model in models
        return {**baseline, "ready": exact_model_available, "reason": "" if exact_model_available else "exact_model_not_advertised", "models": models, "exact_model_available": exact_model_available}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {**baseline, "ready": False, "reason": f"{type(exc).__name__}: endpoint_preflight_failed", "exact_model_available": False}


def generate_with_endpoint(profile_id: str, *, model: str, prompt: str, system_prompt: str = "", settings: dict[str, Any] | None = None) -> str:
    _seed_defaults()
    with SessionLocal() as db:
        item = db.get(ModelEndpointProfile, profile_id)
        if item is None:
            raise KeyError(profile_id)
        profile = _endpoint_dict(item)
    if not profile["enabled"]:
        raise ValueError("endpoint profile is disabled")
    if profile["provider_kind"] != "ollama":
        raise ValueError("only the exact local Ollama endpoint is enabled")
    if model.strip() != DEFAULT_OLLAMA_MODEL:
        raise ValueError("only the exact approved local Ollama model is enabled")
    base_url = safe_ollama_base_url() if profile_id == "local-ollama" else str(profile["base_url"])
    secret = _credential(str(profile["credential_alias"]))
    if profile["credential_alias"] and not secret:
        raise ValueError("endpoint credential alias is not configured")
    options = {**dict(profile.get("settings") or {}), **dict(settings or {})}
    if profile["provider_kind"] == "openrouter":
        selected_model = str((profile.get("settings") or {}).get("model") or "").strip()
        if not selected_model or model.strip() != selected_model:
            raise ValueError("OpenRouter generation requires the exact model ID selected on the endpoint profile")
        if str(options.get("fallback_policy") or "explicit_only") != "explicit_only":
            raise ValueError("OpenRouter fallback policy must remain explicit_only")
    timeout = min(max(float(options.get("timeout_seconds") or 120), 1), 600)
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt[:200_000]})
    messages.append({"role": "user", "content": prompt[:200_000]})
    provider = str(profile["provider_kind"])
    try:
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            if provider in {"ollama", "ollama_cloud", "ollama_compatible"}:
                ollama_options = {key: options[key] for key in ("num_ctx", "temperature", "top_p", "top_k", "min_p", "repeat_penalty", "seed", "stop") if key in options}
                body: dict[str, Any] = {"model": model, "messages": messages, "stream": False, "options": ollama_options, "keep_alive": str(options.get("keep_alive") or "5m")}
                if options.get("output_format") in {"json", "json_schema"}:
                    body["format"] = options.get("json_schema") if options.get("output_format") == "json_schema" and isinstance(options.get("json_schema"), dict) else "json"
                if "enable_thinking" in options:
                    body["think"] = bool(options["enable_thinking"])
                response = client.post(f"{base_url}/api/chat", headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
                return str((payload.get("message") or {}).get("content") or "")[:200_000]
            if provider == "openrouter":
                if options.get("http_referer"):
                    headers["HTTP-Referer"] = str(options["http_referer"])[:500]
                if options.get("x_title"):
                    headers["X-Title"] = str(options["x_title"])[:200]
            body = {"model": model, "messages": messages, "temperature": float(options.get("temperature") or 0.6), "max_tokens": min(max(int(options.get("max_tokens") or 4096), 1), 65536), "stream": False}
            for key in ("top_p", "seed", "stop"):
                if key in options:
                    body[key] = options[key]
            if options.get("output_format") in {"json", "json_schema"}:
                body["response_format"] = {"type": "json_object"}
            response = client.post(f"{profile['base_url']}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices") or []
            return str(((choices[0] if choices else {}).get("message") or {}).get("content") or "")[:200_000]
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"endpoint generation failed ({type(exc).__name__})") from exc


def gpu_inventory() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    command = [executable, "--query-gpu=index,uuid,name,memory.total,memory.free,compute_cap", "--format=csv,noheader,nounits"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode:
        return []
    devices = []
    for line in completed.stdout.splitlines()[:16]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            continue
        try:
            devices.append({"index": int(parts[0]), "uuid": parts[1], "name": parts[2], "memory_total_mb": int(parts[3]), "memory_free_mb": int(parts[4]), "compute_capability": parts[5]})
        except ValueError:
            continue
    return devices


def gpu_process_inventory() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    command = [executable, "--query-compute-apps=pid,gpu_uuid,process_name,used_memory", "--format=csv,noheader,nounits"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5, shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode:
        return []
    processes: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines()[:128]:
        parts = [part.strip() for part in line.split(",", 3)]
        if len(parts) != 4:
            continue
        try:
            processes.append({"pid": int(parts[0]), "gpu_uuid": parts[1], "process_name": os.path.basename(parts[2])[:160], "used_memory_mb": int(parts[3])})
        except ValueError:
            continue
    return processes


def _hardware_dict(item: HardwareProfile, inventory: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if inventory is None:
        inventory = {device["uuid"]: device for device in gpu_inventory()}
    missing = [device for device in item.device_ids or [] if device not in inventory]
    return {"id": item.id, "name": item.name, "mode": item.mode, "device_ids": item.device_ids or [], "settings": item.settings or {}, "ready": not missing, "missing_devices": missing, "devices": [inventory[device] for device in item.device_ids or [] if device in inventory], "updated_at": item.updated_at.isoformat() if item.updated_at else None}


def list_hardware_profiles() -> list[dict[str, Any]]:
    _seed_defaults()
    devices = gpu_inventory()
    inventory = {device["uuid"]: device for device in devices}
    with SessionLocal() as db:
        if len(devices) >= 2 and db.get(HardwareProfile, "multi-gpu-all") is None:
            db.add(HardwareProfile(
                id="multi-gpu-all",
                name="All NVIDIA GPUs · runtime split",
                mode="multi_gpu",
                device_ids=[str(device["uuid"]) for device in devices[:2]],
                settings={"vram_reserve_mb": 1024, "max_loaded_models": 1, "split_strategy": "runtime_auto"},
            ))
        for device in devices:
            profile_id = f"gpu-{device['uuid'].lower().replace('gpu-', '')[:24]}"
            if db.get(HardwareProfile, profile_id) is None:
                db.add(HardwareProfile(id=profile_id, name=device["name"], mode="single_gpu", device_ids=[device["uuid"]], settings={"vram_reserve_mb": 1024, "max_loaded_models": 1}))
        db.commit()
        items = list(db.scalars(select(HardwareProfile).order_by(HardwareProfile.name)).all())
        return [_hardware_dict(item, inventory) for item in items]


def save_hardware_profile(payload: HardwareProfilePayload) -> dict[str, Any]:
    profile_id = payload.id or f"hardware-{uuid.uuid4().hex[:12]}"
    devices = gpu_inventory()
    inventory = {item["uuid"]: item for item in devices}
    known = set(inventory)
    if len(set(payload.device_ids)) != len(payload.device_ids):
        raise ValueError("hardware profiles cannot repeat a GPU UUID")
    if payload.mode in {"single_gpu", "multi_gpu"} and (not payload.device_ids or any(item not in known for item in payload.device_ids)):
        raise ValueError("hardware profile references an unavailable GPU UUID")
    if payload.mode == "single_gpu" and len(payload.device_ids) != 1:
        raise ValueError("single-GPU profiles require exactly one GPU UUID")
    if payload.mode == "multi_gpu" and len(payload.device_ids) < 2:
        raise ValueError("multi-GPU profiles require at least two GPU UUIDs")
    with SessionLocal() as db:
        item = db.get(HardwareProfile, profile_id)
        values = payload.model_dump(exclude={"id"})
        if item is None:
            item = HardwareProfile(id=profile_id, **values)
            db.add(item)
        else:
            for key, value in values.items():
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return _hardware_dict(item, inventory)


def managed_ollama_launch_spec(profile_id: str, port: int) -> dict[str, Any]:
    if port < 1024 or port > 65535:
        raise ValueError("managed Ollama port must be between 1024 and 65535")
    _seed_defaults()
    with SessionLocal() as db:
        item = db.get(HardwareProfile, profile_id)
        if item is None:
            raise KeyError(profile_id)
        profile = _hardware_dict(item)
    if not profile["ready"]:
        raise ValueError("hardware profile is not ready")
    environment = {"OLLAMA_HOST": f"127.0.0.1:{port}", "CUDA_DEVICE_ORDER": "PCI_BUS_ID"}
    if profile["mode"] == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = "-1"
        environment["GGML_CUDA_VISIBLE_DEVICES"] = "-1"
    elif profile["mode"] in {"single_gpu", "multi_gpu"}:
        devices = {str(device["uuid"]): device for device in gpu_inventory()}
        try:
            visible_indices = [str(devices[device_id]["index"]) for device_id in profile["device_ids"]]
        except KeyError as exc:
            raise ValueError("hardware profile device inventory changed; refresh before launch") from exc
        environment["CUDA_VISIBLE_DEVICES"] = ",".join(visible_indices)
        environment["GGML_CUDA_VISIBLE_DEVICES"] = ",".join(visible_indices)
    settings = profile["settings"]
    if "flash_attention" in settings:
        environment["OLLAMA_FLASH_ATTENTION"] = "1" if settings["flash_attention"] else "0"
    if settings.get("kv_cache_type") in {"f16", "q8_0", "q4_0"}:
        environment["OLLAMA_KV_CACHE_TYPE"] = str(settings["kv_cache_type"])
    return {
        "profile_id": profile_id,
        "command": ["ollama", "serve"],
        "environment": environment,
        "base_url": f"http://127.0.0.1:{port}",
        "mutation": "approval_required",
        "placement": {
            "mode": profile["mode"],
            "device_ids": profile["device_ids"],
            "split_strategy": settings.get("split_strategy", "runtime_auto"),
            "vram_reserve_mb": settings.get("vram_reserve_mb"),
        },
        "observed_placement": None,
    }
