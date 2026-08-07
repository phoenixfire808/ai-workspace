from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from .schema import NodeType

OptionKind = Literal["boolean", "enum", "number", "text", "secret_alias", "ordered_list", "capability_reference", "action"]
OptionStatus = Literal["ready", "blocked", "disabled", "experimental", "deprecated"]
OptionEffect = Literal["read_only", "local_state_write", "file_mutation", "process_mutation", "device_action", "network_retrieval", "cloud_request", "external_publication"]
OptionScope = Literal["global", "user", "project", "workflow", "node", "run", "endpoint", "hardware_profile", "runtime_profile", "one_shot"]
OptionPersistence = Literal["ephemeral", "run", "workflow", "project", "profile", "global"]
EvidenceTier = Literal["registered", "source", "synthetic", "live_local", "device", "provider", "external"]
RestartImpact = Literal["none", "frontend", "backend", "isolated_runtime", "full_app"]
InheritanceMode = Literal["safe", "explicit_only", "none"]


class OptionChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str | int | float | bool
    label: str
    status: OptionStatus = "ready"
    reason: str | None = None


class OptionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: EvidenceTier
    receipt: str


class OptionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    category: str
    subgroup: str
    label: str
    description: str
    scope: list[OptionScope]
    kind: OptionKind
    choices: list[OptionChoice] = Field(default_factory=list)
    default: Any
    status: OptionStatus
    prerequisites: list[str] = Field(default_factory=list)
    effect: OptionEffect
    approval_scope: str | None = None
    persistence: OptionPersistence
    evidence: list[OptionEvidence] = Field(default_factory=list)
    privacy_cost: str
    rollback: str
    requires_restart: RestartImpact = "none"
    conflicts_with: list[str] = Field(default_factory=list)
    inheritance: InheritanceMode = "safe"
    dynamic_source: str | None = None


class ControlSurface(BaseModel):
    model_config = ConfigDict(frozen=True)

    surface_id: str
    label: str
    option_ids: list[str] = Field(default_factory=list)
    exemption_reason: str | None = None


PASS_NODE_EVIDENCE = {
    "start": "test_02_start_split_merge_and_plugin",
    "file": "test_04_file_preview_resume_and_delete_context",
    "review": "test_03_human_review_resume",
    "chat": "test_05_chat_and_step_through",
    "split": "test_02_start_split_merge_and_plugin",
    "merge": "test_02_start_split_merge_and_plugin",
    "context": "test_03_human_review_resume",
    "plugin": "test_02_start_split_merge_and_plugin",
    "delegate": "test_06_delegate_plan_only + test_07_delegate_child_receipt_and_completion",
}
NODE_BLOCKERS = {
    "buzz": "real_microphone_and_local_buzz_inference_not_accepted",
    "tts": "real_local_voice_playback_not_accepted",
    "planner": "real_model_inference_not_accepted",
    "coder": "real_model_inference_not_accepted",
    "task": "task_node_behavior_not_individually_accepted",
    "agent": "real_product_worker_dispatch_not_accepted",
    "tool": "tool_readiness_varies_by_selected_library_resource",
    "runtime": "runtime_profile_declaration_is_not_live_placement_proof",
    "search": "public_search_action_not_accepted",
    "research": "public_retrieval_and_synthesis_not_accepted",
    "source_context": "source_context_live_behavior_not_accepted",
}
NODE_EFFECTS: dict[str, OptionEffect] = {
    "buzz": "device_action",
    "tts": "device_action",
    "planner": "local_state_write",
    "coder": "local_state_write",
    "file": "file_mutation",
    "agent": "process_mutation",
    "tool": "local_state_write",
    "runtime": "process_mutation",
    "search": "network_retrieval",
    "research": "network_retrieval",
}
UNSAFE_EFFECTS = {"file_mutation", "process_mutation", "device_action", "network_retrieval", "cloud_request", "external_publication"}


def _choice(value: str | int | float | bool, label: str, status: OptionStatus = "ready", reason: str | None = None) -> OptionChoice:
    return OptionChoice(value=value, label=label, status=status, reason=reason)


def _evidence(tier: EvidenceTier, receipt: str) -> OptionEvidence:
    return OptionEvidence(tier=tier, receipt=receipt)


