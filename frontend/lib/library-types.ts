export type LibraryCategory = "tool" | "agent" | "skill" | "model" | "runtime" | "template";

export type LibraryResource = {
  resource_id: string;
  category: LibraryCategory;
  label: string;
  description: string;
  scope: string;
  ready: boolean;
  disabled_reason?: string | null;
  requires_approval: boolean;
  capabilities: string[];
  arguments_schema?: { properties?: Record<string, { type?: string; title?: string; default?: unknown }> };
  provider?: string | null;
  model?: string | null;
  metadata?: Record<string, unknown>;
};

export type ApprovalItem = { resource_id: string; label: string; scope: string };
export type ApprovalPreview = { preview_id: string; approvals: ApprovalItem[]; requires_approval: boolean };
