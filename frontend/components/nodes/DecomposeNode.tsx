"use client";

import { useEffect, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type AgentListResponse = { agents?: Array<{ id?: string; configured?: boolean }> };

export default function DecomposeNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  const [agents, setAgents] = useState<string[]>([]);
  const target = String(data.worker_target ?? "");
  const mode = String(data.dispatch_mode ?? "plan_only");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/agents`)
      .then((response) => response.ok ? response.json() as Promise<AgentListResponse> : Promise.reject())
      .then((payload) => {
        if (!cancelled) setAgents((payload.agents ?? []).map((item) => String(item.id ?? "")).filter(Boolean));
      })
      .catch(() => { if (!cancelled) setAgents([]); });
    return () => { cancelled = true; };
  }, []);

  return (
    <NodeFrame title="Decompose / Delegate" subtitle="Split work and assign approved workers" accent="node-delegate">
      <NodeField label="Decomposition strategy">
        <select className="node-input nodrag" value={String(data.decompose_strategy ?? "checklist")} onChange={(event) => onChange?.({ decompose_strategy: event.target.value })}>
          <option value="checklist">Checklist / bullets</option>
          <option value="lines">One task per line</option>
          <option value="paragraphs">One task per paragraph</option>
          <option value="sentences">Sentence tasks</option>
          <option value="explicit">Use subtasks field</option>
        </select>
      </NodeField>
      <NodeField label="Dispatch mode">
        <select className="node-input nodrag" value={mode} onChange={(event) => onChange?.({ dispatch_mode: event.target.value })}>
          <option value="plan_only">Plan only — no worker starts</option>
          <option value="single">Send one combined assignment</option>
          <option value="sequential">Dispatch subtasks sequentially</option>
          <option value="parallel">Dispatch subtasks in parallel</option>
        </select>
      </NodeField>
      <NodeField label="Worker target">
        <select className="node-input nodrag" value={target} onChange={(event) => onChange?.({ worker_target: event.target.value })} disabled={mode === "plan_only"}>
          <option value="">Select an approved configured worker…</option>
          {target && !agents.includes(target) && <option value={target} disabled>{target} · unavailable</option>}
          {agents.map((agent) => <option key={agent} value={agent}>{agent}</option>)}
        </select>
      </NodeField>
      <NodeField label="Maximum subtasks">
        <input className="node-input nodrag" type="number" min={1} max={16} value={Number(data.max_subtasks ?? 8)} onChange={(event) => onChange?.({ max_subtasks: Number(event.target.value) })} />
      </NodeField>
      <NodeField label="Custom subtasks (optional JSON array)">
        <textarea className="node-input node-textarea nodrag" rows={3} value={String(data.subtasks ?? "")} placeholder='["Inspect API", "Update UI", "Run smoke"]' onChange={(event) => onChange?.({ subtasks: event.target.value })} />
      </NodeField>
      <div className="node-note">
        {mode === "plan_only"
          ? "Produces a visible bounded subtask plan without starting a worker."
          : agents.length
            ? "Dispatch is approval-gated and limited to backend-registered workers."
            : "No configured workers are available; dispatch remains disabled until one is registered."}
      </div>
    </NodeFrame>
  );
}
