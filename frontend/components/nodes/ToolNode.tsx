import { useEffect, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";
import type { LibraryResource } from "../../lib/library-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function ToolNode({ data }: NodeProps<WorkspaceNode>) {
  const [tools, setTools] = useState<LibraryResource[]>([]);
  const resourceId = String(data.resource_id ?? "");
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/library?category=tool&limit=200`).then((r) => r.json()).then((p: { resources?: LibraryResource[] }) => {
      if (!cancelled) setTools(p.resources ?? []);
    }).catch(() => { if (!cancelled) setTools([]); });
    return () => { cancelled = true; };
  }, []);
  const selected = tools.find((tool) => tool.resource_id === resourceId);
  return <NodeFrame title="Governed tool" subtitle="Allowlisted local capability" accent="node-tool">
    <NodeField label="Tool">
      <select className="node-input nodrag" value={resourceId} onChange={(event) => data.onChange?.({ resource_id: event.target.value, arguments: {} })}>
        <option value="">Select a tool…</option>
        {tools.map((tool) => <option key={tool.resource_id} value={tool.resource_id} disabled={!tool.ready}>{tool.label}{tool.requires_approval ? " · approval" : ""}</option>)}
      </select>
    </NodeField>
    <NodeField label="Arguments (JSON)">
      <textarea className="node-input node-textarea nodrag" rows={3} value={JSON.stringify(data.arguments ?? {}, null, 2)} onChange={(event) => { try { data.onChange?.({ arguments: JSON.parse(event.target.value) }); } catch { /* keep last valid object */ } }} />
    </NodeField>
    <div className="node-note">{selected?.description ?? "Choose one registry-backed tool."}</div>
  </NodeFrame>;
}
