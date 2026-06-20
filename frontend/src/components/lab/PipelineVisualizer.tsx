"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Cpu, Boxes, ShieldAlert, Gauge, ScanLine, Flag, Play } from "lucide-react";
import type { PipelineSnapshot, UpiPayResult } from "@/lib/types";
import { DECISION_META, STAGE_LABELS } from "@/lib/labFormat";
import { formatINR, shortHash } from "@/lib/format";

const STAGE_ICONS: Record<string, React.ElementType> = {
  initiated: Play,
  validated: ScanLine,
  features_extracted: Cpu,
  ml_prediction: ShieldAlert,
  risk_scored: Gauge,
  blockchain_logged: Boxes,
  decision: Flag,
};

// Minimum on-screen dwell per stage so the (sub-500ms real) pipeline is watchable.
const MIN_DWELL_MS = 420;

export default function PipelineVisualizer({
  result,
  playKey,
}: {
  result: UpiPayResult | null;
  playKey: number;
}) {
  const snapshot: PipelineSnapshot | null = result?.pipeline ?? null;
  const order = snapshot?.stage_order ?? [];
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    if (!snapshot) return;
    setRevealed(0);
    let i = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const step = () => {
      i += 1;
      setRevealed(i);
      if (i < order.length) timers.push(setTimeout(step, MIN_DWELL_MS));
    };
    timers.push(setTimeout(step, MIN_DWELL_MS));
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playKey]);

  if (!snapshot) {
    return (
      <div className="flex h-full min-h-[320px] flex-col items-center justify-center text-center">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full" style={{ background: "var(--surface-2)" }}>
          <Cpu className="h-6 w-6 text-[var(--text-dim)]" />
        </div>
        <p className="text-sm text-[var(--text-muted)]">Detection pipeline idle</p>
        <p className="mt-1 text-xs text-[var(--text-dim)]">Make a payment to watch it flow through SecureFlow.</p>
      </div>
    );
  }

  const done = revealed >= order.length;

  return (
    <div className="space-y-2.5">
      {order.map((key, idx) => {
        const stage = snapshot.stages[key];
        const Icon = STAGE_ICONS[key] ?? Check;
        const isDone = idx < revealed;
        const isProcessing = idx === revealed && !done;
        const state = isDone ? "done" : isProcessing ? "processing" : "waiting";
        return (
          <div
            key={key}
            className="flex items-center gap-3 rounded-xl border p-3 transition-all duration-300"
            style={{
              borderColor: isDone ? "var(--border-strong)" : "var(--border)",
              background: isProcessing ? "rgba(47,129,247,0.08)" : isDone ? "var(--surface-2)" : "var(--surface)",
              opacity: state === "waiting" ? 0.45 : 1,
              boxShadow: isProcessing ? "0 0 0 1px var(--accent), 0 0 18px rgba(47,129,247,0.25)" : undefined,
            }}
          >
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              style={{ background: isDone ? "rgba(46,160,67,0.16)" : "var(--bg-elevated)" }}
            >
              {isDone ? (
                <Check className="h-4 w-4" style={{ color: "var(--success)" }} />
              ) : isProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
              ) : (
                <Icon className="h-4 w-4 text-[var(--text-dim)]" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{STAGE_LABELS[key] ?? key}</span>
                {isDone && (
                  <span className="font-mono text-[11px] text-[var(--text-dim)]">{stage.duration_ms}ms</span>
                )}
              </div>
              {isDone && <StageDetail stageKey={key} result={result!} />}
            </div>
          </div>
        );
      })}

      {done && (
        <DecisionBanner result={result!} />
      )}
    </div>
  );
}

function StageDetail({ stageKey, result }: { stageKey: string; result: UpiPayResult }) {
  const muted = "text-[11px] text-[var(--text-muted)]";
  switch (stageKey) {
    case "features_extracted":
      return (
        <p className={muted}>
          {(result.pipeline.stages.features_extracted?.features_count as number) ?? 19} features · amount z-score{" "}
          {result.feature_contributions.find((f) => f.feature === "amount_zscore")?.value ?? "—"}
        </p>
      );
    case "ml_prediction":
      return (
        <p className={muted}>
          Fraud probability <b style={{ color: "var(--text)" }}>{(result.ml_fraud_prob * 100).toFixed(1)}%</b> · anomaly{" "}
          {(result.anomaly_score * 100).toFixed(0)}% · RandomForest
        </p>
      );
    case "risk_scored":
      return (
        <p className={muted}>
          Score <b style={{ color: "var(--text)" }}>{result.risk_score}/100</b> · tier {result.risk_tier}
        </p>
      );
    case "blockchain_logged":
      return (
        <p className={muted}>
          Block #{result.block_index} · <span className="font-mono text-[var(--accent-cyan)]">{shortHash(result.block_hash)}</span>
        </p>
      );
    case "decision":
      return <p className={muted}>{result.recommended_action}</p>;
    default:
      return null;
  }
}

function DecisionBanner({ result }: { result: UpiPayResult }) {
  const meta = DECISION_META[result.decision];
  return (
    <div
      className="animate-fade-up mt-1 flex items-center justify-between rounded-xl p-4"
      style={{ background: meta.bg, border: `1px solid ${meta.color}` }}
    >
      <div>
        <p className="text-lg font-bold" style={{ color: meta.color }}>
          {meta.emoji} {result.decision.replace("_", "-")}
        </p>
        <p className="text-xs text-[var(--text-muted)]">
          {formatINR(result.amount_inr)} → {result.receiver_vpa}
        </p>
      </div>
      <div className="text-right">
        <p className="text-2xl font-bold" style={{ color: meta.color }}>
          {result.risk_score}
        </p>
        <p className="text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
          risk · {result.total_duration_ms}ms total
        </p>
      </div>
    </div>
  );
}