def _base_options() -> list[OptionDefinition]:
    return [
        OptionDefinition(option_id="run.approval_policy", category="run", subgroup="approval", label="Approval policy", description="Controls when protected actions pause for human review.", scope=["workflow", "run"], kind="enum", choices=[_choice("preflight", "Review protected actions before run"), _choice("per_action", "Pause before each protected action"), _choice("step_through", "Step through every node")], default="per_action", status="ready", effect="local_state_write", approval_scope=None, persistence="run", evidence=[_evidence("synthetic", "tests 03-08 durable approval acceptance")], privacy_cost="local/private", rollback="reset to per_action", inheritance="safe"),
        OptionDefinition(option_id="run.max_parallel", category="run", subgroup="execution", label="Maximum parallel branches", description="Bounds concurrent graph branch work without authorizing workers.", scope=["workflow", "run"], kind="number", choices=[], default=4, status="ready", prerequisites=["integer from 1 through 8"], effect="local_state_write", persistence="run", evidence=[_evidence("synthetic", "RunPayload validation and branch acceptance")], privacy_cost="local/private", rollback="reset to 4"),
        OptionDefinition(option_id="run.retain_context", category="run", subgroup="retention", label="Retain run context", description="Keeps bounded local run context until explicit deletion.", scope=["workflow", "run"], kind="boolean", choices=[_choice(True, "Keep until explicit delete"), _choice(False, "Ephemeral after completion", "experimental", "automatic cleanup lifecycle not fully accepted")], default=True, status="ready", effect="local_state_write", persistence="run", evidence=[_evidence("synthetic", "durable run deletion acceptance")], privacy_cost="local/private bounded context", rollback="delete retained run or reset true"),
        OptionDefinition(option_id="run.idle_reminder_seconds", category="run", subgroup="timer", label="Idle reminder", description="Local UI countdown only; never unloads a model automatically.", scope=["user"], kind="enum", choices=[_choice(60, "1 minute"), _choice(300, "5 minutes"), _choice(900, "15 minutes"), _choice(1800, "30 minutes")], default=300, status="ready", effect="read_only", persistence="ephemeral", evidence=[_evidence("source", "RunInspector bounded reminder controls")], privacy_cost="local/private", rollback="stop timer or reset to 5 minutes"),
        OptionDefinition(option_id="ui.complexity_mode", category="ui", subgroup="presentation", label="Settings complexity", description="Controls Basic versus Advanced presentation without changing capability authorization.", scope=["user"], kind="enum", choices=[_choice("basic", "Basic"), _choice("advanced", "Advanced")], default="basic", status="experimental", prerequisites=["reusable option UI in Phase 1"], effect="read_only", persistence="global", evidence=[_evidence("registered", "roadmap UI contract")], privacy_cost="local/private", rollback="reset to Basic"),
        OptionDefinition(option_id="model.endpoint_profile", category="model", subgroup="routing", label="Endpoint profile", description="Selects one exact configured endpoint; specialized endpoint APIs remain authoritative.", scope=["project", "workflow", "node", "run"], kind="capability_reference", choices=[], default="local-ollama", status="ready", prerequisites=["selected profile is enabled and passes preflight"], effect="local_state_write", persistence="workflow", evidence=[_evidence("synthetic", "explicit endpoint profile acceptance")], privacy_cost="depends on selected profile; cloud profiles send content", rollback="reset to local Ollama profile", inheritance="explicit_only", dynamic_source="/api/model-endpoints"),
        OptionDefinition(option_id="model.exact_model_id", category="model", subgroup="routing", label="Exact model ID", description="Persistent global model with explicit workflow and node overrides; no implicit substitutions.", scope=["global", "project", "workflow", "node", "run"], kind="capability_reference", choices=[], default="hf.co/mradermacher/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS-GGUF:Q4_K_M", status="ready", prerequisites=["exact model is installed in loopback Ollama"], effect="local_state_write", persistence="global", evidence=[_evidence("synthetic", "workspace model setting API and exact Ollama preflight")], privacy_cost="local model ID only", rollback="select another exact installed Ollama model or restore the prior setting", inheritance="explicit_only", dynamic_source="/api/ollama/models"),
        OptionDefinition(option_id="model.fallback_policy", category="model", subgroup="routing", label="Fallback policy", description="Prevents silent local-to-cloud or model identity changes.", scope=["endpoint", "workflow", "node"], kind="enum", choices=[_choice("explicit_only", "No implicit fallback")], default="explicit_only", status="ready", effect="local_state_write", persistence="profile", evidence=[_evidence("synthetic", "OpenRouter fallback rejection test")], privacy_cost="local policy metadata", rollback="reset to explicit_only", inheritance="explicit_only"),
        OptionDefinition(option_id="hardware.profile", category="hardware", subgroup="placement", label="Hardware profile", description="Selects requested CPU/GPU placement; observed placement remains a separate receipt.", scope=["project", "workflow", "node", "run"], kind="capability_reference", choices=[], default="auto", status="ready", prerequisites=["profile references currently discovered UUIDs"], effect="local_state_write", persistence="workflow", evidence=[_evidence("device", "Phase 26 GPU 0/GPU 1/dual-device acceptance")], privacy_cost="local device metadata", rollback="reset to auto", inheritance="explicit_only", dynamic_source="/api/hardware/profiles"),
        OptionDefinition(option_id="runtime.ownership", category="runtime", subgroup="lifecycle", label="Runtime ownership", description="Distinguishes user-managed listeners from app-owned isolated runtimes.", scope=["runtime_profile"], kind="enum", choices=[_choice("user_managed", "User managed"), _choice("app_managed", "App managed", "blocked", "app-owned lifecycle not accepted"), _choice("hybrid", "Hybrid", "experimental", "ownership reconciliation incomplete")], default="user_managed", status="experimental", prerequisites=["process ownership receipt for app-managed mode"], effect="process_mutation", approval_scope="runtime_process_control", persistence="profile", evidence=[_evidence("source", "managed launch preview only")], privacy_cost="local process metadata", rollback="stop only app-owned process and restore user-managed", inheritance="explicit_only", requires_restart="isolated_runtime"),
        OptionDefinition(option_id="runtime.auto_unload", category="runtime", subgroup="lifecycle", label="Automatic unload", description="Controls model unload policy; automatic mutation remains disabled.", scope=["runtime_profile", "workflow"], kind="enum", choices=[_choice("off", "Off"), _choice("reminder", "Reminder only"), _choice("approved_idle_policy", "Approved idle policy", "blocked", "app-owned unload acceptance absent")], default="reminder", status="experimental", prerequisites=["app-owned runtime for mutating mode"], effect="process_mutation", approval_scope="runtime_process_control", persistence="profile", evidence=[_evidence("source", "local reminder UI")], privacy_cost="local timing metadata", rollback="set Off and cancel timer", inheritance="explicit_only"),
        OptionDefinition(option_id="terminal.execution_ceiling", category="terminal", subgroup="execution", label="Terminal ceiling", description="Limits terminal access to the highest accepted class.", scope=["global"], kind="enum", choices=[_choice("preview", "Preview/classify only"), _choice("read_only", "Read-only execution", "blocked", "execution adapter not accepted"), _choice("governed_tasks", "Governed tasks", "blocked", "execution adapter not accepted"), _choice("managed_processes", "Managed processes", "blocked", "ownership lifecycle not accepted")], default="preview", status="ready", effect="read_only", persistence="global", evidence=[_evidence("synthetic", "terminal preview classification acceptance")], privacy_cost="bounded local metadata", rollback="reset to preview", inheritance="explicit_only"),
        OptionDefinition(option_id="feedback.destination", category="feedback", subgroup="publication", label="Feedback destination", description="Keeps drafts local unless a destination is explicitly enabled and each send is confirmed.", scope=["global", "one_shot"], kind="enum", choices=[_choice("local", "Local draft only"), _choice("github", "GitHub", "blocked", "publisher disabled and per-draft confirmation required"), _choice("linear", "Linear", "blocked", "adapter not implemented")], default="local", status="ready", effect="external_publication", approval_scope="external_publish", persistence="global", evidence=[_evidence("synthetic", "feedback publisher disabled-by-default acceptance")], privacy_cost="local by default; external mode sends bounded draft metadata", rollback="reset local; external publication is not reversible", inheritance="explicit_only"),
        OptionDefinition(option_id="research.public_retrieval", category="research", subgroup="network", label="Public retrieval", description="Controls whether a run may retrieve public network content.", scope=["workflow", "run"], kind="enum", choices=[_choice("disabled", "Disabled"), _choice("per_run", "Approve each run", "blocked", "live public retrieval acceptance absent"), _choice("standing_workflow", "Standing workflow policy", "blocked", "standing network policy not accepted")], default="disabled", status="blocked", prerequisites=["local SearXNG ready", "network approval", "source allowlist and receipts"], effect="network_retrieval", approval_scope="network_retrieval", persistence="workflow", evidence=[_evidence("synthetic", "bounded source-context fixture")], privacy_cost="sends search terms and fetches public pages", rollback="disable retrieval and delete retained context", inheritance="explicit_only"),
        OptionDefinition(option_id="voice.microphone_mode", category="voice", subgroup="capture", label="Microphone mode", description="Real capture remains opt-in and device acceptance is pending.", scope=["workflow", "node", "run"], kind="enum", choices=[_choice("disabled", "Disabled"), _choice("manual_consent", "Manual Record/Stop", "blocked", "real microphone acceptance absent")], default="disabled", status="blocked", prerequisites=["explicit consent", "device acceptance"], effect="device_action", approval_scope="microphone_capture", persistence="workflow", evidence=[_evidence("source", "manual consent UI contract")], privacy_cost="captures local audio when explicitly active", rollback="stop/cancel capture and delete temporary audio", inheritance="explicit_only"),
        OptionDefinition(option_id="voice.tts_mode", category="voice", subgroup="playback", label="TTS playback", description="Local playback requires an explicit Speak action and accepted device path.", scope=["workflow", "node", "run"], kind="enum", choices=[_choice("disabled", "Disabled"), _choice("manual", "Manual Speak/Stop/Replay", "blocked", "real speaker acceptance absent")], default="disabled", status="blocked", prerequisites=["local TTS route", "explicit playback action", "device acceptance"], effect="device_action", approval_scope="audio_playback", persistence="workflow", evidence=[_evidence("source", "manual TTS UI contract")], privacy_cost="local text/audio", rollback="stop playback and clear staged audio", inheritance="explicit_only"),
        OptionDefinition(option_id="workers.dispatch_mode", category="workers", subgroup="delegation", label="Worker dispatch", description="Parent-only remains the default; hidden delegation is prohibited.", scope=["global", "project"], kind="enum", choices=[_choice("parent_only", "Parent only"), _choice("named_workers", "Explicit named workers", "blocked", "Drew has not assigned a worker lane")], default="parent_only", status="ready", prerequisites=["explicit Drew authorization", "branch/worktree ownership packet"], effect="process_mutation", approval_scope="worker_dispatch", persistence="project", evidence=[_evidence("source", "roadmap worker protocol")], privacy_cost="bounded context packet to explicit worker", rollback="stop replenishment and return parent-only", inheritance="explicit_only"),
        OptionDefinition(option_id="workspace.run_retention", category="workspace", subgroup="persistence", label="Run retention", description="Controls local retained-run lifecycle.", scope=["project", "workflow"], kind="enum", choices=[_choice("explicit_delete", "Keep until explicit delete"), _choice("keep_last_n", "Keep last N", "blocked", "retention scheduler not implemented"), _choice("age_based", "Age based", "blocked", "retention scheduler not implemented")], default="explicit_delete", status="ready", effect="local_state_write", persistence="project", evidence=[_evidence("synthetic", "transactional run deletion acceptance")], privacy_cost="local bounded run context", rollback="restore database backup when deletion has occurred", inheritance="safe"),
        OptionDefinition(option_id="upgrade.channel", category="upgrade", subgroup="source", label="Upgrade channel", description="Inventory/preflight only; activation remains unavailable.", scope=["global"], kind="enum", choices=[_choice("local_artifact", "Local verified artifact"), _choice("stable", "Stable remote", "blocked", "download/stage adapter not accepted"), _choice("candidate", "Candidate", "blocked", "download/stage adapter not accepted")], default="local_artifact", status="experimental", prerequisites=["verified backup", "staging manifest", "rollback smoke"], effect="file_mutation", approval_scope="upgrade_activation", persistence="global", evidence=[_evidence("source", "Upgrade Center inventory/preflight")], privacy_cost="local by default; remote channels use network", rollback="restore verified snapshot", inheritance="explicit_only", requires_restart="full_app"),
    ]


