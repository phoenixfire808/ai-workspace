"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type WebProvenance = { status?: string; backend?: string; query?: string; query_count?: number; result_count?: number; selected_count?: number; domain_count?: number; context_id?: string; packet_sha256?: string; char_count?: number; truncated?: boolean; citations?: string[]; failure_class?: string; detail?: string; sources?: Array<{ source_id?: string; title?: string; url?: string; domain?: string; rank?: number; extraction_status?: string; failure_class?: string }> };
type RunStep = { id: string; node_id: string; node_type: string; branch_key: string; chunk_index?: number | null; status: string; input_context?: Record<string, unknown>; arguments?: Record<string, unknown>; output?: string; provenance?: WebProvenance; failure_class?: string; error_detail?: string; duration_ms?: number };
type DelegateChild = { id: string; subtask_id: string; parent_step_id: string; worker_target: string; assignment: string; status: string; process_id?: number | null; receipt?: Record<string, unknown>; output?: string; failure_class?: string; updated_at?: string };
type Approval = { id: string; step_id: string; action_type: string; status: string; arguments: Record<string, unknown>; impact_preview?: string; note?: string };
type RunSnapshot = { id: string; status: string; approval_policy: string; input_text: string; final_output: string; error_detail: string; created_at?: string; updated_at?: string; steps: RunStep[]; approvals: Approval[]; children?: DelegateChild[]; events: Array<{ sequence: number; event_type: string; payload: Record<string, unknown> }> };
type RunSummary = Pick<RunSnapshot, "id" | "status" | "approval_policy" | "final_output" | "error_detail" | "created_at" | "updated_at">;

function message(value: unknown) { return value instanceof Error ? value.message : "Run inspector request failed."; }

