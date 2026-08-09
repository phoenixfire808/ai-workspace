import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";
import ModelRouteSettings from "../ModelRouteSettings";

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
      <NodeField label="Planning mode">
        <select className="node-input nodrag" value={String(data.planning_mode ?? "implementation")} onChange={(event) => onChange?.({ planning_mode: event.target.value })}>
          <option value="implementation">Implementation plan</option><option value="routing">Routing decision</option><option value="decomposition">Task decomposition</option><option value="review">Review and risks</option>
        </select>
      </NodeField>
      <NodeField label="Tool access">
        <select className="node-input nodrag" value={String(data.tool_access ?? "none")} onChange={(event) => onChange?.({ tool_access: event.target.value })}>
          <option value="none">No tools</option><option value="read_only">Read-only tools</option><option value="approved">Approved governed tools</option>
        </select>
      </NodeField>
      <ModelRouteSettings data={data} />
      <div className="node-note">Uses the saved global Refactor Workflow Studio model unless the workflow supplies an explicit override. Planner output is passed to the next node; raw run logs stay metadata-only.</div>
    </NodeFrame>
  );
}
