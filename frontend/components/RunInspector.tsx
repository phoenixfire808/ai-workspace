"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type RunStep = { id: string; node_id: string; node_type: string; branch_key: string; chunk_index?: number | null; status: string; input_context?: Record<string, unknown>; arguments?: Record<string, unknown>; output?: string; failure_class?: string; error_detail?: string; duration_ms?: number };
type Approval = { id: string; step_id: string; action_type: string; status: string; arguments: Record<string, unknown>; impact_preview?: string; note?: string };
type RunSnapshot = { id: string; status: string; approval_policy: string; input_text: string; final_output: string; error_detail: string; created_at?: string; updated_at?: string; steps: RunStep[]; approvals: Approval[]; events: Array<{ sequence: number; event_type: string; payload: Record<string, unknown> }> };
type RunSummary = Pick<RunSnapshot, "id" | "status" | "approval_policy" | "final_output" | "error_detail" | "created_at" | "updated_at">;

function message(value: unknown) { return value instanceof Error ? value.message : "Run inspector request failed."; }

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
      <div className="run-timeline">{run.steps.map((step) => <details key={step.id} className={`run-step run-step-${step.status}`}><summary><span>{step.node_type}</span><strong>{step.status}</strong><small>{step.branch_key}{step.chunk_index !== null && step.chunk_index !== undefined ? ` · chunk ${step.chunk_index}` : ""} · {step.duration_ms ?? 0} ms</small></summary><div><b>Node</b> {step.node_id}</div><b>Arguments</b><pre className="inspector-pre">{JSON.stringify(step.arguments ?? {}, null, 2)}</pre><b>Inherited context</b><pre className="inspector-pre">{JSON.stringify(step.input_context ?? {}, null, 2)}</pre><b>Output</b><pre className="inspector-pre">{step.output || step.error_detail || "Pending"}</pre></details>)}</div>
      {run.error_detail && <div className="control-notice">{run.error_detail}</div>}
      <button className="button button-quiet full-width" type="button" disabled={run.status === "running"} onClick={() => void removeRun()}>Delete retained run context</button>
    </>}
    {notice && <div className="control-notice">{notice}</div>}
  </section>;
}
