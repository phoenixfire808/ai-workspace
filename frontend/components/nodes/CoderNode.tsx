import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import { EXACT_WORKSPACE_MODEL } from "./types";
import type { WorkspaceNode } from "./types";
import ModelRouteSettings from "../ModelRouteSettings";

export default function CoderNode({ data }: NodeProps<WorkspaceNode>) {
  return (
    <NodeFrame title="Coder model" subtitle="Exact local Ollama model only" accent="node-coder">
      <NodeField label="Provider">
        <input className="node-input nodrag" value="Ollama · local-only" readOnly />
      </NodeField>
      <NodeField label="Exact model ID">
        <input className="node-input nodrag" value={EXACT_WORKSPACE_MODEL} readOnly />
      </NodeField>
      <NodeField label="System prompt">
        <textarea
          className="node-input node-textarea nodrag"
          rows={3}
          value={String(data.system_prompt ?? "")}
          onChange={(event) => data.onChange?.({ system_prompt: event.target.value })}
        />
      </NodeField>
      <ModelRouteSettings data={data} />
      <div className="node-note">
        Every planner, coder, chat, and research LLM call is locked to the exact local LFM Q4_K_M model. Alternate providers and model IDs are disabled.
      </div>
    </NodeFrame>
  );
}
