"use client";

import { useEffect, useMemo, useState } from "react";
import type { LibraryCategory, LibraryResource } from "../lib/library-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const RESOURCE_MIME = "application/x-mo-library-resource";
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
  const argumentValues = useMemo(() => { try { return JSON.parse(argumentsText) as Record<string, unknown>; } catch { return {}; } }, [argumentsText]);
  const setArgument = (name: string, value: unknown) => setArgumentsText(JSON.stringify({ ...argumentValues, [name]: value }, null, 2));
  return <section className="library-panel">
    <div className="panel-heading"><div><span className="eyebrow">DEPLOY</span><h2>Local library</h2></div><button className="toolbar-button" type="button" onClick={refresh}>↻</button></div>
    <p className="panel-copy">Add, run, or deploy every governed local option.</p>
    <select className="control-select" value={category} onChange={(event) => { setCategory(event.target.value as typeof category); setSelectedId(""); }} aria-label="Library category">{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    <input className="control-input library-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search tools, models, skills…" aria-label="Search library" />
    <div className="library-list-resizer" title="Drag the lower-right corner to show more or fewer options">
      <select className="control-select library-resource-list" size={Math.min(16, Math.max(12, filtered.length))} value={selectedId} onChange={(event) => { const item = resources.find((candidate) => candidate.resource_id === event.target.value); setSelectedId(event.target.value); setArgumentsText(JSON.stringify(Object.fromEntries(Object.entries(item?.arguments_schema?.properties ?? {}).filter(([, property]) => property.default !== undefined).map(([name, property]) => [name, property.default])), null, 2)); }} onDoubleClick={() => selected?.ready && selected.capabilities.includes("add_to_canvas") && onAdd(selected)} aria-label="Local resources">
        {filtered.map((item) => <option key={item.resource_id} value={item.resource_id} disabled={!item.ready}>{item.label}{!item.ready ? ` · ${item.disabled_reason ?? "offline"}` : item.requires_approval ? " · approve" : ""}</option>)}
      </select>
    </div>
    {selected && <div className="library-detail" draggable={selected.ready && selected.capabilities.includes("add_to_canvas")} onDragStart={(event) => { event.dataTransfer.setData(RESOURCE_MIME, JSON.stringify(selected)); event.dataTransfer.effectAllowed = "copy"; }} title="Drag this resource onto the canvas or double-click it in the list"><strong>{selected.label}</strong><small>{selected.category} · {selected.scope} · drag or double-click to place</small><p>{selected.description}</p></div>}
    {selected?.capabilities.includes("run_now") && <div className="schema-arguments">{Object.entries(selected.arguments_schema?.properties ?? {}).map(([name, property]) => <label className="control-label" key={name}><span>{property.title ?? name}</span>{property.enum ? <select className="control-select" value={String(argumentValues[name] ?? property.default ?? "")} onChange={(event) => setArgument(name, event.target.value)}>{property.enum.map((value) => <option key={String(value)} value={String(value)}>{String(value)}</option>)}</select> : property.type === "boolean" ? <input type="checkbox" checked={Boolean(argumentValues[name] ?? property.default)} onChange={(event) => setArgument(name, event.target.checked)} /> : <input className="control-input" type={property.type === "integer" || property.type === "number" ? "number" : "text"} value={String(argumentValues[name] ?? property.default ?? "")} onChange={(event) => setArgument(name, property.type === "integer" || property.type === "number" ? Number(event.target.value) : event.target.value)} />}</label>)}<details><summary>Advanced JSON arguments</summary><textarea className="control-textarea library-args" rows={4} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} aria-label="Quick run arguments JSON" /></details></div>}
    <div className="library-actions">
      <button className="button button-quiet" type="button" disabled={!selected || !selected.ready || !selected.capabilities.includes("add_to_canvas")} onClick={() => selected && onAdd(selected)}>Add to canvas</button>
      <button className="button button-primary" type="button" disabled={!selected || !selected.ready || !selected.capabilities.includes("run_now")} onClick={() => { const args = parseArgs(); if (selected && args) onRun(selected, args); }}>Run now</button>
      <button className="button button-primary" type="button" disabled={!selected || !selected.capabilities.includes("deploy_template")} onClick={() => selected && onDeploy(selected)}>Deploy template</button>
    </div>
    {notice && <div className="control-notice">{notice}</div>}
  </section>;
}
