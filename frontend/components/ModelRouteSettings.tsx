"use client";

import { useEffect, useState } from "react";
import { NodeField } from "./nodes/NodeFrame";
import { EXACT_WORKSPACE_MODEL } from "./nodes/types";
import type { WorkspaceNodeData } from "./nodes/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type Hardware = { id: string; name: string; mode: string; ready: boolean; missing_devices?: string[] };

export default function ModelRouteSettings({ data }: { data: WorkspaceNodeData }) {
  const [hardware, setHardware] = useState<Hardware[]>([]);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    void fetch(`${API_URL}/api/hardware/profiles`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload: { profiles?: Hardware[] }) => setHardware(payload.profiles ?? []))
      .catch(() => undefined);
  }, []);
  const change = (patch: Record<string, unknown>) => data.onChange?.(patch);
  return <details className="node-advanced nodrag" open={open} onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}>
    <summary>Local execution settings</summary>
    <NodeField label="Endpoint profile"><input className="node-input nodrag" value="local-ollama · exact-only" readOnly /></NodeField>
    <NodeField label="Exact model ID"><input className="node-input nodrag" value={EXACT_WORKSPACE_MODEL} readOnly /></NodeField>
    <NodeField label="Hardware profile"><select className="node-input nodrag" value={String(data.hardware_profile ?? "auto")} onChange={(event) => change({ hardware_profile: event.target.value })}>{hardware.map((item) => <option key={item.id} value={item.id} disabled={!item.ready}>{item.name} · {item.mode}{!item.ready ? " · unavailable" : ""}</option>)}</select></NodeField>
    <NodeField label="Fallback policy"><input className="node-input nodrag" value="explicit_only · no alternate model" readOnly /></NodeField>
    <NodeField label="Route strategy"><select className="node-input nodrag" value={String(data.route_strategy ?? "local_only")} onChange={(event) => change({ route_strategy: event.target.value })}><option value="local_only">Exact local only</option><option value="user_ordered">User ordered · exact model only</option></select></NodeField>
    <NodeField label="Approval policy"><select className="node-input nodrag" value={String(data.approval_policy ?? "inherit")} onChange={(event) => change({ approval_policy: event.target.value })}><option value="inherit">Inherit workflow</option><option value="preflight">Preflight</option><option value="per_action">Per action</option><option value="step_through">Step through</option></select></NodeField>
    <NodeField label="Context length"><input className="node-input nodrag" type="number" min={512} max={262144} step={512} value={Number(data.num_ctx ?? 4096)} onChange={(event) => change({ num_ctx: Number(event.target.value) })} /></NodeField>
    <NodeField label="Output tokens"><input className="node-input nodrag" type="number" min={1} max={65536} value={Number(data.max_tokens ?? 4096)} onChange={(event) => change({ max_tokens: Number(event.target.value) })} /></NodeField>
    <NodeField label="Temperature"><input className="node-input nodrag" type="number" min={0} max={2} step={0.05} value={Number(data.temperature ?? 0.6)} onChange={(event) => change({ temperature: Number(event.target.value) })} /></NodeField>
    <NodeField label="Top P"><input className="node-input nodrag" type="number" min={0} max={1} step={0.05} value={Number(data.top_p ?? 0.9)} onChange={(event) => change({ top_p: Number(event.target.value) })} /></NodeField>
    <NodeField label="Top K"><input className="node-input nodrag" type="number" min={0} max={200} value={Number(data.top_k ?? 40)} onChange={(event) => change({ top_k: Number(event.target.value) })} /></NodeField>
    <NodeField label="Seed"><input className="node-input nodrag" type="number" value={Number(data.seed ?? -1)} onChange={(event) => change({ seed: Number(event.target.value) })} /></NodeField>
    <NodeField label="Keep alive"><input className="node-input nodrag" value={String(data.keep_alive ?? "5m")} onChange={(event) => change({ keep_alive: event.target.value })} /></NodeField>
    <NodeField label="Output format"><select className="node-input nodrag" value={String(data.output_format ?? "text")} onChange={(event) => change({ output_format: event.target.value })}><option value="text">Text</option><option value="markdown">Markdown</option><option value="json">JSON</option><option value="json_schema">JSON schema</option></select></NodeField>
    <small>All LLM-backed workflow nodes use the exact local LFM Q4_K_M model. Cloud, MiniMax, Nanbeige, and alternate Ollama model routes are disabled.</small>
  </details>;
}