def _node_options() -> list[OptionDefinition]:
    definitions: list[OptionDefinition] = []
    for node_type in get_args(NodeType):
        accepted = node_type in PASS_NODE_EVIDENCE
        effect = NODE_EFFECTS.get(node_type, "local_state_write")
        unsafe = effect in UNSAFE_EFFECTS
        definitions.append(OptionDefinition(
            option_id=f"node.{node_type}.execution_mode",
            category="nodes",
            subgroup=node_type,
            label=f"{node_type.replace('_', ' ').title()} execution",
            description="Phase 0 contract for this node's selectable execution state; node-specific controls arrive in Phase 2.",
            scope=["node"],
            kind="enum",
            choices=[_choice("disabled", "Disabled"), _choice("configured", "Configured", "ready" if accepted else "blocked", None if accepted else NODE_BLOCKERS.get(node_type, "node behavior not accepted"))],
            default="configured" if accepted else "disabled",
            status="ready" if accepted else "blocked",
            prerequisites=[] if accepted else [NODE_BLOCKERS.get(node_type, "node_behavior_not_individually_accepted")],
            effect=effect,
            approval_scope=f"node_{node_type}_effect" if unsafe else None,
            persistence="workflow",
            evidence=[_evidence("synthetic", PASS_NODE_EVIDENCE[node_type])] if accepted else [_evidence("source", "registered node and editor contract")],
            privacy_cost="local metadata; selected node may process bounded workflow content",
            rollback="set node execution mode to disabled",
            inheritance="explicit_only" if unsafe else "safe",
        ))
    return definitions


