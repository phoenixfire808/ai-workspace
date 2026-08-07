"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type RuntimeProfile = {
  profile_id: string;
  label: string;
  provider: string;
  model: string;
  state: string;
  mode: string;
  lanes: Array<{ lane_id: string; label: string; physical_gpu_index?: number | null; endpoint?: string | null }>;
  notes: string;
};

type Preflight = {
  status: string;
  checks?: Array<{ name: string; ok: boolean; detail: string }>;
  endpoints?: Array<{ lane_id: string; status: string; exact_model: boolean }>;
  mutation?: string;
};

type TerminalResult = {
  status: string;
  reason?: string;
  cwd?: string | null;
  executable?: string;
  command_chars?: number;
  requires_approval?: boolean;
};

type UpgradeInventory = {
  items: Array<{ item_id: string; label: string; state: string; kind: string }>;
  upgrade_policy: Record<string, string>;
};

type UpgradePreflight = {
  status: string;
  checks: Array<{ name: string; ok: boolean; detail: string }>;
  rollback: { available: boolean; reason: string };
};

type OllamaInventory = {
  status: string;
  default_model?: string;
  models: Array<{ name: string; size?: number | null; openai_advertised?: boolean }>;
};

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`Control Center request failed (${response.status}).`);
  return response.json() as Promise<T>;
}

function stateClass(value?: string) {
  if (!value) return "control-state control-state-muted";
  return value === "ready" || value === "active-baseline" || value === "active-local" || value === "present"
    ? "control-state control-state-good"
    : "control-state control-state-warn";
}

export default function ControlCenterPanel() {
  const [profiles, setProfiles] = useState<RuntimeProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [inventory, setInventory] = useState<UpgradeInventory | null>(null);
  const [upgradePreflight, setUpgradePreflight] = useState<UpgradePreflight | null>(null);
  const [ollamaInventory, setOllamaInventory] = useState<OllamaInventory | null>(null);
  const [terminalCommand, setTerminalCommand] = useState("git status --short");
  const [terminalResult, setTerminalResult] = useState<TerminalResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const refreshUpgrade = useCallback(async () => {
    const [nextInventory, nextPreflight] = await Promise.all([
      readJson<UpgradeInventory>(`${API_URL}/api/upgrades/inventory`),
      readJson<UpgradePreflight>(`${API_URL}/api/upgrades/preflight`),
    ]);
    setInventory(nextInventory);
    setUpgradePreflight(nextPreflight);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      readJson<{ profiles: RuntimeProfile[] }>(`${API_URL}/api/runtime/profiles`),
      refreshUpgrade(),
      readJson<OllamaInventory>(`${API_URL}/api/ollama/models`),
    ]).then(([runtime, _upgrade, ollama]) => {
      if (cancelled) return;
      setProfiles(runtime.profiles);
      setSelectedProfile(runtime.profiles[0]?.profile_id ?? "");
      setOllamaInventory(ollama);
    }).catch((error: unknown) => {
      if (!cancelled) setNotice(error instanceof Error ? error.message : "Control Center is offline.");
    });
    return () => { cancelled = true; };
  }, [refreshUpgrade]);

  useEffect(() => {
    if (!selectedProfile) return;
    let cancelled = false;
    void readJson<Preflight>(`${API_URL}/api/runtime/profiles/${encodeURIComponent(selectedProfile)}/preflight`)
      .then((result) => { if (!cancelled) setPreflight(result); })
      .catch((error: unknown) => { if (!cancelled) setNotice(error instanceof Error ? error.message : "Profile preflight failed."); });
    return () => { cancelled = true; };
  }, [selectedProfile]);

  const selected = profiles.find((profile) => profile.profile_id === selectedProfile);

  async function previewTerminal() {
    setBusy(true);
    setNotice("");
    try {
      setTerminalResult(await readJson<TerminalResult>(`${API_URL}/api/terminal/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: terminalCommand }),
      }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Terminal preview failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="control-center">
      <div className="control-center-heading">
        <div><span className="eyebrow">OPERATIONS</span><h3>Control Center</h3></div>
        <span className="control-lock">READ-ONLY</span>
      </div>
      <p className="control-copy">Profiles, preflight, terminal classification, and upgrade inventory stay local and mutation-free.</p>

      <label className="control-label" htmlFor="runtime-profile">Runtime profile</label>
      <select id="runtime-profile" className="control-select" value={selectedProfile} onChange={(event) => setSelectedProfile(event.target.value)}>
        {profiles.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.label}</option>)}
      </select>
      {selected && (
        <div className="profile-card">
          <div className="profile-card-title"><strong>{selected.model}</strong><span className={stateClass(selected.state)}>{selected.state}</span></div>
          <small>{selected.mode} · {selected.provider}</small>
          {selected.lanes.map((lane) => <div className="profile-lane" key={lane.lane_id}><span>{lane.label}</span><small>{lane.endpoint ?? "no active endpoint"}</small></div>)}
          <p>{selected.notes}</p>
          {preflight && <div className="preflight-result"><span className={stateClass(preflight.status)}>{preflight.status}</span><small>mutation: {preflight.mutation ?? "none"}</small></div>}
        </div>
      )}

      {selected?.provider === "ollama" && ollamaInventory && (
        <div className="ollama-inventory">
          <div className="mini-section-title">OLLAMA INVENTORY · {ollamaInventory.status}</div>
          <small>Priority exact local IDs · default: {ollamaInventory.default_model ?? "auto"}</small>
          {ollamaInventory.models.map((model) => (
            <div className="upgrade-row" key={model.name}>
              <span title={model.name}>{model.name}</span>
              <span className={stateClass(model.openai_advertised ? "ready" : "not-ready")}>{model.openai_advertised ? "OpenAI API" : "tags only"}</span>
            </div>
          ))}
        </div>
      )}

      <div className="panel-divider" />
      <div className="mini-section-title">TERMINAL PREVIEW</div>
      <div className="terminal-preview-row"><input className="control-input" value={terminalCommand} onChange={(event) => setTerminalCommand(event.target.value)} aria-label="Terminal command preview" /><button className="toolbar-button" type="button" disabled={busy} onClick={() => void previewTerminal()}>Preview</button></div>
      {terminalResult && <div className="terminal-preview-result"><span className={stateClass(terminalResult.status)}>{terminalResult.status}</span><small>{terminalResult.reason}</small></div>}

      <div className="panel-divider" />
      <div className="mini-section-title">UPGRADE CENTER</div>
      {inventory?.items.map((item) => <div className="upgrade-row" key={item.item_id}><span>{item.label}</span><span className={stateClass(item.state)}>{item.state}</span></div>)}
      {upgradePreflight && <div className="upgrade-preflight"><span className={stateClass(upgradePreflight.status)}>{upgradePreflight.status}</span><small>rollback: {upgradePreflight.rollback.available ? "available" : "not armed"}</small></div>}
      <button className="button button-quiet full-width control-refresh" type="button" onClick={() => void refreshUpgrade()}>Refresh inventory / preflight</button>
      {notice && <div className="control-notice">{notice}</div>}
    </section>
  );
}
