"use client";

import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

function update(data: WorkspaceNode["data"], patch: Record<string, unknown>) {
  data.onChange?.(patch);
}

export function SearchNode({ data }: NodeProps<WorkspaceNode>) {
  return <NodeFrame title="Search web" subtitle="Local SearXNG discovery" accent="node-search">
    <NodeField label="Query"><textarea className="nodrag" rows={3} placeholder="Uses inherited input when blank" value={String(data.query ?? "")} onChange={(event) => update(data, { query: event.target.value })} /></NodeField>
    <NodeField label="Category"><input className="nodrag" value={String(data.categories ?? "general")} onChange={(event) => update(data, { categories: event.target.value })} /></NodeField>
    <NodeField label="Results"><input className="nodrag" type="number" min={1} max={20} value={Number(data.max_results ?? 10)} onChange={(event) => update(data, { max_results: Number(event.target.value) })} /></NodeField>
    <NodeField label="Safe search"><select className="nodrag" value={Number(data.safe_search ?? 1)} onChange={(event) => update(data, { safe_search: Number(event.target.value) })}><option value={0}>Off</option><option value={1}>Moderate</option><option value={2}>Strict</option></select></NodeField>
    <small>Discovery stays on the configured loopback SearXNG backend. No cloud-search fallback.</small>
  </NodeFrame>;
}

export function ResearchNode({ data }: NodeProps<WorkspaceNode>) {
  return <NodeFrame title="Deep research" subtitle="Bounded search and extraction" accent="node-research">
    <NodeField label="Research query"><textarea className="nodrag" rows={3} placeholder="Uses inherited input when blank" value={String(data.query ?? "")} onChange={(event) => update(data, { query: event.target.value })} /></NodeField>
    <NodeField label="Additional queries"><textarea className="nodrag" rows={3} placeholder="One per line" value={String(data.queries ?? "")} onChange={(event) => update(data, { queries: event.target.value })} /></NodeField>
    <NodeField label="Maximum pages"><input className="nodrag" type="number" min={1} max={24} value={Number(data.max_pages ?? 12)} onChange={(event) => update(data, { max_pages: Number(event.target.value) })} /></NodeField>
    <NodeField label="Per domain"><input className="nodrag" type="number" min={1} max={5} value={Number(data.per_domain ?? 2)} onChange={(event) => update(data, { per_domain: Number(event.target.value) })} /></NodeField>
    <label className="node-check"><input className="nodrag" type="checkbox" checked={data.extract_pages !== false} onChange={(event) => update(data, { extract_pages: event.target.checked })} /> Extract selected public pages</label>
    <small>Page extraction is approval-gated and enforces public URL, DNS, robots, redirect, timeout, and size limits.</small>
  </NodeFrame>;
}

export function SourceContextNode({ data }: NodeProps<WorkspaceNode>) {
  return <NodeFrame title="Source context" subtitle="Citation-preserving packet" accent="node-source-context">
    <NodeField label="Maximum characters"><input className="nodrag" type="number" min={2000} max={60000} value={Number(data.max_chars ?? 30000)} onChange={(event) => update(data, { max_chars: Number(event.target.value) })} /></NodeField>
    <NodeField label="Additional user context"><textarea className="nodrag" rows={3} value={String(data.context_text ?? "")} onChange={(event) => update(data, { context_text: event.target.value })} /></NodeField>
    <small>Inherited research JSON supplies sources automatically. Output retains source IDs, URLs, citations, size, and packet hash.</small>
  </NodeFrame>;
}
