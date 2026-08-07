from __future__ import annotations

import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .runtime_control import active_baseline_profile_id, preflight_runtime_profile
from .model_settings import get_workspace_model_setting


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _present_item(item_id: str, label: str, path: Path, kind: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "label": label,
        "kind": kind,
        "state": "present" if path.exists() else "missing",
        "path": path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else str(path),
    }


def upgrade_inventory() -> dict[str, Any]:
    items = [
        _present_item("workspace", "M⊕ workspace", PROJECT_ROOT, "application"),
        _present_item("backend-requirements", "Backend dependency manifest", PROJECT_ROOT / "backend" / "requirements.txt", "dependency-manifest"),
        _present_item("frontend-package", "Frontend dependency manifest", PROJECT_ROOT / "frontend" / "package.json", "dependency-manifest"),

    ]
    return {
        "mutation": "none",
        "items": items,
        "workspace_model": get_workspace_model_setting(),
        "upgrade_policy": {
            "downloads": "explicit-action-required",
            "builds": "explicit-action-required",
            "service_changes": "explicit-action-required",
            "rollback": "backup-and-explicit-action-required",
        },
    }


def _manifest_status(path: Path, *, json_manifest: bool = False) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "ok": False, "detail": "missing"}
    try:
        text = path.read_text(encoding="utf-8")
        if json_manifest:
            json.loads(text)
        elif not text.strip():
            raise ValueError("manifest is empty")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"path": str(path), "ok": False, "detail": "unreadable-or-invalid"}
    return {"path": str(path), "ok": True, "detail": "valid-json" if json_manifest else "valid-text"}


def upgrade_preflight() -> dict[str, Any]:
    usage = shutil.disk_usage(PROJECT_ROOT)
    baseline = preflight_runtime_profile(active_baseline_profile_id())
    checks = [
        {"name": "workspace", "ok": PROJECT_ROOT.is_dir(), "detail": str(PROJECT_ROOT)},
        {"name": "backend-manifest", **_manifest_status(PROJECT_ROOT / "backend" / "requirements.txt")},
        {"name": "frontend-manifest", **_manifest_status(PROJECT_ROOT / "frontend" / "package.json", json_manifest=True)},
        {"name": "baseline-runtime", "ok": baseline.get("status") == "ready", "detail": baseline.get("status")},
    ]
    return {
        "mutation": "none",
        "status": "ready" if all(check.get("ok") for check in checks) else "blocked",
        "checks": checks,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(aliased=True),
            "free_bytes": usage.free,
        },
        "baseline": baseline,
        "rollback": {
            "available": False,
            "reason": "No upgrade mutation has been requested; create a verified backup before any future activation.",
        },
    }


__all__ = ["upgrade_inventory", "upgrade_preflight"]
