from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from .database import FeedbackItem

MAX_ISSUE_BODY_CHARS = 24_000
_GITHUB_REPO_PATTERN = re.compile(r"(?:github\.com[/:])([^/\s:]+/[^/\s]+?)(?:\.git)?$")


@dataclass
class FeedbackPublishError(RuntimeError):
    detail: str
    failure_class: str

    def __str__(self) -> str:
        return self.detail


def _repository() -> str:
    configured = os.getenv("GITHUB_REPOSITORY", "").strip()
    if configured and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", configured):
        return configured
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""
    match = _GITHUB_REPO_PATTERN.search(remote)
    return match.group(1) if match else ""


def _token() -> str:
    return (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()


def _publisher_enabled() -> bool:
    return os.getenv("WORKSPACE_FEEDBACK_PUBLISHER", "disabled").strip().lower() == "github"


def _body(item: FeedbackItem) -> str:
    kind_label = "Bug report" if item.kind == "bug" else "Feature suggestion"
    sections = [f"## {kind_label}", item.description.strip()]
    if item.steps.strip():
        sections.extend(["", "## Steps / proposed behavior", item.steps.strip()])
    sections.extend([
        "",
        "## Workspace receipt",
        f"- Local feedback ID: `{item.id}`",
        f"- Source: `{item.context_receipt.get('source', 'local-ui')}`",
        f"- Project ID: `{item.project_id or 'none'}`",
        f"- Run ID: `{item.run_id or 'none'}`",
        "- Sensitive prompts, transcripts, credentials, and file contents are intentionally excluded.",
    ])
    return "\n".join(sections)[:MAX_ISSUE_BODY_CHARS]


def github_publish_preview(item: FeedbackItem) -> dict[str, Any]:
    enabled = _publisher_enabled()
    if not enabled:
        return {
            "status": "blocked",
            "failure_class": "feedback_publisher_disabled",
            "repository": "",
            "title": f"[{item.kind.title()}] {item.title}"[:240],
            "body_chars": len(_body(item)),
            "requires_confirmation": True,
            "mutation": "none",
        }
    repository = _repository()
    token_configured = bool(_token())
    return {
        "status": "ready" if repository and token_configured else "blocked",
        "failure_class": None if repository and token_configured else ("github_repository_missing" if not repository else "github_token_missing"),
        "repository": repository,
        "title": f"[{item.kind.title()}] {item.title}"[:240],
        "body_chars": len(_body(item)),
        "requires_confirmation": True,
        "mutation": "none",
    }


def publish_feedback_to_github(item: FeedbackItem) -> dict[str, Any]:
    if not _publisher_enabled():
        raise FeedbackPublishError("Feedback publisher is disabled", "feedback_publisher_disabled")
    repository = _repository()
    token = _token()
    if not repository:
        raise FeedbackPublishError("GitHub repository is not configured", "github_repository_missing")
    if not token:
        raise FeedbackPublishError("GitHub token is not configured", "github_token_missing")
    title = f"[{item.kind.title()}] {item.title}"[:240]
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.post(
                f"https://api.github.com/repos/{repository}/issues",
                headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"},
                json={"title": title, "body": _body(item)},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise FeedbackPublishError("GitHub issue creation timed out", "github_timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise FeedbackPublishError("GitHub rejected the issue request", "github_request_rejected") from exc
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise FeedbackPublishError("GitHub issue creation failed", "github_request_failed") from exc
    number = payload.get("number")
    url = payload.get("html_url")
    if not isinstance(number, int) or not isinstance(url, str):
        raise FeedbackPublishError("GitHub returned an invalid issue receipt", "github_response_invalid")
    return {"repository": repository, "number": number, "url": url, "title": title, "mutation": "github_issue_created"}


__all__ = ["FeedbackPublishError", "github_publish_preview", "publish_feedback_to_github"]
