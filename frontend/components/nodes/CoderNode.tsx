import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import { MODEL_OPTIONS } from "./types";
import type { ModelProvider, WorkspaceNode } from "./types";

export default function CoderNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  const configuredProvider = String(data.provider ?? "");
  const provider: ModelProvider = Object.prototype.hasOwnProperty.call(MODEL_OPTIONS, configuredProvider)
    ? (configuredProvider as ModelProvider)
    : "nanbeige";
  const model = String(data.model ?? MODEL_OPTIONS[provider].model);
  return (
    <NodeFrame title="Coder model" subtitle="Local or explicitly configured provider" accent="node-coder">
      <NodeField label="Provider">
        <select
          className="node-input nodrag"
          value={provider}
          onChange={(event) => {
            const nextProvider = event.target.value as ModelProvider;
            onChange?.({ provider: nextProvider, model: MODEL_OPTIONS[nextProvider].model });
          }}
        >
          {(Object.entries(MODEL_OPTIONS) as [ModelProvider, { label: string; model: string }][]).map(
            ([value, option]) => <option key={value} value={value}>{option.label}</option>,
          )}
        </select>
      </NodeField>
      <NodeField label="Model">
        <input
          className="node-input nodrag"
          value={model}
          readOnly={provider === "nanbeige" || provider === "lfm"}
          onChange={(event) => onChange?.({ model: event.target.value })}
        />
      </NodeField>
      {provider === "nanbeige" && (
        <NodeField label="Reasoning">
          <select
            className="node-input nodrag"
            value={data.enable_thinking === false ? "off" : "on"}
            onChange={(event) => onChange?.({ enable_thinking: event.target.value === "on" })}
          >
            <option value="on">Thinking enabled</option>
            <option value="off">Fast response</option>
          </select>
        </NodeField>
      )}
      <NodeField label="System prompt">
        <textarea
          className="node-input node-textarea nodrag"
          rows={3}
          value={String(data.system_prompt ?? "")}
          onChange={(event) => onChange?.({ system_prompt: event.target.value })}
        />
      </NodeField>
      <div className="node-note">
        {provider === "nanbeige"
          ? "Exact local alias; endpoint stays outside the canvas."
          : provider === "lfm"
            ? "Explicit LFM2.5 agent option; requires its separate local runtime."
          : "API keys stay outside the canvas and are never serialized."}
      </div>
    </NodeFrame>
  );
}
