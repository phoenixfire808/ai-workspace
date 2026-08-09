"use client";

import { useCallback, useEffect, useState } from "react";
import { EXACT_WORKSPACE_MODEL } from "./nodes/types";

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
  approved_model?: string;
  allowed_models?: string[];
  models: Array<{ name: string; size?: number | null; openai_advertised?: boolean }>;
};

type WorkspaceModelSetting = {
  provider: "ollama";
  model: string;
  hardware_profile_id: string;
  fallback_policy: "explicit_only";
  persisted: boolean;
  mutation: string;
};

type EndpointProfile = { id: string; name: string; provider_kind: string; base_url: string; credential_alias: string; credential_configured: boolean; settings: Record<string, unknown>; enabled: boolean; managed: boolean };
type EndpointPreflight = { ready: boolean; reason: string; selected_model?: string; exact_model_available?: boolean; credential_configured?: boolean; fallback_policy?: string; mutation?: string };
type GpuDevice = { index: number; uuid: string; name: string; memory_total_mb: number; memory_free_mb: number; compute_capability: string };
type GpuProcess = { pid: number; gpu_uuid: string; process_name: string; used_memory_mb: number };
type HardwareProfile = { id: string; name: string; mode: string; device_ids: string[]; settings: Record<string, unknown>; ready: boolean; missing_devices: string[]; devices: GpuDevice[] };

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
  const [workspaceModel, setWorkspaceModel] = useState<WorkspaceModelSetting | null>(null);
  const [workspaceModelDraft, setWorkspaceModelDraft] = useState("");
  const [workspaceHardwareDraft, setWorkspaceHardwareDraft] = useState("auto");
  const [endpoints, setEndpoints] = useState<EndpointProfile[]>([]);
  const [selectedEndpoint, setSelectedEndpoint] = useState("");
  const [endpointModel, setEndpointModel] = useState("");
  const [endpointAlias, setEndpointAlias] = useState("");
  const [endpointEnabled, setEndpointEnabled] = useState(false);
  const [endpointPreflight, setEndpointPreflight] = useState<EndpointPreflight | null>(null);
  const [gpus, setGpus] = useState<GpuDevice[]>([]);
  const [gpuProcesses, setGpuProcesses] = useState<GpuProcess[]>([]);
  const [hardwareProfiles, setHardwareProfiles] = useState<HardwareProfile[]>([]);
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
      readJson<WorkspaceModelSetting>(`${API_URL}/api/settings/model`),
      readJson<{ profiles: EndpointProfile[] }>(`${API_URL}/api/model-endpoints`),
      readJson<{ devices: GpuDevice[]; processes: GpuProcess[] }>(`${API_URL}/api/hardware/gpus`),
      readJson<{ profiles: HardwareProfile[] }>(`${API_URL}/api/hardware/profiles`),
    ]).then(([runtime, _upgrade, ollama, modelSetting, endpointInventory, gpuInventory, hardwareInventory]) => {
      if (cancelled) return;
      setProfiles(runtime.profiles);
      setSelectedProfile(runtime.profiles[0]?.profile_id ?? "");
      setOllamaInventory(ollama);
      setWorkspaceModel(modelSetting);
      setWorkspaceModelDraft(modelSetting.model);
      setWorkspaceHardwareDraft(modelSetting.hardware_profile_id);
      setEndpoints(endpointInventory.profiles);
      setSelectedEndpoint(endpointInventory.profiles.find((item) => item.provider_kind === "ollama")?.id ?? endpointInventory.profiles[0]?.id ?? "");
      setGpus(gpuInventory.devices);
      setGpuProcesses(gpuInventory.processes ?? []);
      setHardwareProfiles(hardwareInventory.profiles);
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
  const endpoint = endpoints.find((item) => item.id === selectedEndpoint);

  useEffect(() => {
    if (!endpoint) return;
    setEndpointModel(String(endpoint.settings.model ?? ""));
    setEndpointAlias(endpoint.credential_alias);
    setEndpointEnabled(endpoint.enabled);
    setEndpointPreflight(null);
  }, [endpoint]);

  async function saveWorkspaceModel() {
    setBusy(true); setNotice("");
    try {
      const saved = await readJson<WorkspaceModelSetting>(`${API_URL}/api/settings/model`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "ollama", model: workspaceModelDraft, hardware_profile_id: workspaceHardwareDraft, fallback_policy: "explicit_only" }),
      });
      setWorkspaceModel(saved);
      setNotice("Global Refactor Workflow Studio model saved. Chat, Planner, Research, and Coder now resolve this exact model unless explicitly overridden.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Workspace model save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveEndpoint() {
    if (!endpoint || endpoint.provider_kind !== "openrouter") return;
    setBusy(true); setNotice("");
    try {
      const saved = await readJson<EndpointProfile>(`${API_URL}/api/model-endpoints`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...endpoint, credential_alias: endpointAlias, enabled: endpointEnabled, settings: { ...endpoint.settings, model: endpointModel, fallback_policy: "explicit_only" } }) });
      setEndpoints((current) => current.map((item) => item.id === saved.id ? saved : item));
      setNotice("Endpoint profile saved locally. No provider request was sent.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Endpoint profile save failed."); }
    finally { setBusy(false); }
  }

  async function preflightEndpoint() {
    if (!endpoint) return;
    setBusy(true); setNotice("");
    try { setEndpointPreflight(await readJson<EndpointPreflight>(`${API_URL}/api/model-endpoints/${encodeURIComponent(endpoint.id)}/preflight`)); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Endpoint preflight failed."); }
    finally { setBusy(false); }
  }

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
        <span className="control-lock">LOCAL SETTINGS</span>
      </div>
      <p className="control-copy">Choose one persistent local model; runtime inventory, terminal classification, and upgrade checks remain bounded.</p>

      <div className="mini-section-title">WORKSPACE MODEL · GLOBAL DEFAULT</div>
      <label className="control-label" htmlFor="workspace-model">Installed Ollama model</label>
      <select id="workspace-model" className="control-select" value={workspaceModelDraft} onChange={(event) => setWorkspaceModelDraft(event.target.value)}>
        {(ollamaInventory?.models ?? []).map((model) => <option key={model.name} value={model.name}>{model.name}</option>)}
      </select>
      <label className="control-label" htmlFor="workspace-hardware">Hardware profile</label>
      <select id="workspace-hardware" className="control-select" value={workspaceHardwareDraft} onChange={(event) => setWorkspaceHardwareDraft(event.target.value)}>
        {hardwareProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name} · {profile.mode}</option>)}
      </select>
      <div className="profile-card">
        <div className="profile-card-title"><strong>Ollama · exact ID</strong><span className={stateClass(workspaceModel?.persisted ? "ready" : "not-ready")}>{workspaceModel?.persisted ? "saved" : "default"}</span></div>
        <small>Resolution: node → workflow → global · fallback: explicit_only</small>
        <button className="button button-primary full-width" type="button" disabled={busy || !workspaceModelDraft} onClick={() => void saveWorkspaceModel()}>Save global model</button>
      </div>

      <div className="panel-divider" />

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
          <div className="mini-section-title">OLLAMA MODEL · {ollamaInventory.status}</div>
          <small>Exact-model policy · approved: {ollamaInventory.approved_model ?? EXACT_WORKSPACE_MODEL}</small>
          <div className="upgrade-row">
            <span title={ollamaInventory.approved_model ?? EXACT_WORKSPACE_MODEL}>{ollamaInventory.approved_model ?? EXACT_WORKSPACE_MODEL}</span>
            <span className={stateClass(ollamaInventory.models.some((model) => model.name === (ollamaInventory.approved_model ?? EXACT_WORKSPACE_MODEL)) ? "ready" : "not-ready")}>APPROVED ONLY</span>
          </div>
        </div>
      )}

      <div className="panel-divider" />
      <div className="mini-section-title">MODEL ENDPOINT · EXACT LOCAL ONLY</div>
      <select className="control-select" value={selectedEndpoint} onChange={(event) => setSelectedEndpoint(event.target.value)} aria-label="Model endpoint profile">{endpoints.filter((item) => item.provider_kind === "ollama").map((item) => <option key={item.id} value={item.id}>{item.name} · {item.enabled ? "enabled" : "disabled"}</option>)}</select>
      {endpoint && <div className="profile-card">
        <div className="profile-card-title"><strong>{endpoint.provider_kind}</strong><span className={stateClass(endpoint.enabled ? "ready" : "disabled")}>{endpoint.enabled ? "enabled" : "disabled"}</span></div>
        <small>{endpoint.base_url}</small>
        {endpoint.provider_kind === "openrouter" && <>
          <label className="control-label">Exact model ID<input className="control-input" value={endpointModel} onChange={(event) => setEndpointModel(event.target.value)} placeholder="provider/model" /></label>
          <label className="control-label">Credential alias only<input className="control-input" value={endpointAlias} onChange={(event) => setEndpointAlias(event.target.value)} placeholder="env:OPENROUTER_API_KEY or wincred:target" /></label>
          <label className="checkbox-row"><input type="checkbox" checked={endpointEnabled} onChange={(event) => setEndpointEnabled(event.target.checked)} /><span>Enable this exact explicit route</span></label>
          <small>Fallback: explicit_only · raw keys are rejected.</small>
          <button className="button button-quiet full-width" type="button" disabled={busy} onClick={() => void saveEndpoint()}>Save local profile</button>
        </>}
        <button className="button button-quiet full-width" type="button" disabled={busy} onClick={() => void preflightEndpoint()}>Preflight selected endpoint</button>
        {endpointPreflight && <div className="preflight-result"><span className={stateClass(endpointPreflight.ready ? "ready" : "blocked")}>{endpointPreflight.ready ? "ready" : "blocked"}</span><small>{endpointPreflight.reason || "exact model advertised"} · mutation: {endpointPreflight.mutation ?? "none"}</small></div>}
      </div>}

      <div className="panel-divider" />
      <div className="mini-section-title">GPU EVIDENCE · READ ONLY</div>
      {gpus.map((gpu) => <div className="upgrade-row" key={gpu.uuid}><span title={gpu.uuid}>GPU {gpu.index} · {gpu.name}</span><span className={stateClass("ready")}>{gpu.memory_free_mb}/{gpu.memory_total_mb} MiB free</span></div>)}
      {gpuProcesses.map((process) => <div className="profile-lane" key={`${process.gpu_uuid}-${process.pid}`}><span>PID {process.pid} · {process.process_name}</span><small title={process.gpu_uuid}>{process.used_memory_mb} MiB · {process.gpu_uuid.slice(0, 18)}…</small></div>)}
      {hardwareProfiles.map((profile) => <div className="profile-lane" key={profile.id}><span>{profile.name} · {profile.mode}</span><small>{profile.ready ? `${profile.device_ids.length || "auto"} device(s) declared` : `missing ${profile.missing_devices.join(", ")}`}{profile.mode === "multi_gpu" ? ` · split ${String(profile.settings.split_strategy ?? "runtime_auto")} · observed placement not yet proven` : ""}</small></div>)}

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
