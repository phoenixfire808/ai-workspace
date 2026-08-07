import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function PlannerNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  return (
    <NodeFrame title="Planner" subtitle="Intent → structured implementation plan" accent="node-planner">
      <NodeField label="Planner instructions">
        <textarea
          className="node-input node-textarea nodrag"
          rows={4}
          value={String(data.system_prompt ?? "")}
          onChange={(event) => onChange?.({ system_prompt: event.target.value })}
        />
      </NodeField>
      <NodeField label="Max plan tokens">
        <input
          className="node-input nodrag"
          type="number"
          min={512}
          max={4096}
          step={256}
          value={Number(data.max_tokens ?? 4096)}
          onChange={(event) => onChange?.({ max_tokens: Number(event.target.value) })}
        />
      </NodeField>
      <div className="node-note">Uses the explicit local Nanbeige route. Planner output is passed to the next node; raw run logs stay metadata-only.</div>
    </NodeFrame>
  );
}
