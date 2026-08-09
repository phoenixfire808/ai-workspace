from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .model_profiles import managed_ollama_launch_spec


class ManagedRuntimeError(RuntimeError):
    def __init__(self, detail: str, failure_class: str) -> None:
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


@dataclass
class ManagedInstance:
    profile_id: str
    host: str
    port: int
    pid: int
    process: subprocess.Popen[bytes]
    started_at: float


_instances: dict[str, ManagedInstance] = {}
_lock = threading.RLock()


def _base_url(host: str, port: int) -> str:
    safe_host = "127.0.0.1" if host in {"localhost", "0.0.0.0", "::"} else host
    return f"http://{safe_host}:{port}"


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def _ready(base_url: str) -> bool:
    try:
        with httpx.Client(timeout=1.0, trust_env=False) as client:
            return client.get(f"{base_url}/api/tags").status_code == 200
    except httpx.HTTPError:
        return False


def start_managed_instance(profile_id: str, *, port: int, host: str = "127.0.0.1") -> dict[str, Any]:
    if not (1024 <= int(port) <= 65535):
        raise ManagedRuntimeError("managed Ollama port is invalid", "runtime_port_invalid")
    if host not in {"127.0.0.1", "localhost"}:
        raise ManagedRuntimeError("managed Ollama must bind to loopback", "runtime_host_invalid")
    executable = shutil.which("ollama")
    if not executable:
        raise ManagedRuntimeError("Ollama executable is unavailable", "ollama_unavailable")
    with _lock:
        existing = _instances.get(profile_id)
        if existing and existing.process.poll() is None:
            return instance_status(profile_id)
        if not _port_free("127.0.0.1", port):
            raise ManagedRuntimeError("managed Ollama port is already occupied", "runtime_port_busy")
        spec = managed_ollama_launch_spec(profile_id, port)
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in dict(spec.get("environment") or {}).items()})
        env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
        process = subprocess.Popen(
            [executable, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        item = ManagedInstance(profile_id=profile_id, host="127.0.0.1", port=port, pid=int(process.pid), process=process, started_at=time.time())
        _instances[profile_id] = item
    deadline = time.monotonic() + 8.0
    base_url = _base_url(item.host, item.port)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            with _lock:
                _instances.pop(profile_id, None)
            raise ManagedRuntimeError("managed Ollama exited during startup", "runtime_start_failed")
        if _ready(base_url):
            return instance_status(profile_id)
        time.sleep(0.15)
    stop_managed_instance(profile_id)
    raise ManagedRuntimeError("managed Ollama did not become ready", "runtime_start_timeout")


def stop_managed_instance(profile_id: str) -> dict[str, Any]:
    with _lock:
        item = _instances.get(profile_id)
        if item is None:
            return {"profile_id": profile_id, "status": "stopped", "owned": False}
        process = item.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        _instances.pop(profile_id, None)
    return {"profile_id": profile_id, "status": "stopped", "owned": True, "pid": item.pid}


def load_model(profile_id: str, model: str, *, keep_alive: str = "5m") -> dict[str, Any]:
    with _lock:
        item = _instances.get(profile_id)
    if item is None or item.process.poll() is not None:
        raise ManagedRuntimeError("managed runtime is not running", "runtime_not_running")
    if not str(model or "").strip():
        raise ManagedRuntimeError("exact model ID is required", "model_id_missing")
    try:
        with httpx.Client(timeout=300, trust_env=False) as client:
            response = client.post(f"{_base_url(item.host, item.port)}/api/generate", json={"model": model, "prompt": "", "stream": False, "keep_alive": keep_alive})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ManagedRuntimeError("model preload failed", "model_load_failed") from exc
    return instance_status(profile_id)


def unload_model(profile_id: str, model: str) -> dict[str, Any]:
    with _lock:
        item = _instances.get(profile_id)
    if item is None or item.process.poll() is not None:
        raise ManagedRuntimeError("managed runtime is not running", "runtime_not_running")
    try:
        with httpx.Client(timeout=60, trust_env=False) as client:
            response = client.post(f"{_base_url(item.host, item.port)}/api/generate", json={"model": model, "prompt": "", "stream": False, "keep_alive": 0})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ManagedRuntimeError("model unload failed", "model_unload_failed") from exc
    return instance_status(profile_id)


def instance_status(profile_id: str) -> dict[str, Any]:
    with _lock:
        item = _instances.get(profile_id)
    if item is None:
        return {"profile_id": profile_id, "status": "stopped", "owned": False, "models": []}
    if item.process.poll() is not None:
        with _lock:
            _instances.pop(profile_id, None)
        return {"profile_id": profile_id, "status": "stopped", "owned": True, "pid": item.pid, "models": []}
    models: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.get(f"{_base_url(item.host, item.port)}/api/ps")
            response.raise_for_status()
            models = list(response.json().get("models") or [])
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    bounded_models = [{key: model.get(key) for key in ("name", "model", "size", "size_vram", "expires_at") if key in model} for model in models[:32] if isinstance(model, dict)]
    return {"profile_id": profile_id, "status": "ready" if _ready(_base_url(item.host, item.port)) else "starting", "owned": True, "pid": item.pid, "host": item.host, "port": item.port, "started_at": item.started_at, "models": bounded_models}


def list_instances() -> list[dict[str, Any]]:
    with _lock:
        profile_ids = list(_instances)
    return [instance_status(profile_id) for profile_id in profile_ids]
