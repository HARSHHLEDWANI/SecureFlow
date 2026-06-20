"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  PlayCircle,
  RotateCcw,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { UpiDemoUser, UpiPayResult, UpiScenario } from "@/lib/types";
import { formatINR, shortHash, formatDateTime } from "@/lib/format";
import { DECISION_META } from "@/lib/labFormat";
import { Panel, EmptyState } from "@/components/ui";
import PhoneFrame, { type PayForm } from "@/components/lab/PhoneFrame";
import PipelineVisualizer from "@/components/lab/PipelineVisualizer";
import ScenarioPanel from "@/components/lab/ScenarioPanel";

type Tab = "manual" | "scenarios";

const GUIDED_STEPS: { scenario: string; blurb: string }[] = [
  { scenario: "normal", blurb: "A normal payment within the user's usual pattern — flows straight through." },
  { scenario: "normal", blurb: "Another routine payment. Low-risk traffic is never slowed down." },
  { scenario: "high_amount", blurb: "Now an unusual high amount — SecureFlow raises a step-up auth challenge." },
  { scenario: "midnight_anomaly", blurb: "A 3 AM payment when this user never transacts at night — flagged." },
  { scenario: "impossible_travel", blurb: "Kolkata, 5 minutes after Pune, new device, 2 AM — physically impossible. Blocked." },
  { scenario: "account_takeover", blurb: "Every red flag at once: account takeover. Hard blocked, fraud team alerted." },
  { scenario: "rapid_fire", blurb: "A rapid-fire cash-out. Watch velocity detection escalate APPROVED → BLOCKED." },
];

