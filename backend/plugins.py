from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


MAX_PLUGIN_TEXT = 200_000


class PluginError(RuntimeError):
    def __init__(self, detail: str, failure_class: str = "plugin_failed") -> None:
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    label: str
    description: str
    handler: Callable[[str, dict[str, Any]], dict[str, Any]]
    requires_approval: bool = False


def _run_annotation(value: str, config: dict[str, Any]) -> dict[str, Any]:
    note = str(config.get("note") or "").strip()[:4_000]
    return {"output": value[:MAX_PLUGIN_TEXT], "events": [{"event_type": "run_annotation", "payload": {"note": note}}] if note else []}


def _select_path(value: str, config: dict[str, Any]) -> dict[str, Any]:
    import json

    selector = str(config.get("selector") or "").strip()
    if not selector:
        return {"output": value[:MAX_PLUGIN_TEXT], "events": []}
    try:
        current: Any = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PluginError("context selector requires JSON input", "plugin_context_not_json") from exc
    for part in selector.split("."):
        if not part:
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise PluginError("context selector did not match the input", "plugin_selector_missing")
    output = json.dumps(current, ensure_ascii=False) if not isinstance(current, str) else current
    return {"output": output[:MAX_PLUGIN_TEXT], "events": []}


PLUGINS: dict[str, PluginManifest] = {
    "run_annotation": PluginManifest("run_annotation", "Run annotation", "Append a human-visible note to the durable run.", _run_annotation),
    "context_selector": PluginManifest("context_selector", "Context selector", "Select a named field from upstream JSON context.", _select_path),
}


def plugin_catalog() -> list[dict[str, Any]]:
    return [{"plugin_id": item.plugin_id, "label": item.label, "description": item.description, "requires_approval": item.requires_approval, "ready": True, "disabled_reason": ""} for item in PLUGINS.values()]


def execute_plugin(plugin_id: str, value: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = PLUGINS.get(str(plugin_id or ""))
    if manifest is None:
        raise PluginError("plugin is not registered", "plugin_unregistered")
    return manifest.handler(str(value or ""), dict(config or {}))
