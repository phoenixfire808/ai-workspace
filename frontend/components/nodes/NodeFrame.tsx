import { Handle, Position } from "@xyflow/react";
import type { ReactNode } from "react";

interface NodeFrameProps {
  title: string;
  subtitle: string;
  accent: string;
  children: ReactNode;
  showTarget?: boolean;
  showSource?: boolean;
}

export default function NodeFrame({
  title,
  subtitle,
  accent,
  children,
  showTarget = true,
  showSource = true,
}: NodeFrameProps) {
  return (
    <div className={`node-card ${accent}`}>
      {showTarget && <Handle className="node-handle target-handle" position={Position.Left} type="target" />}
      <div className="node-card-header">
        <div>
          <div className="node-card-title">{title}</div>
          <div className="node-card-subtitle">{subtitle}</div>
        </div>
      </div>
      <div className="node-card-body">{children}</div>
      {showSource && <Handle className="node-handle source-handle" position={Position.Right} type="source" />}
    </div>
  );
}

export function NodeField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="node-field">
      <span>{label}</span>
      {children}
    </label>
  );
}