function safeExternalUrl(value?: string) {
  try {
    const parsed = new URL(value ?? "");
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}

function DelegateChildren({ children, parentStepId }: { children: DelegateChild[]; parentStepId: string }) {
  const related = children.filter((child) => child.parent_step_id === parentStepId);
  if (!related.length) return null;
  return <section className="delegate-children"><b>Delegate children</b>{related.map((child) => <details key={child.id}><summary><span>{child.subtask_id}</span><strong>{child.status}</strong><small>{child.worker_target || "plan only"}{child.process_id ? ` · PID ${child.process_id}` : ""}</small></summary><b>Assignment</b><pre className="inspector-pre">{child.assignment}</pre><b>Receipt</b><pre className="inspector-pre">{JSON.stringify(child.receipt ?? {}, null, 2)}</pre><b>Result</b><pre className="inspector-pre">{child.output || child.failure_class || "Pending"}</pre></details>)}</section>;
}

export default function RunInspector({ activeRunId, onOutput, onRunStatus }: { activeRunId: string | null; onOutput: (value: string) => void; onRunStatus: (value: string) => void }) {
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [note, setNote] = useState("");
  const [argumentsText, setArgumentsText] = useState("{}");
  const [notice, setNotice] = useState("");
  const resolvedId = activeRunId || selectedRunId;

  const refreshHistory = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/runs?limit=100`);
    if (!response.ok) throw new Error(`Run history failed (${response.status}).`);
    const payload = await response.json() as { runs?: RunSummary[] };
    setHistory(payload.runs ?? []);
  }, []);

  const refreshRun = useCallback(async (runId: string) => {
    const response = await fetch(`${API_URL}/api/runs/${encodeURIComponent(runId)}`);
    if (!response.ok) throw new Error(`Run load failed (${response.status}).`);
    const payload = await response.json() as RunSnapshot;
    setRun(payload);
    onRunStatus(payload.status);
    if (payload.final_output) onOutput(payload.final_output);
  }, [onOutput, onRunStatus]);

  useEffect(() => { void refreshHistory().catch((error) => setNotice(message(error))); }, [refreshHistory]);
  useEffect(() => {
    if (!resolvedId) { setRun(null); return; }
    void refreshRun(resolvedId).catch((error) => setNotice(message(error)));
    const timer = window.setInterval(() => void refreshRun(resolvedId).catch(() => undefined), 750);
    return () => window.clearInterval(timer);
  }, [refreshRun, resolvedId]);

  const pending = useMemo(() => run?.approvals.find((item) => item.status === "pending") ?? null, [run]);
  useEffect(() => { setArgumentsText(JSON.stringify(pending?.arguments ?? {}, null, 2)); setNote(""); }, [pending?.id]);

  const decide = async (decision: "approve" | "deny" | "cancel" | "edit", approveIdentical = false) => {
    if (!run || !pending) return;
    try {
      const parsed = JSON.parse(argumentsText) as Record<string, unknown>;
      const response = await fetch(`${API_URL}/api/runs/${run.id}/approvals/${pending.id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, arguments: parsed, note, approve_identical: approveIdentical }) });
      const payload = await response.json() as RunSnapshot & { detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? `Decision failed (${response.status}).`);
      setRun(payload); setNotice(`${decision} recorded.`); await refreshHistory();
    } catch (error) { setNotice(message(error)); }
  };

  const sendChat = async () => {
    if (!run || !note.trim()) return;
    try {
      const response = await fetch(`${API_URL}/api/runs/${run.id}/input`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: note }) });
      if (!response.ok) throw new Error(`Chat continuation failed (${response.status}).`);
      setRun(await response.json() as RunSnapshot); setNote("");
    } catch (error) { setNotice(message(error)); }
  };

  const removeRun = async () => {
    if (!run || !window.confirm(`Delete local run ${run.id.slice(0, 8)} and all retained context?`)) return;
    try {
      const response = await fetch(`${API_URL}/api/runs/${run.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`Run deletion failed (${response.status}).`);
      setRun(null); setSelectedRunId(""); await refreshHistory(); setNotice("Run context deleted.");
    } catch (error) { setNotice(message(error)); }
  };

  return <section className="run-inspector">
    <div className="panel-heading"><div><span className="eyebrow">RUN INSPECTOR</span><h2>Context & decisions</h2></div><button className="toolbar-button" type="button" onClick={() => void refreshHistory()}>↻</button></div>
    <select className="control-select" value={resolvedId} onChange={(event) => setSelectedRunId(event.target.value)} aria-label="Run history"><option value="">Select retained run…</option>{history.map((item) => <option key={item.id} value={item.id}>{item.id.slice(0, 8)} · {item.status} · {item.updated_at ? new Date(item.updated_at).toLocaleString() : ""}</option>)}</select>
    {!run && <p className="panel-copy">Execute a flow or select retained local run context.</p>}
    {run && <>
      <div className="run-summary"><strong>{run.id.slice(0, 8)}</strong><span className={`status-badge status-${run.status}`}>{run.status}</span><small>{run.approval_policy}</small></div>
      <details><summary>Run input and context</summary><pre className="inspector-pre">{run.input_text}</pre></details>
      {pending && <section className="decision-card"><span className="eyebrow">HUMAN IN THE LOOP</span><h3>{pending.action_type.replaceAll("_", " ")}</h3><textarea className="control-textarea" rows={6} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} aria-label="Reviewed arguments" />{pending.impact_preview && <pre className="impact-preview">{pending.impact_preview}</pre>}<textarea className="control-textarea" rows={3} placeholder={pending.action_type === "chat_input" ? "Your context…" : "Decision note (optional)…"} value={note} onChange={(event) => setNote(event.target.value)} />{pending.action_type === "chat_input" ? <button className="button button-primary full-width" type="button" onClick={() => void sendChat()}>Send context and continue</button> : <div className="decision-actions"><button className="button button-quiet" type="button" onClick={() => void decide("deny")}>Deny</button><button className="button button-quiet" type="button" onClick={() => void decide("edit")}>Save edits</button><button className="button button-primary" type="button" onClick={() => void decide("approve")}>Approve once</button><button className="button button-primary" type="button" onClick={() => void decide("approve", true)}>Approve identical</button></div>}</section>}
      <div className="run-timeline">{run.steps.map((step) => <details key={step.id} className={`run-step run-step-${step.status}`}><summary><span>{step.node_type}</span><strong>{step.status}</strong><small>{step.branch_key}{step.chunk_index !== null && step.chunk_index !== undefined ? ` · chunk ${step.chunk_index}` : ""} · {step.duration_ms ?? 0} ms</small></summary><div><b>Node</b> {step.node_id}</div><b>Arguments</b><pre className="inspector-pre">{JSON.stringify(step.arguments ?? {}, null, 2)}</pre><b>Inherited context</b><pre className="inspector-pre">{JSON.stringify(step.input_context ?? {}, null, 2)}</pre>{step.provenance && Object.keys(step.provenance).length > 0 && <section className="web-provenance"><b>Web provenance</b><div className="provenance-summary"><span>{step.provenance.backend ?? "context packet"}</span><span>{step.provenance.result_count ?? step.provenance.selected_count ?? 0} results</span><span>{step.provenance.char_count ?? 0} chars</span></div>{step.provenance.packet_sha256 && <small>packet {step.provenance.packet_sha256.slice(0, 16)}…</small>}{step.provenance.sources?.map((source) => <a key={`${source.source_id}-${source.url}`} href={safeExternalUrl(source.url)} target="_blank" rel="noreferrer"><strong>{source.source_id}</strong> {source.title || source.domain || source.url}<small>{source.extraction_status || source.failure_class || "selected"}</small></a>)}{step.provenance.failure_class && <div className="control-notice">{step.provenance.failure_class}: {step.provenance.detail}</div>}</section>}<DelegateChildren children={run.children ?? []} parentStepId={step.id} /><b>Output</b><pre className="inspector-pre">{step.output || step.error_detail || "Pending"}</pre></details>)}</div>
      {run.error_detail && <div className="control-notice">{run.error_detail}</div>}
      <button className="button button-quiet full-width" type="button" disabled={run.status === "running"} onClick={() => void removeRun()}>Delete retained run context</button>
    </>}
    {notice && <div className="control-notice">{notice}</div>}
  </section>;
}
