"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Landmark,
  ShieldCheck,
  ShieldAlert,
  Check,
  X,
  Users,
  GitPullRequestArrow,
  Boxes,
  AlertTriangle,
  RotateCcw,
  Copy,
  Radar,
  Lock,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Council, IntegrityResult, Proposal, TransactionSummary } from "@/lib/types";

type WatchdogState = Awaited<ReturnType<typeof api.governance.watchdog>>;
import { formatINR, shortHash, formatDateTime } from "@/lib/format";
import { Panel, EmptyState } from "@/components/ui";

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  ALLOWED: { label: "Allowed", color: "var(--success)", bg: "rgba(46,160,67,0.14)" },
  STEP_UP: { label: "Step-up", color: "var(--warning)", bg: "rgba(210,153,34,0.14)" },
  BLOCKED: { label: "Blocked", color: "var(--danger)", bg: "rgba(248,81,73,0.14)" },
};
const PROPOSAL_META: Record<string, { color: string; bg: string }> = {
  PENDING: { color: "var(--accent-cyan)", bg: "rgba(34,211,238,0.12)" },
  APPLIED: { color: "var(--success)", bg: "rgba(46,160,67,0.14)" },
  REJECTED: { color: "var(--danger)", bg: "rgba(248,81,73,0.14)" },
  DIVERGED: { color: "var(--warning)", bg: "rgba(210,153,34,0.16)" },
};

function StatusPill({ status }: { status: string }) {
  const m = STATUS_META[status] ?? STATUS_META.ALLOWED;
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ background: m.bg, color: m.color }}>
      {m.label}
    </span>
  );
}