OPTIONS: tuple[OptionDefinition, ...] = tuple(_base_options() + _node_options())

CONTROL_SURFACES: tuple[ControlSurface, ...] = tuple([
    ControlSurface(surface_id="run.approval_policy", label="Run approval policy", option_ids=["run.approval_policy"]),
    ControlSurface(surface_id="run.workflow_input", label="Workflow input", exemption_reason="bounded user content, not a reusable option"),
    ControlSurface(surface_id="run.execute", label="Execute Flow", exemption_reason="governed action, not a persisted option"),
    ControlSurface(surface_id="run.idle_timer", label="Idle reminder controls", option_ids=["run.idle_reminder_seconds", "runtime.auto_unload"]),
    ControlSurface(surface_id="control.runtime_profile", label="Runtime profile", option_ids=["runtime.ownership"]),
    ControlSurface(surface_id="control.model_endpoint", label="Model endpoint", option_ids=["model.endpoint_profile", "model.exact_model_id", "model.fallback_policy"]),
    ControlSurface(surface_id="control.hardware_profile", label="GPU evidence and profile", option_ids=["hardware.profile"]),
    ControlSurface(surface_id="control.terminal_preview", label="Terminal preview", option_ids=["terminal.execution_ceiling"]),
    ControlSurface(surface_id="control.upgrade_center", label="Upgrade Center", option_ids=["upgrade.channel"]),
    ControlSurface(surface_id="feedback.local_intake", label="Feedback draft and publisher preview", option_ids=["feedback.destination"]),
    ControlSurface(surface_id="coder.provider", label="Coder provider", option_ids=["model.endpoint_profile"]),
    ControlSurface(surface_id="coder.model", label="Coder exact model", option_ids=["model.exact_model_id"]),
    ControlSurface(surface_id="coder.system_prompt", label="Coder system prompt", exemption_reason="workflow content, not a shared settings option"),
] + [ControlSurface(surface_id=f"node.{node_type}.editor", label=f"{node_type} node editor", option_ids=[f"node.{node_type}.execution_mode"]) for node_type in get_args(NodeType)])


