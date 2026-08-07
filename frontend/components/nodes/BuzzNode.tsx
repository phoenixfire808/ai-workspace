import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function BuzzNode({ data }: NodeProps<WorkspaceNode>) {
  const onChange = data.onChange;
  return (
    <NodeFrame title="Buzz transcription" subtitle="Whisper on the audio GPU" accent="node-buzz">
      <NodeField label="Audio file (workspace-relative)">
        <input
          className="node-input nodrag"
          value={String(data.file_path ?? "")}
          placeholder="audio/sample.wav"
          onChange={(event) => onChange?.({ file_path: event.target.value })}
        />
      </NodeField>
      <NodeField label="Model size">
        <select
          className="node-input nodrag"
          value={String(data.model_size ?? "small")}
          onChange={(event) => onChange?.({ model_size: event.target.value })}
        >
          <option value="tiny">tiny</option>
          <option value="base">base</option>
          <option value="small">small</option>
          <option value="medium">medium</option>
        </select>
      </NodeField>
      <div className="node-note">No audio is uploaded; the backend invokes the configured local Buzz path.</div>
    </NodeFrame>
  );
}
