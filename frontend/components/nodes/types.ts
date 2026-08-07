import type { Node } from "@xyflow/react";

export type NodeKind = "start" | "buzz" | "planner" | "coder" | "file" | "task" | "agent";
export type ModelProvider = "nanbeige" | "lfm" | "minimax" | "ollama";

export interface WorkspaceNodeData extends Record<string, unknown> {
  label: string;
  description?: string;
  provider?: ModelProvider;
  model?: string;
  onChange?: (patch: Record<string, unknown>) => void;
}

export type WorkspaceNode = Node<WorkspaceNodeData, NodeKind>;

export const MODEL_OPTIONS: Record<ModelProvider, { label: string; model: string }> = {
  nanbeige: { label: "Nanbeige4.2-3B · RTX 2070 SUPER", model: "nanbeige4.2-3b-local" },
  lfm: { label: "LFM2.5-2.6B · explicit agent option", model: "LFM2.5-2.6B" },
  minimax: { label: "MiniMax-M3", model: "MiniMax-M3" },
  ollama: {
    label: "Ollama · environment configured",
    model: "",
  },
};

export const NODE_META: Record<NodeKind, { label: string; icon: string; accent: string; hint: string }> = {
  start: { label: "Start", icon: "◉", accent: "node-start", hint: "Workflow input" },
  buzz: { label: "Buzz transcription", icon: "◌", accent: "node-buzz", hint: "Whisper audio" },
  planner: { label: "Planner", icon: "✦", accent: "node-planner", hint: "Intent to plan" },
  coder: { label: "Coder model", icon: "⌘", accent: "node-coder", hint: "Nanbeige / LFM local" },
  file: { label: "File I/O", icon: "▣", accent: "node-file", hint: "Workspace files" },
  task: { label: "Task tracker", icon: "☷", accent: "node-task", hint: "SQLite task" },
  agent: { label: "Agent reaction", icon: "↗", accent: "node-agent", hint: "Allowlisted launch" },
};

export function persistedData(data: WorkspaceNodeData): Record<string, unknown> {
  const { onChange: _onChange, ...serializable } = data;
  return serializable;
}

export function nodeDefaults(kind: NodeKind): WorkspaceNodeData {
  switch (kind) {
    case "start":
      return { label: "Start", description: "Accepts the run input." };
    case "buzz":
      return { label: "Buzz transcription", description: "Transcribe a local audio file.", file_path: "", model_size: "small" };
    case "planner":
      return {
        label: "Planner",
        description: "Turn conversational intent into a structured implementation plan.",
        system_prompt: "You are the local workflow planner. Return goal, assumptions, ordered steps, risks, and verification.",
        max_tokens: 4096,
      };
    case "coder":
      return {
        label: "Coder model",
        description: "Generate a result with the selected provider.",
        provider: "nanbeige",
        model: "nanbeige4.2-3b-local",
        system_prompt: "You are a precise local coding assistant. Return the most useful direct result for the workflow.",
        temperature: 0.6,
        enable_thinking: true,
        max_tokens: 4096,
      };
    case "file":
      return { label: "File I/O", description: "Read or write inside the workspace root.", mode: "read", path: "" };
    case "task":
      return { label: "Task tracker", description: "Persist a task in SQLite.", title: "", status: "todo", notes: "" };
    case "agent":
      return { label: "Agent reaction", description: "Start a configured local agent.", target: "", prompt_prefix: "" };
  }
}