def validate_registry(definitions: tuple[OptionDefinition, ...] = OPTIONS, surfaces: tuple[ControlSurface, ...] = CONTROL_SURFACES) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    ids = [item.option_id for item in definitions]
    known = set(ids)
    for option_id, count in Counter(ids).items():
        if count > 1:
            errors.append({"option_id": option_id, "failure_class": "duplicate_option_id"})
    for item in definitions:
        choice_values = [choice.value for choice in item.choices]
        if item.kind in {"enum", "boolean"} and item.default not in choice_values:
            errors.append({"option_id": item.option_id, "failure_class": "invalid_default"})
        if not item.effect:
            errors.append({"option_id": item.option_id, "failure_class": "missing_effect"})
        if item.status == "ready" and not item.evidence:
            errors.append({"option_id": item.option_id, "failure_class": "ready_without_evidence"})
        if item.effect in UNSAFE_EFFECTS and item.inheritance != "explicit_only":
            errors.append({"option_id": item.option_id, "failure_class": "unsafe_inheritance"})
        if item.effect in UNSAFE_EFFECTS and "global" in item.scope and item.default not in {"disabled", "off", "local", "parent_only", "preview", "local_artifact", "user_managed", "reminder", "explicit_only"}:
            errors.append({"option_id": item.option_id, "failure_class": "unsafe_global_default"})
        for conflict in item.conflicts_with:
            if conflict not in known:
                errors.append({"option_id": item.option_id, "failure_class": f"unknown_conflict:{conflict}"})
    for surface in surfaces:
        if not surface.option_ids and not surface.exemption_reason:
            errors.append({"option_id": surface.surface_id, "failure_class": "unmapped_control_surface"})
        for option_id in surface.option_ids:
            if option_id not in known:
                errors.append({"option_id": surface.surface_id, "failure_class": f"unknown_option:{option_id}"})
    expected_nodes = set(get_args(NodeType))
    represented_nodes = {item.subgroup for item in definitions if item.category == "nodes"}
    for node_type in sorted(expected_nodes - represented_nodes):
        errors.append({"option_id": f"node.{node_type}", "failure_class": "node_option_missing"})
    return errors


