"use client";

import { useCallback, useEffect, useState } from "react";
import { Boxes, CheckCircle2, ChevronDown, Link2, ShieldCheck, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { Block } from "@/lib/types";
import { formatDateTime, shortHash } from "@/lib/format";
import { EmptyState, Panel, Skeleton, StatCard } from "@/components/ui";

export default function BlockchainPage() {
  const [chain, setChain] = useState<Block[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; message: string } | null>(null);
  const [validating, setValidating] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.chain();
      setChain([...data.chain].reverse());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function validate() {
    setValidating(true);
    try {
      const res = await api.validateChain();
      setValidation(res);
    } finally {
      setValidating(false);
    }
  }

  const totalTxns = chain.reduce((sum, b) => sum + b.transactions.length, 0);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Blockchain Explorer</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Tamper-evident audit ledger · SHA-256 proof-of-work
          </p>
        </div>
        <button className="btn btn-primary" onClick={validate} disabled={validating}>
          <ShieldCheck className="h-4 w-4" />
          {validating ? "Validating…" : "Validate chain"}
        </button>
      </header>

      {validation && (
        <div
          className="panel flex items-center gap-3 p-4 animate-fade-up"
          style={{ borderColor: validation.valid ? "var(--success)" : "var(--danger)" }}
        >
          {validation.valid ? (
            <CheckCircle2 className="h-5 w-5 text-[var(--success)]" />
          ) : (
            <XCircle className="h-5 w-5 text-[var(--danger)]" />
          )}
          <p className="text-sm">{validation.message}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard label="Blocks" value={chain.length} accent="var(--accent-cyan)" />
        <StatCard label="Transactions logged" value={totalTxns} />
        <StatCard label="Latest hash" value={<span className="font-mono text-sm">{shortHash(chain[0]?.hash ?? null)}</span>} accent="var(--success)" />
      </div>

      <Panel title="Chain">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : chain.length === 0 ? (
          <EmptyState title="Empty chain" />
        ) : (
          <div className="space-y-2">
            {chain.map((block) => (
              <div key={block.index} className="panel-2 overflow-hidden">
                <button
                  className="flex w-full items-center justify-between p-3 text-left"
                  onClick={() => setExpanded(expanded === block.index ? null : block.index)}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--surface)]">
                      <Boxes className="h-4 w-4 text-[var(--accent)]" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">
                        Block #{block.index}
                        {block.index === 0 && (
                          <span className="ml-2 text-[10px] text-[var(--text-dim)]">genesis</span>
                        )}
                      </p>
                      <p className="font-mono text-[11px] text-[var(--text-dim)]">
                        {shortHash(block.hash, 14)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="hidden text-xs text-[var(--text-dim)] sm:block">
                      {block.transactions.length} txn · nonce {block.nonce}
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 text-[var(--text-muted)] transition ${
                        expanded === block.index ? "rotate-180" : ""
                      }`}
                    />
                  </div>
                </button>

                {expanded === block.index && (
                  <div className="border-t border-[var(--border)] p-3 text-xs animate-fade-up">
                    <div className="mb-3 grid gap-1 sm:grid-cols-2">
                      <Field label="Timestamp" value={formatDateTime(new Date(block.timestamp * 1000).toISOString())} />
                      <Field label="Nonce" value={String(block.nonce)} mono />
                      <Field label="Hash" value={block.hash} mono full />
                      <Field label="Previous hash" value={block.previous_hash} mono full />
                    </div>
                    <p className="mb-1 flex items-center gap-1 text-[var(--text-muted)]">
                      <Link2 className="h-3 w-3" /> Transactions
                    </p>
                    <pre className="max-h-48 overflow-auto rounded-md bg-[var(--bg)] p-2 text-[11px] text-[var(--text-muted)] scrollbar-thin">
                      {JSON.stringify(block.transactions, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

function Field({ label, value, mono, full }: { label: string; value: string; mono?: boolean; full?: boolean }) {
  return (
    <div className={full ? "sm:col-span-2" : ""}>
      <span className="text-[var(--text-dim)]">{label}: </span>
      <span className={`${mono ? "font-mono break-all" : ""} text-[var(--text-muted)]`}>{value}</span>
    </div>
  );
}
