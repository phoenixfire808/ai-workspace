"use client";

import { useEffect, useRef, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type CaptureState = "idle" | "requesting_consent" | "preparing_device" | "recording" | "transcribing" | "stopped" | "error";

export default function BuzzNode({ data }: NodeProps<WorkspaceNode>) {
  const [state, setState] = useState<CaptureState>("idle");
  const [detail, setDetail] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const cancelledRef = useRef(false);
  const requestRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const consent = data.capture_consent === true;

  const release = () => {
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  };

  useEffect(() => () => {
    cancelledRef.current = true;
    requestRef.current?.abort();
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    release();
  }, []);

  const transcribe = async (blob: Blob) => {
    setState("transcribing");
    const durationMs = Math.max(0, Math.round(performance.now() - startedAtRef.current));
    try {
      const controller = new AbortController();
      requestRef.current = controller;
      const params = new URLSearchParams({ model_size: String(data.model_size ?? "small"), consent: "true", duration_ms: String(durationMs) });
      const response = await fetch(`${API_URL}/api/audio/transcribe?${params}`, { method: "POST", headers: { "Content-Type": blob.type || "audio/webm" }, body: blob, signal: controller.signal });
      const payload = await response.json() as { transcript?: string; provenance?: Record<string, unknown>; detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? `Transcription failed (${response.status}).`);
      data.onChange?.({ transcript: payload.transcript ?? "", transcript_provenance: payload.provenance ?? {}, input_mode: "captured_transcript" });
      setState("stopped");
      setDetail("Local transcription complete; temporary audio was deleted.");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") { setState("idle"); setDetail("Transcription cancelled."); return; }
      setState("error");
      setDetail(error instanceof Error ? error.message : "Local transcription failed.");
    } finally {
      requestRef.current = null;
    }
  };

  const start = async () => {
    setState("requesting_consent");
    setDetail("");
    if (!consent) { setState("error"); setDetail("Enable explicit microphone consent first."); return; }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") { setState("error"); setDetail("This browser does not expose local microphone recording."); return; }
    try {
      setState("preparing_device");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      cancelledRef.current = false;
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onerror = () => { release(); setState("error"); setDetail("The browser microphone recorder failed."); };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        release();
        if (cancelledRef.current) { chunksRef.current = []; setState("idle"); setDetail("Capture cancelled; audio discarded."); return; }
        void transcribe(blob);
      };
      startedAtRef.current = performance.now();
      recorder.start(250);
      timeoutRef.current = window.setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, 5 * 60 * 1000);
      setState("recording");
    } catch (error) {
      release();
      setState("error");
      setDetail(error instanceof Error ? error.message : "Microphone consent or device preparation failed.");
    }
  };

  const stop = () => { if (recorderRef.current?.state === "recording") recorderRef.current.stop(); };
  const cancel = () => { cancelledRef.current = true; requestRef.current?.abort(); if (recorderRef.current?.state === "recording") recorderRef.current.stop(); else { release(); setState("idle"); } };

  return <NodeFrame title="Buzz transcription" subtitle="Explicit local capture or workspace file" accent="node-buzz">
    <label className="node-check"><input className="nodrag" type="checkbox" checked={consent} disabled={state === "recording" || state === "transcribing"} onChange={(event) => data.onChange?.({ capture_consent: event.target.checked })} /> I explicitly consent to microphone capture for this recording</label>
    <div className="node-action-row"><button className="nodrag" type="button" disabled={!consent || !["idle", "stopped", "error"].includes(state)} onClick={() => void start()}>Record</button><button className="nodrag" type="button" disabled={state !== "recording"} onClick={stop}>Stop</button><button className="nodrag" type="button" disabled={!(["preparing_device", "recording", "transcribing"] as CaptureState[]).includes(state)} onClick={cancel}>Cancel</button></div>
    <small>State: {state}{detail ? ` · ${detail}` : ""}</small>
    <NodeField label="Audio file (workspace-relative)"><input className="node-input nodrag" value={String(data.file_path ?? "")} placeholder="audio/sample.wav" onChange={(event) => data.onChange?.({ file_path: event.target.value, input_mode: "workspace_file" })} /></NodeField>
    <NodeField label="Model size"><select className="node-input nodrag" value={String(data.model_size ?? "small")} onChange={(event) => data.onChange?.({ model_size: event.target.value })}><option value="tiny">tiny</option><option value="base">base</option><option value="small">small</option><option value="medium">medium</option></select></NodeField>
    {String(data.transcript ?? "") && <NodeField label="Captured transcript handoff"><textarea className="nodrag" rows={4} value={String(data.transcript ?? "")} onChange={(event) => data.onChange?.({ transcript: event.target.value })} /></NodeField>}
    <div className="node-note">Audio stays loopback/local, is not logged, and temporary capture artifacts are deleted after Buzz returns.</div>
  </NodeFrame>;
}
