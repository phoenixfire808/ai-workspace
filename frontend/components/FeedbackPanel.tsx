"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type FeedbackItem = { id: string; kind: "bug" | "feature"; title: string; description: string; steps: string; status: string; failure_class?: string; created_at?: string; github_url?: string };
type PublishPreview = { status: string; failure_class?: string | null; repository?: string; title?: string; body_chars?: number; mutation?: string };

export default function FeedbackPanel({ activeRunId }: { activeRunId: string | null }) {
  const [kind, setKind] = useState<"bug" | "feature">("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState("");
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [preview, setPreview] = useState<PublishPreview | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/feedback?limit=20`);
    if (!response.ok) throw new Error(`Feedback history failed (${response.status}).`);
    const payload = await response.json() as { items?: FeedbackItem[] };
    setItems(payload.items ?? []);
  }, []);

  useEffect(() => { void refresh().catch(() => setNotice("Local feedback history is unavailable.")); }, [refresh]);

  async function createDraft() {
    if (title.trim().length < 3 || !description.trim()) { setNotice("Add a title and description first."); return; }
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`${API_URL}/api/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, title, description, steps, run_id: activeRunId }) });
      const payload = await response.json() as FeedbackItem & { detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? `Draft creation failed (${response.status}).`);
      setTitle(""); setDescription(""); setSteps(""); setPreview(null); setNotice(`Local draft ${payload.id.slice(-8)} saved.`); await refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Draft creation failed."); }
    finally { setBusy(false); }
  }

  async function previewPublisher(item: FeedbackItem) {
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`${API_URL}/api/feedback/${encodeURIComponent(item.id)}/publish-preview`);
      if (!response.ok) throw new Error(`Publisher preview failed (${response.status}).`);
      setPreview(await response.json() as PublishPreview);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Publisher preview failed."); }
    finally { setBusy(false); }
  }

  return <section className="feedback-panel">
    <div className="control-center-heading"><div><span className="eyebrow">LOCAL INTAKE</span><h3>Bug / feature draft</h3></div><span className="control-lock">NO SEND</span></div>
    <p className="control-copy">Drafts persist locally. Publisher readiness is preview-only; external publication is not exposed here.</p>
    <select className="control-select" value={kind} onChange={(event) => setKind(event.target.value as "bug" | "feature")} aria-label="Feedback type"><option value="bug">Bug report</option><option value="feature">Feature suggestion</option></select>
    <input className="control-input" value={title} maxLength={240} onChange={(event) => setTitle(event.target.value)} placeholder="Short title" />
    <textarea className="control-textarea" rows={4} value={description} maxLength={20000} onChange={(event) => setDescription(event.target.value)} placeholder="What happened or what should improve?" />
    <textarea className="control-textarea" rows={3} value={steps} maxLength={20000} onChange={(event) => setSteps(event.target.value)} placeholder="Steps or desired behavior (optional)" />
    <button className="button button-primary full-width" type="button" disabled={busy} onClick={() => void createDraft()}>Save local draft</button>
    <div className="mini-section-title">RECENT LOCAL DRAFTS</div>
    {items.slice(0, 5).map((item) => <div className="upgrade-row" key={item.id}><span title={item.title}>{item.kind} · {item.title}</span><button className="toolbar-button" type="button" disabled={busy} onClick={() => void previewPublisher(item)}>Preview gate</button></div>)}
    {preview && <div className="control-notice">Publisher {preview.status}: {preview.failure_class ?? "configured"} · mutation {preview.mutation ?? "none"}</div>}
    {notice && <div className="control-notice">{notice}</div>}
  </section>;
}
