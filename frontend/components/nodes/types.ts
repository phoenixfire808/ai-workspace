import type { Node } from "@xyflow/react";

export type NodeKind = "start" | "buzz" | "planner" | "coder" | "file" | "task" | "agent" | "tool" | "runtime" | "review" | "chat" | "split" | "merge" | "context" | "plugin" | "delegate";
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
    label: "Ollama · installed local models",
    model: "",
  },
};

export const NODE_META: Record<NodeKind, { label: string; icon: string; accent: string; hint: string }> = {
  start: { label: "Start", icon: "◉", accent: "node-start", hint: "Workflow input" },
  buzz: { label: "Buzz transcription", icon: "◌", accent: "node-buzz", hint: "Whisper audio" },
  planner: { label: "Planner", icon: "✦", accent: "node-planner", hint: "Intent to plan" },
  coder: { label: "Coder model", icon: "⌘", accent: "node-coder", hint: "Ollama installed / local alternatives" },
  file: { label: "File I/O", icon: "▣", accent: "node-file", hint: "Workspace files" },
  task: { label: "Task tracker", icon: "☷", accent: "node-task", hint: "SQLite task" },
  agent: { label: "Agent reaction", icon: "↗", accent: "node-agent", hint: "Allowlisted launch" },
  tool: { label: "Governed tool", icon: "⚙", accent: "node-tool", hint: "Registry capability" },
  runtime: { label: "Runtime profile", icon: "◇", accent: "node-runtime", hint: "Exact-model preflight" },
  review: { label: "Human Review", icon: "✓", accent: "node-review", hint: "Pause for approval" },
  chat: { label: "Chat Input", icon: "◫", accent: "node-chat", hint: "Request human context" },
  split: { label: "Split / Router", icon: "⑂", accent: "node-split", hint: "Branch and chunk" },
  merge: { label: "Merge", icon: "⑃", accent: "node-merge", hint: "Join branch outputs" },
  context: { label: "Context", icon: "{}", accent: "node-context", hint: "Select inherited data" },
  plugin: { label: "Plugin", icon: "⬡", accent: "node-plugin", hint: "Registered extension" },
  delegate: { label: "Decompose / Delegate", icon: "⇶", accent: "node-delegate", hint: "Bounded worker assignment" },
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
        provider: "nanbeige",
        model: "nanbeige4.2-3b-local",
        system_prompt: "You are the local workflow planner. Return goal, assumptions, ordered steps, risks, and verification.",
        max_tokens: 4096,
      };
    case "coder":
      return {
        label: "Coder model",
        description: "Generate a result with the selected provider.",
        provider: "ollama",
        model: "",
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
    case "tool":
      return { label: "Governed tool", description: "Run an allowlisted local capability.", resource_id: "", arguments: {} };
    case "runtime":
      return { label: "Runtime profile", description: "Preflight a named local runtime without activating it.", profile_id: "" };
    case "review":
      return { label: "Human Review", description: "Pause durably for a human decision.", prompt: "Review this step before it continues." };
    case "chat":
      return { label: "Chat Input", description: "Pause for additional human context.", prompt: "What should this workflow know before continuing?" };
    case "split":
      return { label: "Split / Router", description: "Fan out or chunk workflow context.", branch_mode: "parallel", chunk_strategy: "paragraphs", chunk_size: 2000, chunk_overlap: 0, max_chunks: 64 };
    case "merge":
      return { label: "Merge", description: "Join all required upstream results.", merge_strategy: "concatenate", separator: "\n\n" };
    case "context":
      return { label: "Context", description: "Select a bounded part of inherited JSON context.", selector: "" };
    case "plugin":
      return { label: "Plugin", description: "Run a registered local extension.", plugin_id: "run_annotation", note: "" };
    case "delegate":
      return { label: "Decompose / Delegate", description: "Split work and assign approved workers.", decompose_strategy: "checklist", dispatch_mode: "plan_only", worker_target: "", max_subtasks: 8, max_parallel: 4, subtasks: "" };
  }
}
