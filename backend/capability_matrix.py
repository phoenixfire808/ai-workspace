from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Iterable, get_args

from .library import capability_audit, library_resources
from .options_registry import option_inventory
from .schema import NodeType


NODE_PASS_EVIDENCE = {
    "start": "test_02_start_split_merge_and_plugin",
    "split": "test_02_start_split_merge_and_plugin",
    "merge": "test_02_start_split_merge_and_plugin",
    "plugin": "test_02_start_split_merge_and_plugin",
    "review": "test_03_human_review_resume",
    "file": "test_04_file_preview_resume_and_delete_context",
    "chat": "test_05_chat_and_step_through",
    "context": "test_03_human_review_resume",
    "delegate": "test_06_delegate_plan_only + test_07_delegate_child_receipt_and_completion",
}
NODE_BLOCKERS = {
    "buzz": "real_microphone_and_local_buzz_inference_not_accepted",
    "tts": "real_local_voice_playback_not_accepted",
    "planner": "real_model_inference_not_accepted",
    "coder": "real_model_inference_not_accepted",
    "agent": "real_product_worker_dispatch_not_accepted",
    "tool": "tool_readiness_varies_by_selected_library_resource",
    "runtime": "runtime_profile_declaration_is_not_live_placement_proof",
    "search": "public_search_action_not_accepted",
    "research": "public_retrieval_and_synthesis_not_accepted",
    "source_context": "source_context_contract_passes_bounded_fixture_only",
}
RESOURCE_PASS_EVIDENCE = {
    "tool:create_workspace_file": "test_08_all_file_actuators_stale_and_replay",
    "tool:write_workspace_text": "test_04_file_preview_resume_and_delete_context",
    "tool:patch_workspace_file": "test_08_all_file_actuators_stale_and_replay",
    "tool:rename_workspace_path": "test_08_all_file_actuators_stale_and_replay",
    "tool:delete_workspace_path": "test_08_all_file_actuators_stale_and_replay",
    "tool:list_hermes_skills": "test_inventory_and_read_receipts",
    "tool:read_hermes_skill": "test_inventory_and_read_receipts",
    "tool:build_research_context": "test_context_packet_drops_non_public_and_non_http_sources",
    "plugin:run_annotation": "test_02_start_split_merge_and_plugin",
    "plugin:context_selector": "test_01_registry_and_profile_contracts",
}
ROUTE_PASS_EVIDENCE = {
    "/api/health": "test_01_registry_and_profile_contracts + live HTTP 200",
    "/api/library/capability-audit": "test_01_registry_and_profile_contracts + live 231/0-invalid",
    "/api/hermes/capability-audit": "test_01_registry_and_profile_contracts + fresh-process acceptance",
    "/api/capabilities/matrix": "test_01_registry_and_profile_contracts",
    "/api/capabilities/export.md": "test_01_registry_and_profile_contracts",
    "/api/options": "test_option_api_is_read_only_and_honest",
    "/api/options/export.md": "test_option_api_is_read_only_and_honest",
    "/api/feedback": "test_01_registry_and_profile_contracts",
    "/api/feedback/{feedback_id}/publish-preview": "test_01_registry_and_profile_contracts",
    "/api/plugins": "test_01_registry_and_profile_contracts",
    "/api/model-endpoints": "test_01_registry_and_profile_contracts",
    "/api/model-endpoints/{profile_id}/preflight": "test_01_registry_and_profile_contracts + explicit provider preflight contract",
    "/api/hardware/gpus": "read-only nvidia-smi inventory 2026-08-07 04:07 CDT",
    "/api/hardware/profiles": "test_01_registry_and_profile_contracts",
    "/api/hardware/profiles/{profile_id}/ollama-launch-preview": "hardware profile launch-preview contract",
    "/api/feedback": "local draft API contract",
    "/api/feedback/{feedback_id}/publish-preview": "approval-gated publisher preview contract",
    "/api/runs": "tests 02-08 + deployed plan-only lifecycle",
    "/api/runs/{run_id}": "tests 02-08 + deployed deletion lifecycle",
    "/api/runs/{run_id}/approvals/{approval_id}": "tests 03-08",
    "/api/runs/{run_id}/input": "test_05_chat_and_step_through",
    "/api/actions/preview": "test_08_all_file_actuators_stale_and_replay",
}


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "BLOCKED") for row in rows)
    return {name: counts.get(name, 0) for name in ("PASS", "BLOCKED", "DISABLED", "FAIL")}


