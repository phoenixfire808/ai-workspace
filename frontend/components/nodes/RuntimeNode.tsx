import { useEffect, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";
import type { LibraryResource } from "../../lib/library-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function RuntimeNode({ data }: NodeProps<WorkspaceNode>) {
  const [profiles, setProfiles] = useState<LibraryResource[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/library?category=runtime&limit=100`).then((r) => r.json()).then((p: { resources?: LibraryResource[] }) => {
      if (!cancelled) setProfiles(p.resources ?? []);
    }).catch(() => { if (!cancelled) setProfiles([]); });
    return () => { cancelled = true; };
  }, []);
  const profileId = String(data.profile_id ?? "");
  const selected = profiles.find((profile) => profile.metadata?.profile_id === profileId);
  return <NodeFrame title="Runtime profile" subtitle="Read-only exact-model preflight" accent="node-runtime">
    <NodeField label="Profile">
      <select className="node-input nodrag" value={profileId} onChange={(event) => data.onChange?.({ profile_id: event.target.value })}>
        <option value="">Select a runtime…</option>
        {profiles.map((profile) => <option key={profile.resource_id} value={String(profile.metadata?.profile_id ?? "")} disabled={!profile.ready}>{profile.label}</option>)}
      </select>
    </NodeField>
    <div className="node-note">{selected?.description ?? "Preflight only; this node never starts or repoints a model server."}</div>
  </NodeFrame>;
}
