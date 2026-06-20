"use client";

import { Play, Loader2 } from "lucide-react";
import type { UpiScenario } from "@/lib/types";

export default function ScenarioPanel({
  scenarios,
  onRun,
  runningId,
  disabled,
}: {
  scenarios: UpiScenario[];
  onRun: (s: UpiScenario) => void;
  runningId: string | null;
  disabled: boolean;
}) {
  return (
    <div className="space-y-2">
      {scenarios.map((s) => {
        const running = runningId === s.id;
        return (
          <div
            key={s.id}
            className="rounded-xl border border-[var(--border)] p-3 transition hover:border-[var(--border-strong)]"
            style={{ background: "var(--surface-2)" }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <span>{s.emoji}</span>
                  {s.name}
                </p>
                <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{s.description}</p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
                  Expected: {s.expected_result}
                </p>
              </div>
              <button
                onClick={() => onRun(s)}
                disabled={disabled}
                className="btn btn-ghost shrink-0 px-2.5 py-1.5 text-xs"
              >
                {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Run
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
