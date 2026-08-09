import { useEffect, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function AgentNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  const [agents, setAgents] = useState<string[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/agents`).then((response) => response.json()).then((payload: { agents?: Array<{ id?: string }> }) => {
      if (!cancelled) setAgents((payload.agents ?? []).map((item) => String(item.id ?? "")).filter(Boolean));
    }).catch(() => { if (!cancelled) setAgents([]); });
    return () => { cancelled = true; };
  }, []);
  return (
    <NodeFrame title="Agent reaction" subtitle="Allowlisted local launch" accent="node-agent">
      <NodeField label="Configured target">
        <select
          className="node-input nodrag"
          value={String(data.target ?? "")}
          onChange={(event) => onChange?.({ target: event.target.value })}
        >
          <option value="">Select a configured agent…</option>
          {String(data.target ?? "") && !agents.includes(String(data.target)) && <option value={String(data.target)} disabled>{String(data.target)} · unavailable</option>}
          {agents.map((agent) => <option key={agent} value={agent}>{agent}</option>)}
        </select>
      </NodeField>
      <NodeField label="Prompt prefix">
        <textarea
          className="node-input node-textarea nodrag"
          rows={2}
          value={String(data.prompt_prefix ?? "")}
          placeholder="Optional instruction before workflow output"
          onChange={(event) => onChange?.({ prompt_prefix: event.target.value })}
        />
      </NodeField>
      <div className="node-note">{agents.length ? "Only dropdown targets registered by the backend can start." : "No allowlisted agents are configured yet."}</div>
    </NodeFrame>
  );
}