export default function GovernancePage() {
  const { user } = useAuth();
  const [council, setCouncil] = useState<Council | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [txns, setTxns] = useState<TransactionSummary[]>([]);
  const [busy, setBusy] = useState(false);

  // create-proposal form
  const [selTxn, setSelTxn] = useState("");
  const [proposed, setProposed] = useState("ALLOWED");
  const [reason, setReason] = useState("");

  // integrity panel
  const [intTxn, setIntTxn] = useState("");
  const [integrity, setIntegrity] = useState<IntegrityResult | null>(null);

  // auto-heal watchdog
  const [watchdog, setWatchdog] = useState<WatchdogState | null>(null);

  const isCouncil = useMemo(
    () => !!council?.members.some((m) => m.email === user?.email),
    [council, user],
  );

  const denied = !!user && user.governance_access === false;

  const load = useCallback(async () => {
    try {
      const [c, p, t, w] = await Promise.all([
        api.governance.council(),
        api.governance.proposals(),
        api.transactions({ limit: 60 }),
        api.governance.watchdog(),
      ]);
      setCouncil(c);
      setProposals(p);
      setTxns(t);
      setWatchdog(w);
      setSelTxn((cur) => cur || t[0]?.id || "");
      setIntTxn((cur) => cur || t[0]?.id || "");
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 403)) {
        toast.error(e instanceof ApiError ? e.message : "Failed to load governance data");
      }
    }
  }, []);
  useEffect(() => {
    if (denied) return;
    load();
  }, [load, denied]);

  // Poll the watchdog so auto-heals appear without a refresh.
  useEffect(() => {
    if (denied) return;
    const id = setInterval(async () => {
      try {
        const w = await api.governance.watchdog();
        setWatchdog((prev) => {
          if (prev && w.healed_total > prev.healed_total) {
            const last = w.recent[0];
            toast(`🛡️ Watchdog auto-healed ${last?.transaction_id?.slice(0, 8)} (${last?.from_status} → ${last?.to_status})`);
            load();
          }
          return w;
        });
      } catch {
        /* ignore */
      }
    }, 5000);
    return () => clearInterval(id);
  }, [denied, load]);

  async function runWatchdog() {
    try {
      const r = await api.governance.watchdogScan();
      toast(r.healed.length ? `🛡️ Auto-healed ${r.healed.length} tampered record(s)` : `✓ Scanned ${r.checked} — all intact`);
      await load();
      if (integrity) await checkIntegrity();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Scan failed");
    }
  }

  async function createProposal() {
    setBusy(true);
    try {
      await api.governance.createProposal({ transaction_id: selTxn, proposed_status: proposed, reason });
      setReason("");
      toast.success("Proposal opened — needs unanimous council approval");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not create proposal");
    } finally {
      setBusy(false);
    }
  }

  async function vote(id: string, v: "APPROVE" | "REJECT") {
    try {
      const p = await api.governance.vote(id, v);
      const msg =
        p.status === "APPLIED" ? "✅ Unanimous — override applied & sealed on-chain"
        : p.status === "REJECTED" ? "🚫 Rejected — change discarded"
        : p.status === "DIVERGED" ? "⚠️ Divergence detected — change discarded"
        : `Vote recorded (${p.approvals}/${p.required_approvals})`;
      toast(msg);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Vote failed");
    }
  }

  async function checkIntegrity() {
    try {
      const r = await api.governance.integrity(intTxn);
      setIntegrity(r);
      toast(r.tampered ? "⚠️ Tampering detected!" : "✓ Record matches the blockchain");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Integrity check failed");
    }
  }

  async function tamper(newStatus: string) {
    try {
      await api.governance.simulateTamper(intTxn, newStatus);
      toast("🕵️ Rogue edit applied directly to the DB (no consensus, no chain)");
      await checkIntegrity();
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Tamper failed");
    }
  }

  async function rollback() {
    try {
      const r = await api.governance.rollback(intTxn);
      toast.success(`⛓️ Restored from blockchain: ${r.before.status} → ${r.after.status}`);
      await checkIntegrity();
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Rollback failed");
    }
  }

  if (denied) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full" style={{ background: "rgba(248,81,73,0.12)" }}>
          <Lock className="h-7 w-7 text-[var(--danger)]" />
        </div>
        <h1 className="text-lg font-bold">Governance is restricted</h1>
        <p className="mt-1 max-w-md text-sm text-[var(--text-muted)]">
          This area is limited to the 4-member governance council and the main admin. Your account doesn’t have
          governance access.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-bold">
          <Landmark className="h-5 w-5 text-[var(--accent)]" /> Admin Governance
          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ background: "rgba(34,211,238,0.15)", color: "var(--accent-cyan)" }}>
            4-OF-4 CONSENSUS
          </span>
        </h1>
        <p className="text-sm text-[var(--text-muted)]">
          Reversing a fraud decision requires <b>unanimous approval</b> from the 4-admin council and is sealed on-chain.
          No single admin — even a compromised one — can act alone.
        </p>
      </header>

      {/* council roster */}
      <Panel
        title="Governance council"
        action={
          isCouncil ? (
            <span className="flex items-center gap-1 text-xs text-[var(--success)]">
              <ShieldCheck className="h-3.5 w-3.5" /> You are a council member
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-[var(--text-dim)]">
              <ShieldAlert className="h-3.5 w-3.5" /> View-only (not on council)
            </span>
          )
        }
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {council?.members.map((m) => {
            const me = m.email === user?.email;
            return (
              <div key={m.id} className="rounded-lg border p-2.5" style={{ borderColor: me ? "var(--accent)" : "var(--border)", background: "var(--surface-2)" }}>
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: "var(--accent)" }}>
                    {m.name[0]}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold">{m.name}{me && " (you)"}</p>
                    <p className="truncate text-[10px] text-[var(--text-dim)]">{m.email}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] p-2.5 text-xs text-[var(--text-muted)]" style={{ background: "var(--bg-elevated)" }}>
          <Users className="h-3.5 w-3.5 text-[var(--accent-cyan)]" />
          To demo unanimity, log in as each council member.
          <span className="font-mono text-[var(--text)]">password: {council?.demo_password}</span>
          <button
            onClick={() => { navigator.clipboard?.writeText(council?.demo_password ?? ""); toast("Password copied"); }}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[var(--text-dim)] hover:text-[var(--text)]"
          >
            <Copy className="h-3 w-3" /> copy
          </button>
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* propose */}
        <Panel title="Propose a decision override">
          {!isCouncil && (
            <p className="mb-3 rounded-lg p-2 text-xs text-[var(--warning)]" style={{ background: "rgba(210,153,34,0.1)" }}>
              Only council admins can propose. Log in as a council member to try this.
            </p>
          )}
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">Transaction</label>
              <select className="field" value={selTxn} onChange={(e) => setSelTxn(e.target.value)}>
                {txns.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.status} · {formatINR(t.amount_inr)} · {t.from_vpa} → {t.to_vpa} · risk {t.risk_score}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">New decision</label>
                <select className="field" value={proposed} onChange={(e) => setProposed(e.target.value)}>
                  <option value="ALLOWED">ALLOWED (unblock)</option>
                  <option value="STEP_UP">STEP_UP</option>
                  <option value="BLOCKED">BLOCKED</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Reason</label>
                <input className="field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Justification…" />
              </div>
            </div>
            <button className="btn btn-primary w-full" disabled={busy || !isCouncil || !selTxn || reason.trim().length < 3} onClick={createProposal}>
              <GitPullRequestArrow className="h-4 w-4" /> Open proposal
            </button>
          </div>
        </Panel>

        {/* integrity / immutability demo */}
        <Panel
          title="Integrity & immutability"
          action={<span className="text-[11px] text-[var(--text-dim)]">chain = source of truth</span>}
        >
          <div className="space-y-3">
            <select className="field" value={intTxn} onChange={(e) => { setIntTxn(e.target.value); setIntegrity(null); }}>
              {txns.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.status} · {formatINR(t.amount_inr)} · {t.from_vpa} → {t.to_vpa}
                </option>
              ))}
            </select>

            <div className="flex flex-wrap gap-2">
              <button className="btn btn-ghost text-xs" onClick={checkIntegrity}>
                <ShieldCheck className="h-3.5 w-3.5" /> Verify integrity
              </button>
              <button className="btn btn-ghost text-xs" onClick={() => tamper("ALLOWED")} title="Rogue direct DB edit">
                <AlertTriangle className="h-3.5 w-3.5 text-[var(--danger)]" /> Simulate rogue tamper
              </button>
              <button className="btn btn-ghost text-xs" onClick={rollback}>
                <RotateCcw className="h-3.5 w-3.5 text-[var(--accent-cyan)]" /> Restore from chain
              </button>
            </div>

            {integrity && (
              <div
                className="animate-fade-up rounded-lg p-3 text-xs"
                style={{
                  background: integrity.tampered ? "rgba(248,81,73,0.1)" : "rgba(46,160,67,0.1)",
                  border: `1px solid ${integrity.tampered ? "var(--danger)" : "var(--success)"}`,
                }}
              >
                <p className="mb-1 font-semibold" style={{ color: integrity.tampered ? "var(--danger)" : "var(--success)" }}>
                  {integrity.tampered ? "⚠️ Tampering detected — DB differs from blockchain" : "✓ Verified — DB matches blockchain"}
                </p>
                <div className="flex gap-6 text-[var(--text-muted)]">
                  <span>Live DB: <StatusPill status={integrity.current.status} /></span>
                  <span>On-chain: {integrity.agreed ? <StatusPill status={integrity.agreed.status} /> : "—"}</span>
                </div>
                {integrity.tampered && (
                  <p className="mt-1.5 text-[11px] text-[var(--text-dim)]">
                    Click <b>Restore from chain</b> — the blockchain&apos;s immutable record overrides the rogue edit.
                  </p>
                )}
              </div>
            )}
            <p className="text-[11px] text-[var(--text-dim)]">
              &quot;Simulate rogue tamper&quot; writes a decision directly to the database, bypassing consensus and the chain —
              exactly the attack the council defends against. The verify step catches it; restore repairs it from the immutable ledger.
            </p>
          </div>
        </Panel>
      </div>

      {/* auto-heal watchdog */}
      <Panel
        title="Automatic integrity watchdog"
        action={
          <span className="flex items-center gap-1.5 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" style={{ background: watchdog?.enabled ? "var(--success)" : "var(--text-dim)" }} />
              <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: watchdog?.enabled ? "var(--success)" : "var(--text-dim)" }} />
            </span>
            <span style={{ color: watchdog?.enabled ? "var(--success)" : "var(--text-dim)" }}>
              {watchdog?.enabled ? "Active" : "Idle"}
            </span>
          </span>
        }
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <span className="flex items-center gap-1.5 text-[var(--text-muted)]">
            <Radar className="h-3.5 w-3.5 text-[var(--accent-cyan)]" />
            Re-verifies every transaction against the blockchain {watchdog ? `every ${watchdog.interval_seconds}s` : ""} and auto-restores tampering — on its own.
          </span>
          <span className="text-[var(--text-dim)]">Scans: <b className="text-[var(--text)]">{watchdog?.runs ?? 0}</b></span>
          <span className="text-[var(--text-dim)]">Checked: <b className="text-[var(--text)]">{watchdog?.checked ?? 0}</b></span>
          <span className="text-[var(--text-dim)]">Auto-healed: <b style={{ color: (watchdog?.healed_total ?? 0) > 0 ? "var(--warning)" : "var(--text)" }}>{watchdog?.healed_total ?? 0}</b></span>
          <button onClick={runWatchdog} className="btn btn-ghost ml-auto px-2.5 py-1 text-xs">
            <Radar className="h-3.5 w-3.5" /> Run scan now
          </button>
        </div>
        {watchdog && watchdog.recent.length > 0 && (
          <div className="mt-3 space-y-1 rounded-lg p-2 text-[11px] font-mono" style={{ background: "var(--bg-elevated)" }}>
            {watchdog.recent.slice(0, 5).map((e, i) => (
              <div key={i} className="flex items-center justify-between gap-2 text-[var(--text-muted)]">
                <span className="text-[var(--warning)]">⛓ auto-healed</span>
                <span className="flex-1 truncate">{e.transaction_id.slice(0, 8)}…</span>
                <span>{e.from_status} → {e.to_status}</span>
                <span className="text-[var(--accent-cyan)]">#{e.block_index}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* proposals */}
      <Panel title={`Proposals (${proposals.length})`}>
        {proposals.length === 0 ? (
          <EmptyState title="No proposals yet" hint="Open one above to start a consensus vote." />
        ) : (
          <div className="space-y-3">
            {proposals.map((p) => {
              const pm = PROPOSAL_META[p.status];
              const iVoted = p.votes?.some((v) => v.admin_id === user?.id);
              const canVote = isCouncil && p.status === "PENDING" && !iVoted;
              return (
                <div key={p.id} className="rounded-xl border border-[var(--border)] p-3" style={{ background: "var(--surface-2)" }}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-sm">
                      <StatusPill status={p.current_status} />
                      <span className="text-[var(--text-dim)]">→</span>
                      <StatusPill status={p.proposed_status} />
                      {p.txn && (
                        <span className="text-xs text-[var(--text-muted)]">
                          {formatINR(p.txn.amount_inr)} · {p.txn.from_vpa} → {p.txn.to_vpa}
                        </span>
                      )}
                    </div>
                    <span className="rounded px-2 py-0.5 text-[10px] font-bold" style={{ background: pm.bg, color: pm.color }}>
                      {p.status}
                    </span>
                  </div>

                  <p className="mt-1.5 text-xs text-[var(--text-muted)]">“{p.reason}”</p>

                  {/* consensus progress */}
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex gap-1">
                      {Array.from({ length: p.required_approvals }).map((_, i) => (
                        <span
                          key={i}
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ background: i < p.approvals ? "var(--success)" : p.rejects > 0 && i >= p.approvals ? "var(--danger)" : "var(--surface)", border: "1px solid var(--border-strong)" }}
                        />
                      ))}
                    </div>
                    <span className="text-[11px] text-[var(--text-dim)]">
                      {p.approvals}/{p.required_approvals} approvals{p.rejects > 0 && ` · ${p.rejects} reject`}
                    </span>
                    {p.diverged && <span className="text-[11px] text-[var(--warning)]">· divergence flagged</span>}
                    {p.block_index != null && (
                      <span className="ml-auto flex items-center gap-1 text-[11px] text-[var(--accent-cyan)]">
                        <Boxes className="h-3 w-3" /> #{p.block_index} · {shortHash(p.block_hash)}
                      </span>
                    )}
                  </div>

                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-[10px] text-[var(--text-dim)]">{formatDateTime(p.created_at)}</span>
                    {canVote ? (
                      <div className="flex gap-2">
                        <button onClick={() => vote(p.id, "APPROVE")} className="btn btn-ghost px-2.5 py-1 text-xs" style={{ color: "var(--success)" }}>
                          <Check className="h-3.5 w-3.5" /> Approve
                        </button>
                        <button onClick={() => vote(p.id, "REJECT")} className="btn btn-ghost px-2.5 py-1 text-xs" style={{ color: "var(--danger)" }}>
                          <X className="h-3.5 w-3.5" /> Reject
                        </button>
                      </div>
                    ) : (
                      p.status === "PENDING" && (
                        <span className="text-[11px] text-[var(--text-dim)]">
                          {iVoted ? "You voted — awaiting other admins" : "Log in as a council admin to vote"}
                        </span>
                      )
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
