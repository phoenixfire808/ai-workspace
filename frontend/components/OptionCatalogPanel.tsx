"use client";

import { useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type OptionEvidence = { tier: string; receipt: string };
type OptionDefinition = {
  option_id: string;
  category: string;
  subgroup: string;
  label: string;
  description: string;
  scope: string[];
  kind: string;
  default: unknown;
  status: string;
  prerequisites: string[];
  effect: string;
  approval_scope?: string | null;
  persistence: string;
  evidence: OptionEvidence[];
  privacy_cost: string;
  rollback: string;
  requires_restart: string;
  inheritance: string;
};
type OptionInventory = {
  mutation: "none";
  phase: number;
  definitions: OptionDefinition[];
  summary: { total: number; ready: number; blocked: number; experimental: number; node_types: number; control_surfaces: number; invalid: number };
  invalid: Array<{ option_id: string; failure_class: string }>;
};

function statusClass(status: string): string {
  return status === "ready" ? "state-ready" : status === "disabled" ? "state-disabled" : "state-blocked";
}

function renderDefault(value: unknown): string {
  if (value === "") return "unset";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export default function OptionCatalogPanel() {
  const [inventory, setInventory] = useState<OptionInventory | null>(null);
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_URL}/api/options`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Option inventory failed (${response.status}).`);
        return response.json() as Promise<OptionInventory>;
      })
      .then((payload) => { if (!cancelled) setInventory(payload); })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Option inventory is offline."); });
    return () => { cancelled = true; };
  }, []);

  const categories = useMemo(() => Array.from(new Set(inventory?.definitions.map((item) => item.category) ?? [])).sort(), [inventory]);
  const definitions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (inventory?.definitions ?? []).filter((item) =>
      (category === "all" || item.category === category)
      && (!needle || `${item.option_id} ${item.label} ${item.description}`.toLowerCase().includes(needle)),
    );
  }, [category, inventory, query]);

  return (
    <section className="option-catalog">
      <div className="control-center-heading">
        <div><span className="eyebrow">PHASE 0</span><h3>Option Catalog</h3></div>
        <span className="control-lock">READ-ONLY</span>
      </div>
      <p className="control-copy">One validated contract for defaults, scope, effects, gates, evidence, restart impact, and rollback. Existing specialized APIs remain authoritative.</p>
      {error && <div className="control-notice">{error}</div>}
      {inventory && <>
        <div className="option-summary">
          <span><strong>{inventory.summary.total}</strong> options</span>
          <span><strong>{inventory.summary.node_types}</strong> nodes</span>
          <span><strong>{inventory.summary.control_surfaces}</strong> surfaces</span>
          <span className={inventory.summary.invalid ? "state-blocked" : "state-ready"}><strong>{inventory.summary.invalid}</strong> invalid</span>
        </div>
        <div className="option-filters">
          <select className="control-select" value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Option category">
            <option value="all">All categories</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <input className="control-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter options" aria-label="Filter options" />
        </div>
        <a className="control-button secondary" href={`${API_URL}/api/options/export.md`} target="_blank" rel="noreferrer">Export detailed Markdown</a>
        <div className="option-list">
          {definitions.map((item) => <details className="option-row" key={item.option_id}>
            <summary><span><strong>{item.label}</strong><code>{item.option_id}</code></span><span className={statusClass(item.status)}>{item.status}</span></summary>
            <p>{item.description}</p>
            <dl>
              <dt>Default</dt><dd><code>{renderDefault(item.default)}</code></dd>
              <dt>Scope</dt><dd>{item.scope.join(" · ")}</dd>
              <dt>Effect</dt><dd><code>{item.effect}</code>{item.approval_scope ? ` · approval: ${item.approval_scope}` : ""}</dd>
              <dt>Persistence</dt><dd>{item.persistence} · inheritance: {item.inheritance}</dd>
              <dt>Restart</dt><dd>{item.requires_restart}</dd>
              <dt>Evidence</dt><dd>{item.evidence.map((entry) => `${entry.tier}: ${entry.receipt}`).join("; ") || "none"}</dd>
              <dt>Prerequisites</dt><dd>{item.prerequisites.join("; ") || "none"}</dd>
              <dt>Privacy</dt><dd>{item.privacy_cost}</dd>
              <dt>Rollback</dt><dd>{item.rollback}</dd>
            </dl>
          </details>)}
        </div>
      </>}
    </section>
  );
}
