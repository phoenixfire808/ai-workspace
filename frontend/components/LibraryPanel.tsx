"use client";

import { useEffect, useMemo, useState } from "react";
import type { LibraryCategory, LibraryResource } from "../lib/library-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const categories: Array<["all" | LibraryCategory, string]> = [["all", "Everything"], ["model", "Models"], ["tool", "Tools"], ["agent", "Agents"], ["skill", "Hermes skills"], ["runtime", "Runtimes"], ["template", "Templates"]];

export default function LibraryPanel({ onAdd, onRun, onDeploy }: { onAdd: (resource: LibraryResource) => void; onRun: (resource: LibraryResource, args: Record<string, unknown>) => void; onDeploy: (resource: LibraryResource) => void }) {
  const [resources, setResources] = useState<LibraryResource[]>([]);
  const [category, setCategory] = useState<"all" | LibraryCategory>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [argumentsText, setArgumentsText] = useState("{}");
  const [notice, setNotice] = useState("");
  const refresh = () => {
    setNotice("Refreshing local registry…");
    fetch(`${API_URL}/api/library?limit=500`).then((r) => r.ok ? r.json() : Promise.reject(new Error(`registry ${r.status}`))).then((p: { resources?: LibraryResource[] }) => {
      setResources(p.resources ?? []); setNotice(`${p.resources?.length ?? 0} local options ready.`);
    }).catch((error: unknown) => setNotice(error instanceof Error ? error.message : "Registry unavailable."));
  };
  useEffect(refresh, []);
  const filtered = useMemo(() => resources.filter((item) => (category === "all" || item.category === category) && `${item.label} ${item.description} ${item.resource_id}`.toLowerCase().includes(query.toLowerCase())), [resources, category, query]);
  const selected = resources.find((item) => item.resource_id === selectedId);
  const parseArgs = () => { try { return JSON.parse(argumentsText) as Record<string, unknown>; } catch { setNotice("Arguments must be valid JSON."); return null; } };
  return <section className="library-panel">
    <div className="panel-heading"><div><span className="eyebrow">DEPLOY</span><h2>Local library</h2></div><button className="toolbar-button" type="button" onClick={refresh}>↻</button></div>
    <p className="panel-copy">Add, run, or deploy every governed local option.</p>
    <select className="control-select" value={category} onChange={(event) => { setCategory(event.target.value as typeof category); setSelectedId(""); }} aria-label="Library category">{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    <input className="control-input library-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search tools, models, skills…" aria-label="Search library" />
    <select className="control-select" size={Math.min(7, Math.max(3, filtered.length))} value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setArgumentsText("{}"); }} aria-label="Local resources">
      {filtered.map((item) => <option key={item.resource_id} value={item.resource_id} disabled={!item.ready}>{item.label}{!item.ready ? ` · ${item.disabled_reason ?? "offline"}` : item.requires_approval ? " · approve" : ""}</option>)}
    </select>
    {selected && <div className="library-detail"><strong>{selected.label}</strong><small>{selected.category} · {selected.scope}</small><p>{selected.description}</p></div>}
    {selected?.capabilities.includes("run_now") && <textarea className="control-textarea library-args" rows={3} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} aria-label="Quick run arguments JSON" />}
    <div className="library-actions">
      <button className="button button-quiet" type="button" disabled={!selected || !selected.ready || !selected.capabilities.includes("add_to_canvas")} onClick={() => selected && onAdd(selected)}>Add to canvas</button>
      <button className="button button-primary" type="button" disabled={!selected || !selected.ready || !selected.capabilities.includes("run_now")} onClick={() => { const args = parseArgs(); if (selected && args) onRun(selected, args); }}>Run now</button>
      <button className="button button-primary" type="button" disabled={!selected || !selected.capabilities.includes("deploy_template")} onClick={() => selected && onDeploy(selected)}>Deploy template</button>
    </div>
    {notice && <div className="control-notice">{notice}</div>}
  </section>;
}
