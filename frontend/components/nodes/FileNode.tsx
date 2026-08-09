import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function FileNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  return (
    <NodeFrame title="File I/O" subtitle="Workspace-rooted local files" accent="node-file">
      <NodeField label="Mode">
        <select
          className="node-input nodrag"
          value={String(data.mode ?? "read")}
          onChange={(event) => onChange?.({ mode: event.target.value })}
        >
          <option value="read">Read file</option>
          <option value="write">Write previous output</option>
        </select>
      </NodeField>
      <NodeField label="Path">
        <input
          className="node-input nodrag"
          value={String(data.path ?? "")}
          placeholder="notes/result.md"
          onChange={(event) => onChange?.({ path: event.target.value })}
        />
      </NodeField>
      <div className="node-note">Paths are checked against the configured workspace root.</div>
    </NodeFrame>
  );
}
