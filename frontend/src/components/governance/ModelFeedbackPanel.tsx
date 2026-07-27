"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { BrainCircuit, RefreshCw, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { FeedbackSummary, ModelScores } from "@/lib/types";
import { Panel, EmptyState } from "@/components/ui";

function pct(n?: number) {
  return n == null ? "—" : `${(n * 100).toFixed(1)}%`;
}

function Scores({ m }: { m: ModelScores | null }) {
  if (!m) return <span className="text-[var(--text-dim)]">n/a</span>;
  return (
    <span className="font-mono text-[11px]">
      AUC {pct(m.auc_roc)} · recall {pct(m.recall)} · precision {pct(m.precision)}
    </span>
  );
}

/**
 * Governance-only "Model Feedback" panel: shows approved corrections waiting to be
 * folded in, retrains a versioned candidate (never auto-promoted), and lets an
 * admin promote it — with the regression guard blocking a worse candidate unless
 * explicitly overridden.
 */
export default function ModelFeedbackPanel() {
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setSummary(await api.governance.feedbackSummary());
    } catch {
      /* surfaced via empty state */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a retrain is running.
  const running = summary?.retrain_status.state === "running";
  useEffect(() => {
    if (!running) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [running, load]);

  async function retrain() {
    setBusy(true);
    try {
      await api.governance.feedbackRetrain();
      toast("Retrain scheduled — training a candidate model…");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Couldn’t start retrain");
    } finally {
      setBusy(false);
    }
  }

  async function promote(version: number, force: boolean) {
    if (force && !confirm("This candidate regresses vs the live model. Promote anyway?")) return;
    setBusy(true);
    try {
      const res = await api.governance.feedbackPromote(version, force);
      toast(`✓ Promoted model v${res.promoted_version} · ${res.consumed} correction(s) consumed`);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Promotion failed");
    } finally {
      setBusy(false);
    }
  }

  const pending = summary?.unconsumed_corrections ?? 0;
  const canRetrain = pending >= (summary?.min_examples ?? 1) && !running && !busy;

  return (
    <Panel
      title="Model feedback loop"
      action={
        <button onClick={retrain} disabled={!canRetrain} className="btn btn-primary text-xs">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {running ? "Training…" : "Retrain"}
        </button>
      }
    >
      {!summary ? (
        <EmptyState title="Loading feedback state…" />
      ) : (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="flex items-center gap-1.5 text-[var(--text-muted)]">
              <BrainCircuit className="h-4 w-4 text-[var(--accent)]" />
              Pending corrections:{" "}
              <b className="text-[var(--text)]">{pending}</b>
            </span>
            <span className="text-[var(--text-muted)]">
              Live model: <Scores m={summary.live_metrics} />
            </span>
          </div>

          <p className="text-xs text-[var(--text-dim)]">
            Approved council overrides become labeled training data (using the exact
            feature vector scored at the time). Retraining produces a{" "}
            <b>separately versioned candidate</b> — it is never auto-promoted.
          </p>

          {summary.retrain_status.state === "error" && (
            <p className="text-xs text-[var(--danger)]">
              Last retrain failed: {summary.retrain_status.error}
            </p>
          )}

          <div>
            <p className="mb-2 text-xs font-semibold text-[var(--text-muted)]">Candidates</p>
            {summary.candidates.length === 0 ? (
              <p className="text-xs text-[var(--text-dim)]">
                No candidates yet. Approve a correction, then retrain.
              </p>
            ) : (
              <div className="space-y-2">
                {summary.candidates.map((c) => {
                  const blocked = !c.regression.ok;
                  return (
                    <div key={c.version} className="panel-2 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold">
                            Candidate v{c.version}
                            <span className="ml-2 text-[10px] font-normal text-[var(--text-dim)]">
                              {c.n_corrections} correction(s)
                            </span>
                          </p>
                          <p className="mt-0.5 text-[var(--text-muted)]">
                            <Scores m={c.metrics} />
                          </p>
                        </div>
                        {blocked ? (
                          <button
                            onClick={() => promote(c.version, true)}
                            disabled={busy}
                            className="btn btn-ghost text-xs"
                            title={c.regression.reasons.join("; ")}
                            style={{ borderColor: "var(--warning)", color: "var(--warning)" }}
                          >
                            <AlertTriangle className="h-3.5 w-3.5" /> Promote anyway
                          </button>
                        ) : (
                          <button
                            onClick={() => promote(c.version, false)}
                            disabled={busy}
                            className="btn btn-primary text-xs"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" /> Promote
                          </button>
                        )}
                      </div>
                      {blocked && (
                        <p className="mt-1.5 flex items-center gap-1 text-[11px] text-[var(--warning)]">
                          <AlertTriangle className="h-3 w-3" />
                          Regression guard: {c.regression.reasons.join("; ")}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
