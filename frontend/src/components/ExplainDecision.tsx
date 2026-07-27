"use client";

import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Explanation } from "@/lib/types";

/**
 * On-demand "Explain this decision" control. Calls the backend, which turns the
 * already-computed risk signals into plain English via an LLM (falling back to a
 * deterministic template). We surface the `source` honestly — "AI-generated" vs
 * "Auto-generated" — rather than pretending the fallback is the same thing.
 */
export default function ExplainDecision({ txnId }: { txnId: string }) {
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setExplanation(await api.explain(txnId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t generate an explanation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {!explanation && (
        <button onClick={run} disabled={busy} className="btn btn-ghost w-full text-sm">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {busy ? "Explaining…" : "Explain this decision"}
        </button>
      )}
      {error && <p className="mt-2 text-xs text-[var(--danger)]">{error}</p>}
      {explanation && (
        <div className="panel-2 animate-fade-up p-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-[var(--accent-cyan)]" />
            <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-dim)]">
              {explanation.source === "llm" ? "AI-generated" : "Auto-generated"}
            </span>
          </div>
          <p className="text-sm text-[var(--text-muted)]">{explanation.explanation}</p>
        </div>
      )}
    </div>
  );
}
