import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function TaskNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  return (
    <NodeFrame title="Task tracker" subtitle="SQLite-backed task state" accent="node-task">
      <NodeField label="Title">
        <input
          className="node-input nodrag"
          value={String(data.title ?? "")}
          placeholder="Task title from input"
          onChange={(event) => onChange?.({ title: event.target.value })}
        />
      </NodeField>
      <NodeField label="Status">
        <select
          className="node-input nodrag"
          value={String(data.status ?? "todo")}
          onChange={(event) => onChange?.({ status: event.target.value })}
        >
          <option value="todo">Todo</option>
          <option value="in_progress">In progress</option>
          <option value="done">Done</option>
          <option value="blocked">Blocked</option>
        </select>
      </NodeField>
      <NodeField label="Notes">
        <textarea
          className="node-input node-textarea nodrag"
          rows={2}
          value={String(data.notes ?? "")}
          onChange={(event) => onChange?.({ notes: event.target.value })}
        />
      </NodeField>
    </NodeFrame>
  );
}
