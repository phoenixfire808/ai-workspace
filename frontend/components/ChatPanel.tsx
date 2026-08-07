"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "event";
  content: string;
};

type ToolInfo = {
  name: string;
  description: string;
  requires_approval: boolean;
  scope: string;
};

type StreamFrame = {
  event: string;
  data: Record<string, unknown>;
};

function parseFrame(block: string): StreamFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  const raw = dataLines.join("\n");
  if (!raw) return null;
  try {
    return { event, data: JSON.parse(raw) as Record<string, unknown> };
  } catch {
    return { event, data: { detail: raw } };
  }
}

function frameText(frame: StreamFrame): string {
  if (frame.event === "token") return String(frame.data.content ?? "");
  if (frame.event === "tool_start") return `tool started · ${String(frame.data.tool ?? "unknown")}`;
  if (frame.event === "tool_end") return `tool completed · ${String(frame.data.tool ?? "unknown")} · ${String(frame.data.output_chars ?? 0)} chars`;
  if (frame.event === "approval_required") return `approval required · ${Array.isArray(frame.data.tools) ? frame.data.tools.join(", ") : "tool"}`;
  if (frame.event === "loop_limit") return "bounded loop limit reached";
  if (frame.event === "error") return String(frame.data.detail ?? "local agent error");
  return String(frame.data.status ?? frame.data.detail ?? frame.event);
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [lastPrompt, setLastPrompt] = useState("");
  const [pendingTools, setPendingTools] = useState<string[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [maxLoops, setMaxLoops] = useState(4);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_URL}/api/chat/tools`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("tool catalog unavailable"))))
      .then((payload: { tools?: ToolInfo[] }) => {
        if (!cancelled) setTools(Array.isArray(payload.tools) ? payload.tools : []);
      })
      .catch(() => {
        if (!cancelled) setTools([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const approvalLabels = useMemo(
    () => pendingTools.map((name) => tools.find((tool) => tool.name === name)?.description ?? name),
    [pendingTools, tools],
  );

  const send = useCallback(async (prompt: string, approved: string[] = []) => {
    const trimmed = prompt.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setLastPrompt(trimmed);
    setPendingTools([]);
    const assistantId = `assistant-${Date.now()}`;
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: trimmed },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          approved_tools: approved,
          max_loops: maxLoops,
          active_hardware_lane: "ollama-auto",
        }),
      });
      if (!response.ok || !response.body) throw new Error(`chat request failed (${response.status})`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let done = false;
      while (!done) {
        const result = await reader.read();
        done = result.done;
        buffer = `${buffer}${decoder.decode(result.value ?? new Uint8Array(), { stream: !done })}`.replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const frame = parseFrame(block);
          if (!frame) continue;
          if (frame.event === "token") {
            setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: `${message.content}${String(frame.data.content ?? "")}` } : message));
          } else if (frame.event === "approval_required") {
            const requested = Array.isArray(frame.data.tools) ? frame.data.tools.map(String) : [];
            setPendingTools(requested);
            setMessages((current) => [...current, { id: `event-${Date.now()}-${frame.event}`, role: "event", content: frameText(frame) }]);
          } else {
            const text = frameText(frame);
            if (frame.event !== "run_started" && frame.event !== "complete") {
              setMessages((current) => [...current, { id: `event-${Date.now()}-${frame.event}`, role: "event", content: text }]);
            }
          }
        }
      }
      const finalFrame = parseFrame(buffer);
      if (finalFrame && finalFrame.event === "token") {
        setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: `${message.content}${String(finalFrame.data.content ?? "")}` } : message));
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "local chat request failed";
      setMessages((current) => [...current, { id: `event-${Date.now()}-error`, role: "event", content: detail }]);
    } finally {
      setBusy(false);
    }
  }, [busy, maxLoops]);

  const submit = () => {
    const prompt = draft;
    setDraft("");
    void send(prompt);
  };

  return (
    <section className="chat-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">AGENT CHAT</span><h2>Local coding loop</h2></div>
        <span className="output-lock">approval-aware</span>
      </div>
      <p className="panel-copy">LFM is opt-in for this chat route. Read-only workspace tools can run automatically; code execution and Hermes dispatch pause for approval.</p>
      <div className="chat-transcript" aria-live="polite">
        {messages.length === 0 && <div className="chat-empty">Ask for a plan, codebase inspection, or bounded local computation.</div>}
        {messages.map((message) => <div key={message.id} className={`chat-message chat-${message.role}`}><span>{message.role === "user" ? "YOU" : message.role === "event" ? "EVENT" : "M⊕"}</span><p>{message.content || (message.role === "assistant" ? "…" : "")}</p></div>)}
      </div>
      {pendingTools.length > 0 && (
        <div className="chat-approval">
          <strong>Approval needed once</strong>
          {approvalLabels.map((label) => <small key={label}>{label}</small>)}
          <div className="chat-approval-actions">
            <button className="button button-primary" type="button" onClick={() => void send(lastPrompt, pendingTools)} disabled={busy}>Approve and resume</button>
            <button className="button button-quiet" type="button" onClick={() => setPendingTools([])} disabled={busy}>Deny</button>
          </div>
        </div>
      )}
      <label className="control-label" htmlFor="agent-chat-input">Message</label>
      <textarea id="agent-chat-input" className="control-textarea chat-input" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submit(); }} rows={4} placeholder="Ask the local agent to inspect or reason about this workspace…" disabled={busy} />
      <div className="chat-controls"><label htmlFor="chat-max-loops">Max loops</label><input id="chat-max-loops" type="number" min={1} max={8} value={maxLoops} onChange={(event) => setMaxLoops(Math.min(8, Math.max(1, Number(event.target.value) || 1)))} disabled={busy} /><button className="button button-primary" type="button" onClick={submit} disabled={busy || !draft.trim()}>{busy ? "Running…" : "Send"}</button></div>
      <div className="chat-tool-list"><span className="mini-section-title">AVAILABLE LOCAL TOOLS</span>{tools.map((tool) => <span key={tool.name} className={tool.requires_approval ? "chat-tool approval" : "chat-tool"}>{tool.name}{tool.requires_approval ? " · approve" : ""}</span>)}</div>
    </section>
  );
}
