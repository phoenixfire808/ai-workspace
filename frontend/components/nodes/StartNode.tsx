import type { NodeProps } from "@xyflow/react";
import NodeFrame from "./NodeFrame";
import type { WorkspaceNode } from "./types";

export default function StartNode(_props: NodeProps<WorkspaceNode>) {
  return (
    <NodeFrame title="Start" subtitle="Workflow input" accent="node-start" showTarget={false}>
      <div className="node-note">Receives the text supplied in the Run panel and passes it into the graph.</div>
      <div className="node-chip">input_text</div>
    </NodeFrame>
  );
}
