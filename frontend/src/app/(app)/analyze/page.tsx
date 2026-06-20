"use client";

import { useState } from "react";
import { Boxes, Cpu, Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { getDeviceId } from "@/lib/auth";
import type { AnalyzeResult } from "@/lib/types";
import { formatINR, shortHash, tierColor } from "@/lib/format";
import { EmptyState, Panel, TierBadge } from "@/components/ui";
import RiskGauge from "@/components/RiskGauge";

interface FormState {
  to_vpa: string;
  amount_inr: number;
  txn_type: string;
  device_id: string;
  location_lat: number;
  location_lon: number;
}

const PRESETS: Record<string, Partial<FormState> & { label: string }> = {
  normal: {
    label: "Normal payment",
    to_vpa: "kirana@okaxis",
    amount_inr: 850,
    txn_type: "P2M",
    device_id: getDeviceIdSafe(),
    location_lat: 19.076,
    location_lon: 72.8777,
  },
  suspicious: {
    label: "Suspicious",
    to_vpa: "newpayee@paytm",
    amount_inr: 48000,
    txn_type: "P2P",
    device_id: "device-unknown-42",
    location_lat: 28.6139,
    location_lon: 77.209,
  },
  fraud: {
    label: "Likely fraud",
    to_vpa: "scammer@ybl",
    amount_inr: 320000,
    txn_type: "P2M",
    device_id: "device-stolen-99",
    location_lat: 13.0827,
    location_lon: 80.2707,
  },
};

function getDeviceIdSafe() {
  try {
    return getDeviceId();
  } catch {
    return "web-default";
  }
}

export default function AnalyzePage() {
  const [form, setForm] = useState<FormState>({
    to_vpa: "merchant@okhdfc",
    amount_inr: 1500,
    txn_type: "P2P",
    device_id: getDeviceIdSafe(),
    location_lat: 19.076,
    location_lon: 72.8777,
  });
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyPreset(key: keyof typeof PRESETS) {
    const p = PRESETS[key];
    setForm((f) => ({ ...f, ...p } as FormState));
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.analyze(form));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Transaction Analysis</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Submit a UPI transaction for real-time ML + blockchain risk assessment
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Transaction details">
          <div className="mb-4 flex flex-wrap gap-2">
            {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((k) => (
              <button key={k} type="button" className="btn btn-ghost text-xs" onClick={() => applyPreset(k)}>
                {PRESETS[k].label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">Beneficiary VPA</label>
              <input
                className="field"
                value={form.to_vpa}
                onChange={(e) => update("to_vpa", e.target.value)}
                placeholder="payee@bank"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Amount (₹)</label>
                <input
                  className="field"
                  type="number"
                  min={1}
                  value={form.amount_inr}
                  onChange={(e) => update("amount_inr", Number(e.target.value))}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Type</label>
                <select
                  className="field"
                  value={form.txn_type}
                  onChange={(e) => update("txn_type", e.target.value)}
                >
                  <option value="P2P">P2P</option>
                  <option value="P2M">P2M</option>
                  <option value="BILL_PAY">BILL_PAY</option>
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">Device ID</label>
              <input
                className="field"
                value={form.device_id}
                onChange={(e) => update("device_id", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Latitude</label>
                <input
                  className="field"
                  type="number"
                  step="any"
                  value={form.location_lat}
                  onChange={(e) => update("location_lat", Number(e.target.value))}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Longitude</label>
                <input
                  className="field"
                  type="number"
                  step="any"
                  value={form.location_lon}
                  onChange={(e) => update("location_lon", Number(e.target.value))}
                />
              </div>
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button className="btn btn-primary w-full" disabled={busy}>
              <Zap className="h-4 w-4" />
              {busy ? "Analyzing…" : "Analyze transaction"}
            </button>
          </form>
        </Panel>

        <Panel title="Risk assessment">
          {!result ? (
            <EmptyState title="No assessment yet" hint="Submit a transaction or pick a preset scenario." />
          ) : (
            <div className="space-y-5 animate-fade-up">
              <div className="flex flex-col items-center">
                <RiskGauge score={result.risk_score} tier={result.risk_tier} />
                <div className="mt-2 flex items-center gap-3">
                  <TierBadge tier={result.risk_tier} />
                  <span className="text-xs text-[var(--text-dim)]">
                    ML confidence {(result.ml_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <div
                className="rounded-lg p-3 text-center text-sm font-medium"
                style={{ background: "var(--surface-2)", color: tierColor(result.risk_tier) }}
              >
                {result.recommended_action}
              </div>

              <div>
                <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[var(--text-muted)]">
                  <Cpu className="h-3.5 w-3.5" /> Top risk drivers
                </p>
                <div className="space-y-1.5">
                  {result.feature_contributions.map((f) => (
                    <div key={f.feature} className="flex items-center gap-2">
                      <span className="w-36 truncate text-[11px] text-[var(--text-dim)]">
                        {f.feature}
                      </span>
                      <div className="h-1.5 flex-1 rounded-full bg-[var(--surface-2)]">
                        <div
                          className="h-full rounded-full bg-[var(--accent)]"
                          style={{ width: `${Math.min(f.importance * 100, 100)}%` }}
                        />
                      </div>
                      <span className="w-10 text-right text-[11px] text-[var(--text-muted)]">
                        {f.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel-2 flex items-center justify-between p-3 text-xs">
                <span className="flex items-center gap-1.5 text-[var(--text-muted)]">
                  <Boxes className="h-3.5 w-3.5 text-[var(--accent-cyan)]" /> Logged to blockchain
                </span>
                <span className="font-mono text-[var(--accent-cyan)]">
                  #{result.block_index} · {shortHash(result.block_hash)}
                </span>
              </div>
              <p className="text-center text-[11px] text-[var(--text-dim)]">
                {formatINR(result.amount_inr)} → {result.to_vpa} · fraud prob{" "}
                {(result.ml_fraud_prob * 100).toFixed(1)}% · anomaly{" "}
                {(result.anomaly_score * 100).toFixed(0)}%
              </p>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
