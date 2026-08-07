import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function AgentNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  return (
    <NodeFrame title="Agent reaction" subtitle="Allowlisted local launch" accent="node-agent">
      <NodeField label="Configured target">
        <input
          className="node-input nodrag"
          value={String(data.target ?? "")}
          placeholder="hermes or codex"
          onChange={(event) => onChange?.({ target: event.target.value })}
        />
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
      <div className="node-note">Only targets registered in `WORKSPACE_AGENT_COMMANDS` can start.</div>
    </NodeFrame>
  );
}