def option_inventory() -> dict[str, Any]:
    definitions = [item.model_dump() for item in OPTIONS]
    surfaces = [item.model_dump() for item in CONTROL_SURFACES]
    invalid = validate_registry()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mutation": "none",
        "phase": 0,
        "definitions": definitions,
        "control_surfaces": surfaces,
        "summary": {
            "total": len(definitions),
            "ready": sum(1 for item in definitions if item["status"] == "ready"),
            "blocked": sum(1 for item in definitions if item["status"] == "blocked"),
            "experimental": sum(1 for item in definitions if item["status"] == "experimental"),
            "node_types": sum(1 for item in definitions if item["category"] == "nodes"),
            "control_surfaces": len(surfaces),
            "invalid": len(invalid),
        },
        "invalid": invalid,
    }


def option_inventory_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# M⊕ option registry",
        "",
        f"Generated: `{inventory['generated_at']}`",
        "",
        "> Phase 0 is a read-only contract inventory. Existing specialized APIs remain authoritative for mutations.",
        "",
        "| Option | Status | Default | Scope | Effect | Evidence / blocker | Rollback |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in inventory["definitions"]:
        evidence = "; ".join(entry["receipt"] for entry in item["evidence"]) or "; ".join(item["prerequisites"])
        lines.append(f"| `{item['option_id']}` | **{item['status']}** | `{item['default']}` | {', '.join(item['scope'])} | `{item['effect']}` | {evidence.replace('|', '/')} | {item['rollback'].replace('|', '/')} |")
    lines.extend(["", "## Control-surface coverage", "", "| Surface | Options / exemption |", "|---|---|"])
    for surface in inventory["control_surfaces"]:
        mapping = ", ".join(f"`{item}`" for item in surface["option_ids"]) or str(surface["exemption_reason"])
        lines.append(f"| `{surface['surface_id']}` | {mapping.replace('|', '/')} |")
    lines.extend(["", f"Invalid registry rows: **{len(inventory['invalid'])}**", ""])
    return "\n".join(lines)
