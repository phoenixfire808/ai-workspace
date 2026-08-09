"""Structured, redacted observability for Refactor Workflow Studio.

All events stay on the local process stdout/stderr so Docker logs, Uvicorn,
and a future file sink can consume the same records. Payloads intentionally
contain identifiers, counts, statuses, and bounded error text only; prompts,
secrets, file contents, and arbitrary script bodies are never logged here.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

LOGGER = logging.getLogger("refactor_workflow_studio")
LOGGER.setLevel(str(os.getenv("RWS_LOG_LEVEL", "INFO")).upper())
if not LOGGER.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(_handler)
    LOGGER.propagate = False


def log_event(event: str, **fields: Any) -> None:
    """Emit one compact JSON event without logging sensitive payloads."""
    safe: dict[str, Any] = {"event": event}
    for key, value in fields.items():
        if key in {"prompt", "message", "content", "script", "script_content", "old_text", "new_text", "arguments"}:
            continue
        if isinstance(value, str):
            safe[key] = value[:500]
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, (list, tuple, set)):
            safe[key] = [str(item)[:120] for item in list(value)[:32]]
        else:
            safe[key] = str(value)[:500]
    LOGGER.info("%s", json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str))


def log_exception(event: str, exc: BaseException, **fields: Any) -> None:
    log_event(event, error_type=type(exc).__name__, error=str(exc)[:500], **fields)
