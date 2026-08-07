import { useEffect, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import { MODEL_OPTIONS } from "./types";
import type { ModelProvider, WorkspaceNode } from "./types";
import ModelRouteSettings from "../ModelRouteSettings";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function CoderNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  const configuredProvider = String(data.provider ?? "");
  const provider: ModelProvider = Object.prototype.hasOwnProperty.call(MODEL_OPTIONS, configuredProvider)
    ? (configuredProvider as ModelProvider)
    : "ollama";
  const model = String(data.model ?? MODEL_OPTIONS[provider].model);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [globalModel, setGlobalModel] = useState("");

  useEffect(() => {
    if (provider !== "ollama") {
      setOllamaModels([]);
      return;
    }
    let cancelled = false;
    Promise.all([
      fetch(`${API_URL}/api/ollama/models`).then((response) => response.json()),
      fetch(`${API_URL}/api/settings/model`).then((response) => response.json()),
    ])
      .then(([payload, setting]: [{ models?: Array<{ name?: string }> }, { model?: string }]) => {
        if (!cancelled) {
          setOllamaModels((payload.models ?? []).map((item) => String(item.name ?? "")).filter(Boolean));
          setGlobalModel(String(setting.model ?? ""));
        }
      })
      .catch(() => {
        if (!cancelled) setOllamaModels([]);
      });
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const selectedOllamaModel = model;
  return (
    <NodeFrame title="Coder model" subtitle="Local or explicitly configured provider" accent="node-coder">
      <NodeField label="Provider">
        <select
          className="node-input nodrag"
          value={provider}
          onChange={(event) => {
            const nextProvider = event.target.value as ModelProvider;
            onChange?.({
              provider: nextProvider,
              model: MODEL_OPTIONS[nextProvider].model,
              endpoint_profile: nextProvider === "openrouter" ? "openrouter" : "",
              fallback_policy: "explicit_only",
            });
          }}
        >
          {(Object.entries(MODEL_OPTIONS) as [ModelProvider, { label: string; model: string }][]).map(
            ([value, option]) => <option key={value} value={value}>{option.label}</option>,
          )}
        </select>
      </NodeField>
      <NodeField label="Model">
        {provider === "ollama" && ollamaModels.length > 0 ? (
          <select
            className="node-input nodrag"
            value={selectedOllamaModel}
            onChange={(event) => onChange?.({ model: event.target.value })}
          >
            <option value="">Global default · {globalModel || "not configured"}</option>
            {model && !ollamaModels.includes(model) && <option value={model}>{model} (not installed)</option>}
            {ollamaModels.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        ) : (
          <input
            className="node-input nodrag"
            value={model}
            placeholder={provider === "ollama" ? "Waiting for local Ollama inventory…" : undefined}
            onChange={(event) => onChange?.({ model: event.target.value })}
          />
        )}
      </NodeField>

      <NodeField label="System prompt">
        <textarea
          className="node-input node-textarea nodrag"
          rows={3}
          value={String(data.system_prompt ?? "")}
          onChange={(event) => onChange?.({ system_prompt: event.target.value })}
        />
      </NodeField>
      <ModelRouteSettings data={data} />
      <div className="node-note">
        {provider === "ollama"
            ? "Uses the saved global model unless an exact node override is selected."
          : provider === "openrouter"
            ? "Explicit OpenRouter route; configure the local credential alias before enabling it."
            : "API keys stay outside the canvas and are never serialized."}
      </div>
    </NodeFrame>
  );
}