def _node_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node_type in get_args(NodeType):
        if node_type in NODE_PASS_EVIDENCE:
            rows.append({"id": node_type, "status": "PASS", "registration": "registered", "evidence": [NODE_PASS_EVIDENCE[node_type]], "reason": None})
        else:
            rows.append({"id": node_type, "status": "BLOCKED", "registration": "registered", "evidence": ["source_compiled_and_frontend_built"], "reason": NODE_BLOCKERS.get(node_type, "node_behavior_not_individually_accepted")})
    return rows


def _resource_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource in library_resources():
        payload = resource.model_dump()
        resource_id = str(payload["resource_id"])
        if not payload.get("ready"):
            status, reason, evidence = "DISABLED", str(payload.get("disabled_reason") or "resource_not_ready"), []
        elif resource_id in RESOURCE_PASS_EVIDENCE:
            status, reason, evidence = "PASS", None, [RESOURCE_PASS_EVIDENCE[resource_id]]
        else:
            status, reason, evidence = "BLOCKED", "registered_ready_but_not_individually_executed", ["capability_registry_honesty_audit"]
        rows.append({"id": resource_id, "category": payload.get("category"), "status": status, "ready": bool(payload.get("ready")), "requires_approval": bool(payload.get("requires_approval")), "scope": payload.get("scope"), "evidence": evidence, "reason": reason})
    return rows


def _route_rows(routes: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/"):
            continue
        methods = sorted(method for method in (getattr(route, "methods", set()) or set()) if method not in {"HEAD", "OPTIONS"})
        evidence = ROUTE_PASS_EVIDENCE.get(path)
        rows.append({"id": f"{'|'.join(methods)} {path}", "path": path, "methods": methods, "status": "PASS" if evidence else "BLOCKED", "registration": "registered", "evidence": [evidence] if evidence else [], "reason": None if evidence else "route_registered_but_not_individually_accepted"})
    return sorted(rows, key=lambda row: (row["path"], row["id"]))


def _approval_rows(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": row["id"], "scope": row.get("scope"), "status": "PASS" if row["status"] == "PASS" else row["status"], "evidence": row.get("evidence", []), "reason": row.get("reason")}
        for row in resources
        if row.get("requires_approval")
    ]


def _option_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    accepted_tiers = {"synthetic", "live_local", "device", "provider", "external"}
    for item in option_inventory()["definitions"]:
        evidence = [entry["receipt"] for entry in item["evidence"]]
        tiers = {entry["tier"] for entry in item["evidence"]}
        if item["status"] == "disabled":
            status = "DISABLED"
        elif item["status"] == "ready" and tiers & accepted_tiers:
            status = "PASS"
        else:
            status = "BLOCKED"
        reason = None if status == "PASS" else "; ".join(item["prerequisites"]) or f"option_status_{item['status']}"
        rows.append({"id": item["option_id"], "category": item["category"], "status": status, "effect": item["effect"], "default": item["default"], "evidence": evidence, "reason": reason})
    return rows


def build_capability_matrix(routes: Iterable[Any]) -> dict[str, Any]:
    nodes = _node_rows()
    resources = _resource_rows()
    route_rows = _route_rows(routes)
    approvals = _approval_rows(resources)
    options = _option_rows()
    honesty = capability_audit()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "taxonomy": {"PASS": "exercised with recorded evidence", "BLOCKED": "registered or implemented but required acceptance evidence is absent", "DISABLED": "unavailable with an explicit reason", "FAIL": "exercised and failed"},
        "registry_honesty": {"total": honesty.get("total"), "invalid_ready": honesty.get("invalid_ready", [])},
        "summary": {"nodes": _status_counts(nodes), "resources": _status_counts(resources), "routes": _status_counts(route_rows), "approvals": _status_counts(approvals), "options": _status_counts(options)},
        "nodes": nodes,
        "resources": resources,
        "routes": route_rows,
        "approvals": approvals,
        "options": options,
    }


def capability_matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = ["# AI Workspace capability acceptance matrix", "", f"Generated: `{matrix['generated_at']}`", "", "> PASS requires executed evidence. Registration alone is BLOCKED, never PASS.", ""]
    for section in ("nodes", "resources", "routes", "approvals", "options"):
        rows = matrix[section]
        lines.extend([f"## {section.title()}", "", "| Capability | Status | Evidence / exact reason |", "|---|---|---|"])
        for row in rows:
            evidence = "; ".join(row.get("evidence") or []) or str(row.get("reason") or "")
            lines.append(f"| `{row['id']}` | **{row['status']}** | {evidence.replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)