export default function LabPage() {
  const [users, setUsers] = useState<UpiDemoUser[]>([]);
  const [scenarios, setScenarios] = useState<UpiScenario[]>([]);
  const [senderVpa, setSenderVpa] = useState<string>("");
  const [tab, setTab] = useState<Tab>("scenarios");
  const [form, setForm] = useState<PayForm>({
    receiver_vpa: "kirana@okaxis",
    amount_inr: 350,
    txn_type: "P2M",
    note: "",
  });

  const [result, setResult] = useState<UpiPayResult | null>(null);
  const [playKey, setPlayKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [session, setSession] = useState<UpiPayResult[]>([]);
  const [rapidFeed, setRapidFeed] = useState<UpiPayResult[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [guided, setGuided] = useState<{ step: number; blurb: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const guidedAbort = useRef(false);

  const sender = useMemo(() => users.find((u) => u.vpa === senderVpa) ?? null, [users, senderVpa]);

  // ── Load demo data ──────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([api.upi.users(), api.upi.scenarios()]);
      setUsers(u.users);
      setScenarios(s.scenarios);
      setSenderVpa((cur) => cur || u.users[0]?.vpa || "");
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Failed to load the Lab. Is the backend running?");
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  // ── Core actions ────────────────────────────────────────────────────────────
  const record = useCallback((r: UpiPayResult) => {
    setResult(r);
    setPlayKey((k) => k + 1);
    setSession((prev) => [r, ...prev].slice(0, 100));
  }, []);

  async function pay() {
    if (!sender) return;
    setBusy(true);
    setRapidFeed([]);
    try {
      const r = await api.upi.pay({
        sender_vpa: sender.vpa,
        receiver_vpa: form.receiver_vpa,
        amount_inr: form.amount_inr,
        txn_type: form.txn_type,
        note: form.note || null,
        city: sender.home_city,
        device_id: sender.known_device,
      });
      record(r);
      toast(`${DECISION_META[r.decision].emoji} ${r.decision.replace("_", "-")} · risk ${r.risk_score}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Payment failed");
    } finally {
      setBusy(false);
    }
  }

  const runScenario = useCallback(
    async (s: UpiScenario) => {
      setRunningId(s.id);
      setRapidFeed([]);
      // Reflect the scenario in the phone UI for realism.
      setSenderVpa(s.sender);
      if (!s.rapid_fire && s.receiver) {
        setForm({
          receiver_vpa: s.receiver,
          amount_inr: s.amount ?? 0,
          txn_type: s.txn_type ?? "P2P",
          note: s.name,
        });
      }
      try {
        const run = await api.upi.runScenario(s.id);
        if (run.rapid_fire && run.results) {
          // Stream the burst into the feed for drama.
          for (const r of run.results) {
            if (guidedAbort.current) break;
            setRapidFeed((prev) => [...prev, r]);
            setSession((prev) => [r, ...prev].slice(0, 100));
            setResult(r);
            setPlayKey((k) => k + 1);
            await sleep(380);
          }
          const blocked = run.results.filter((r) => r.decision === "BLOCKED").length;
          toast(`⚡ Rapid-fire done · ${blocked}/${run.results.length} blocked`);
        } else if (run.result) {
          record(run.result);
          const ok = run.match ? "✓ matches expected" : "✗ differs from expected";
          toast(`${DECISION_META[run.result.decision].emoji} ${s.name}: ${run.result.decision.replace("_", "-")} (${ok})`);
        }
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : "Scenario failed");
      } finally {
        setRunningId(null);
      }
    },
    [record],
  );

  async function runGuided() {
    setTab("scenarios");
    guidedAbort.current = false;
    for (let i = 0; i < GUIDED_STEPS.length; i++) {
      if (guidedAbort.current) break;
      const step = GUIDED_STEPS[i];
      setGuided({ step: i + 1, blurb: step.blurb });
      const s = scenarios.find((x) => x.id === step.scenario);
      if (s) await runScenario(s);
      await sleep(1400);
    }
    setGuided(null);
  }

  async function resetSession() {
    guidedAbort.current = true;
    try {
      await api.upi.reset();
    } catch {
      /* ignore */
    }
    setSession([]);
    setRapidFeed([]);
    setResult(null);
    setGuided(null);
    await load();
    toast("Session reset — demo data restored");
  }

  // ── Derived stats ───────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const total = session.length;
    const approved = session.filter((r) => r.decision === "APPROVED").length;
    const stepUp = session.filter((r) => r.decision === "STEP_UP").length;
    const blocked = session.filter((r) => r.decision === "BLOCKED").length;
    const avg = total ? Math.round(session.reduce((a, r) => a + r.total_duration_ms, 0) / total) : 0;
    const lastBlock = session.find((r) => r.block_index != null)?.block_index ?? null;
    return { total, approved, stepUp, blocked, avg, lastBlock };
  }, [session]);

  const pct = (n: number) => (stats.total ? ((n / stats.total) * 100).toFixed(0) : "0");

  if (loadError) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">UPI Transaction Lab</h1>
        <div className="rounded-xl border border-[var(--danger)] p-4 text-sm" style={{ background: "rgba(248,81,73,0.08)" }}>
          <p className="font-semibold text-[var(--danger)]">Couldn’t reach the SecureFlow backend.</p>
          <p className="mt-1 text-[var(--text-muted)]">{loadError}</p>
          <button onClick={load} className="btn btn-ghost mt-3">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            UPI Transaction Lab
            <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ background: "rgba(34,211,238,0.15)", color: "var(--accent-cyan)" }}>
              SIMULATOR
            </span>
          </h1>
          <p className="text-sm text-[var(--text-muted)]">
            Live UPI payments routed through SecureFlow’s real fraud-detection pipeline. No real money moves.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={runGuided} disabled={!!guided || busy} className="btn btn-primary">
            <Sparkles className="h-4 w-4" /> Guided Demo
          </button>
          <button onClick={resetSession} className="btn btn-ghost">
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
        </div>
      </header>

      {/* stats bar */}
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-x-5 gap-y-1 rounded-xl border border-[var(--border)] px-4 py-2.5 text-xs backdrop-blur" style={{ background: "rgba(17,26,48,0.85)" }}>
        <Stat icon={<Activity className="h-3.5 w-3.5" />} label="Transactions" value={stats.total} />
        <Stat label="Approved" value={`${stats.approved} (${pct(stats.approved)}%)`} color="var(--success)" />
        <Stat label="Step-up" value={`${stats.stepUp} (${pct(stats.stepUp)}%)`} color="var(--warning)" />
        <Stat label="Blocked" value={`${stats.blocked} (${pct(stats.blocked)}%)`} color="var(--danger)" />
        <Stat label="Avg pipeline" value={`${stats.avg}ms`} />
        <Stat label="Latest block" value={stats.lastBlock != null ? `#${stats.lastBlock}` : "—"} color="var(--accent-cyan)" />
      </div>

      {/* guided banner */}
      {guided && (
        <div className="animate-fade-up flex items-center gap-3 rounded-xl border border-[var(--accent)] p-3 text-sm" style={{ background: "rgba(47,129,247,0.1)" }}>
          <PlayCircle className="h-5 w-5 shrink-0 text-[var(--accent)]" />
          <p>
            <span className="font-semibold">Step {guided.step}/{GUIDED_STEPS.length}:</span> {guided.blurb}
          </p>
        </div>
      )}

      {/* main grid */}
      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        {/* left: phone */}
        <div>
          <PhoneFrame
            users={users}
            sender={sender}
            onSenderChange={setSenderVpa}
            form={form}
            onChange={(p) => setForm((f) => ({ ...f, ...p }))}
            onPay={pay}
            busy={busy}
          />
          {sender && (
            <p className="mt-3 text-center text-[11px] text-[var(--text-dim)]">
              {sender.name} · avg {formatINR(sender.avg_transaction)} · {sender.risk_profile} risk profile · device {sender.known_device}
            </p>
          )}
        </div>

        {/* right: pipeline + scenarios */}
        <div className="space-y-4">
          <Panel
            title="Detection pipeline"
            action={
              <span className="text-[11px] text-[var(--text-dim)]">
                {result ? `${result.total_duration_ms}ms · real timings` : "live"}
              </span>
            }
          >
            {rapidFeed.length > 0 ? (
              <RapidFeed feed={rapidFeed} />
            ) : (
              <PipelineVisualizer result={result} playKey={playKey} />
            )}
          </Panel>

          <Panel
            title="Attack scenarios"
            action={
              <div className="flex gap-1 rounded-lg border border-[var(--border)] p-0.5 text-xs">
                <TabButton active={tab === "scenarios"} onClick={() => setTab("scenarios")}>Scenarios</TabButton>
                <TabButton active={tab === "manual"} onClick={() => setTab("manual")}>How it works</TabButton>
              </div>
            }
          >
            {tab === "scenarios" ? (
              <ScenarioPanel scenarios={scenarios} onRun={runScenario} runningId={runningId} disabled={busy || !!runningId} />
            ) : (
              <div className="space-y-2 text-sm text-[var(--text-muted)]">
                <p>Each payment runs the <b className="text-[var(--text)]">real</b> pipeline: feature engineering → RandomForest + IsolationForest → weighted risk score → blockchain log → decision.</p>
                <p>The engine is deliberately conservative: a single red flag triggers <b className="text-[var(--warning)]">step-up auth</b> (OTP), and only overwhelming evidence is hard-<b className="text-[var(--danger)]">blocked</b> — minimising false positives.</p>
                <p>Use the phone to craft your own payment, or run a preset attack. Everything appears in the Dashboard, Blockchain Explorer and Analytics too.</p>
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* session history */}
      <Panel title={`Session history (${session.length})`}>
        {session.length === 0 ? (
          <EmptyState title="No transactions yet" hint="Make a payment or run a scenario to populate the ledger." />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-left text-xs">
              <thead className="text-[var(--text-dim)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="px-2 py-2 font-medium">Time</th>
                  <th className="px-2 py-2 font-medium">From → To</th>
                  <th className="px-2 py-2 text-right font-medium">Amount</th>
                  <th className="px-2 py-2 text-right font-medium">Risk</th>
                  <th className="px-2 py-2 font-medium">Decision</th>
                  <th className="px-2 py-2 font-medium">Block</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {session.map((r) => {
                  const meta = DECISION_META[r.decision];
                  const open = expanded === r.txn_id;
                  return (
                    <Fragment key={r.txn_id}>
                      <tr
                        onClick={() => setExpanded(open ? null : r.txn_id)}
                        className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--surface-2)]"
                      >
                        <td className="px-2 py-2 text-[var(--text-dim)]">{formatDateTime(r.created_at)}</td>
                        <td className="px-2 py-2">
                          <span className="text-[var(--text-muted)]">{r.sender_vpa}</span>
                          <span className="text-[var(--text-dim)]"> → </span>
                          {r.receiver_vpa}
                        </td>
                        <td className="px-2 py-2 text-right font-medium">{formatINR(r.amount_inr)}</td>
                        <td className="px-2 py-2 text-right font-semibold" style={{ color: meta.color }}>{r.risk_score}</td>
                        <td className="px-2 py-2">
                          <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ background: meta.bg, color: meta.color }}>
                            {meta.emoji} {r.decision.replace("_", "-")}
                          </span>
                        </td>
                        <td className="px-2 py-2 font-mono text-[var(--accent-cyan)]">#{r.block_index}</td>
                        <td className="px-2 py-2 text-[var(--text-dim)]">{open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</td>
                      </tr>
                      {open && (
                        <tr className="border-b border-[var(--border)]">
                          <td colSpan={7} className="bg-[var(--bg-elevated)] px-4 py-3">
                            <Detail r={r} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

// ── Small components ────────────────────────────────────────────────────────────

function Stat({ icon, label, value, color }: { icon?: React.ReactNode; label: string; value: React.ReactNode; color?: string }) {
  return (
    <span className="flex items-center gap-1.5">
      {icon}
      <span className="text-[var(--text-dim)]">{label}:</span>
      <span className="font-semibold" style={{ color: color ?? "var(--text)" }}>{value}</span>
    </span>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-2.5 py-1 ${active ? "text-[var(--text)]" : "text-[var(--text-muted)]"}`}
      style={active ? { background: "var(--surface-2)" } : undefined}
    >
      {children}
    </button>
  );
}

function RapidFeed({ feed }: { feed: UpiPayResult[] }) {
  return (
    <div className="space-y-1.5">
      <p className="mb-2 flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
        <Zap className="h-3.5 w-3.5 text-[var(--warning)]" /> Rapid-fire burst — velocity detection live
      </p>
      <div className="max-h-[360px] space-y-1.5 overflow-y-auto scrollbar-thin rounded-lg p-2 font-mono text-xs" style={{ background: "var(--bg-elevated)" }}>
        {feed.map((r) => {
          const meta = DECISION_META[r.decision];
          return (
            <div key={r.txn_id} className="animate-fade-up flex items-center justify-between gap-2">
              <span className="text-[var(--text-dim)]">#{String(r.sequence).padStart(2, "0")}</span>
              <span className="flex-1 truncate text-[var(--text-muted)]">{r.receiver_vpa}</span>
              <span>{formatINR(r.amount_inr)}</span>
              <span className="w-8 text-right" style={{ color: meta.color }}>{r.risk_score}</span>
              <span className="w-20 text-right font-sans font-semibold" style={{ color: meta.color }}>
                {meta.emoji} {r.decision.replace("_", "-")}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Detail({ r }: { r: UpiPayResult }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div>
        <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-[var(--text-muted)]"><Terminal className="h-3 w-3" /> ML & risk</p>
        <ul className="space-y-0.5 text-[11px] text-[var(--text-muted)]">
          <li>Fraud probability: <b className="text-[var(--text)]">{(r.ml_fraud_prob * 100).toFixed(1)}%</b></li>
          <li>Anomaly score: {(r.anomaly_score * 100).toFixed(0)}%</li>
          <li>ML confidence: {(r.ml_confidence * 100).toFixed(0)}%</li>
          <li>Risk score: <b className="text-[var(--text)]">{r.risk_score}/100</b> ({r.risk_tier})</li>
        </ul>
      </div>
      <div>
        <p className="mb-1 text-[11px] font-semibold text-[var(--text-muted)]">Top risk drivers</p>
        <ul className="space-y-0.5 text-[11px] text-[var(--text-muted)]">
          {r.feature_contributions.slice(0, 5).map((f) => (
            <li key={f.feature} className="flex justify-between gap-2">
              <span className="truncate">{f.feature}</span>
              <span className="text-[var(--text-dim)]">{f.value}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="mb-1 text-[11px] font-semibold text-[var(--text-muted)]">Blockchain proof</p>
        <ul className="space-y-0.5 text-[11px] text-[var(--text-muted)]">
          <li>Block: <span className="font-mono text-[var(--accent-cyan)]">#{r.block_index}</span></li>
          <li>Hash: <span className="font-mono text-[var(--accent-cyan)]">{shortHash(r.block_hash)}</span></li>
          <li>Pipeline: {r.total_duration_ms}ms</li>
          <li>Action: {r.recommended_action}</li>
        </ul>
      </div>
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((res) => setTimeout(res, ms));
}
