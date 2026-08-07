"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import NodeFrame, { NodeField } from "./NodeFrame";
import type { WorkspaceNode } from "./types";

type PlaybackState = "idle" | "speaking" | "stopped" | "completed" | "error";

export default function TtsNode({ data }: NodeProps<WorkspaceNode>) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [state, setState] = useState<PlaybackState>("idle");
  const lastText = useRef("");
  const localVoices = useMemo(() => voices.filter((voice) => voice.localService), [voices]);

  useEffect(() => {
    const refresh = () => setVoices(window.speechSynthesis?.getVoices() ?? []);
    refresh();
    window.speechSynthesis?.addEventListener("voiceschanged", refresh);
    return () => {
      window.speechSynthesis?.removeEventListener("voiceschanged", refresh);
      window.speechSynthesis?.cancel();
    };
  }, []);

  const speak = (replay = false) => {
    const text = replay ? lastText.current : String(data.text ?? "").trim();
    const selected = localVoices.find((voice) => voice.voiceURI === String(data.voice_uri ?? "")) ?? localVoices[0];
    if (!text || !selected || !window.speechSynthesis) { setState("error"); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = selected;
    utterance.rate = Math.min(2, Math.max(0.5, Number(data.rate ?? 1)));
    utterance.pitch = Math.min(2, Math.max(0, Number(data.pitch ?? 1)));
    utterance.onstart = () => setState("speaking");
    utterance.onend = () => setState("completed");
    utterance.onerror = () => setState("error");
    lastText.current = text;
    window.speechSynthesis.speak(utterance);
  };

  const stop = () => { window.speechSynthesis?.cancel(); setState("stopped"); };
  const selectedVoice = String(data.voice_uri ?? localVoices[0]?.voiceURI ?? "");

  return <NodeFrame title="Local TTS" subtitle="Manual local playback" accent="node-tts">
    <NodeField label="Text"><textarea className="nodrag" rows={4} placeholder="Enter text for explicit local playback" value={String(data.text ?? "")} onChange={(event) => data.onChange?.({ text: event.target.value })} /></NodeField>
    <NodeField label="Local voice"><select className="nodrag" value={selectedVoice} onChange={(event) => data.onChange?.({ voice_uri: event.target.value })}><option value="">{localVoices.length ? "Select local voice" : "No local browser voice"}</option>{localVoices.map((voice) => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} · {voice.lang}</option>)}</select></NodeField>
    <NodeField label="Rate"><input className="nodrag" type="number" min={0.5} max={2} step={0.1} value={Number(data.rate ?? 1)} onChange={(event) => data.onChange?.({ rate: Number(event.target.value) })} /></NodeField>
    <div className="node-action-row"><button className="nodrag" type="button" disabled={!localVoices.length || !String(data.text ?? "").trim()} onClick={() => speak(false)}>Speak</button><button className="nodrag" type="button" disabled={state !== "speaking"} onClick={stop}>Stop</button><button className="nodrag" type="button" disabled={!lastText.current || !localVoices.length} onClick={() => speak(true)}>Replay</button></div>
    <small>State: {state} · local voices: {localVoices.length}. Playback occurs only after a button click; remote voices are excluded.</small>
  </NodeFrame>;
}
