"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Search, ExternalLink, Filter } from "lucide-react";
import { useAuth } from "@/context/auth";
import {
  fetchTransactions,
  createTransaction,
  Transaction,
  CreateTransactionInput,
} from "@/lib/api";

const WALLET_RE = /^0x[a-fA-F0-9]{40}$/;

const STATUS_COLORS: Record<string, string> = {
  APPROVED: "text-cyan-400 bg-cyan-400/10",
  FLAGGED: "text-amber-400 bg-amber-400/10",
  REJECTED: "text-red-400 bg-red-400/10",
  PENDING: "text-indigo-400 bg-indigo-400/10",
};

const ETHERSCAN = "https://sepolia.etherscan.io/tx/";

export default function TransactionsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createResult, setCreateResult] = useState<Transaction | null>(null);
  const [form, setForm] = useState<CreateTransactionInput>({
    fromWallet: "",
    toWallet: "",
    amount: 0,
    currency: "USD",
  });

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [user, loading, router]);

  const load = useCallback(
    async (cursor?: string) => {
      if (!user) return;
      try {
        const res = await fetchTransactions({
          cursor,
          limit: 20,
          status: statusFilter || undefined,
        });
        setTransactions((prev) => (cursor ? [...prev, ...res.items] : res.items));
        setNextCursor(res.meta?.nextCursor ?? null);
        setHasMore(res.meta?.hasMore ?? false);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setDataLoading(false);
      }
    },
    [user, statusFilter]
  );

  useEffect(() => {
    setDataLoading(true);
    setTransactions([]);
    load();
  }, [load]);

  const filtered = transactions.filter(
    (tx) =>
      !search ||
      tx.fromWallet.toLowerCase().includes(search.toLowerCase()) ||
      tx.toWallet.toLowerCase().includes(search.toLowerCase()) ||
      tx.id.toLowerCase().includes(search.toLowerCase())
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!WALLET_RE.test(form.fromWallet)) {
      setCreateError("fromWallet must be a valid Ethereum address (0x + 40 hex chars)");
      return;
    }
    if (!WALLET_RE.test(form.toWallet)) {
      setCreateError("toWallet must be a valid Ethereum address (0x + 40 hex chars)");
      return;
    }
    setCreating(true);
    try {
      const tx = await createTransaction(form);
      setCreateResult(tx);
      setTransactions((prev) => [tx, ...prev]);
    } catch (e) {
      setCreateError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }

  function closeModal() {
    setShowModal(false);
    setCreateResult(null);
    setCreateError(null);
    setForm({ fromWallet: "", toWallet: "", amount: 0, currency: "USD" });
  }

  if (loading) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Transactions</h1>
          <p className="text-slate-400 text-sm mt-1">All payment transactions with AI fraud scores</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-semibold rounded-lg transition-colors text-sm"
        >
          <Plus className="w-4 h-4" /> New Transaction
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by wallet or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-800/60 border border-slate-700/40 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="py-2 px-3 bg-slate-800/60 border border-slate-700/40 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500/50"
          >
            <option value="">All statuses</option>
            <option value="APPROVED">Approved</option>
            <option value="FLAGGED">Flagged</option>
            <option value="REJECTED">Rejected</option>
            <option value="PENDING">Pending</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl overflow-hidden">
        {dataLoading ? (
          <div className="space-y-px">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-12 bg-slate-800/40 animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-slate-500 text-sm p-8 text-center">No transactions found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-700/40 bg-slate-900/40">
                  {["From", "To", "Amount", "Status", "Risk", "On-Chain", "Date"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((tx) => (
                  <tr
                    key={tx.id}
                    className="border-b border-slate-800/30 hover:bg-slate-800/30 cursor-pointer transition-colors"
                    onClick={() => router.push(`/transactions/${tx.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-slate-300">{tx.fromWallet.slice(0, 10)}…</td>
                    <td className="px-4 py-3 font-mono text-slate-300">{tx.toWallet.slice(0, 10)}…</td>
                    <td className="px-4 py-3 text-white">{Number(tx.amount).toLocaleString()} {tx.currency}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[tx.status]}`}>
                        {tx.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {tx.riskScore != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-700">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${tx.riskScore * 100}%`,
                                background: tx.riskScore > 0.7 ? "#ef4444" : tx.riskScore > 0.4 ? "#f59e0b" : "#22d3ee",
                              }}
                            />
                          </div>
                          <span className="text-slate-300 text-xs">{(tx.riskScore * 100).toFixed(0)}%</span>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {tx.auditTxHash ? (
                        <a
                          href={`${ETHERSCAN}${tx.auditTxHash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-xs"
                        >
                          {tx.auditTxHash.slice(0, 8)}… <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : <span className="text-slate-600 text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{new Date(tx.createdAt).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {hasMore && (
          <div className="p-4 text-center">
            <button
              onClick={() => load(nextCursor ?? undefined)}
              className="text-cyan-400 hover:text-cyan-300 text-sm"
            >
              Load more
            </button>
          </div>
        )}
      </div>

      {/* Create Transaction Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={closeModal}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-slate-900 border border-slate-700/60 rounded-2xl p-6 w-full max-w-lg"
              onClick={(e) => e.stopPropagation()}
            >
              {createResult ? (
                <div className="space-y-4">
                  <h2 className="text-lg font-bold text-white">Transaction Submitted</h2>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Status</span>
                      <span className={`font-semibold ${STATUS_COLORS[createResult.status].split(" ")[0]}`}>
                        {createResult.status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Risk Score</span>
                      <span className="text-white">
                        {createResult.riskScore != null ? `${(createResult.riskScore * 100).toFixed(1)}%` : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Confidence</span>
                      <span className="text-white">
                        {createResult.confidence != null ? `${(createResult.confidence * 100).toFixed(1)}%` : "—"}
                      </span>
                    </div>
                    {createResult.aiExplanation && (
                      <div className="pt-2 border-t border-slate-700/40">
                        <p className="text-slate-400 mb-1">AI Explanation</p>
                        <p className="text-slate-200">{createResult.aiExplanation}</p>
                      </div>
                    )}
                    {createResult.auditTxHash && (
                      <div className="pt-2 border-t border-slate-700/40">
                        <p className="text-slate-400 mb-1">Blockchain Hash</p>
                        <a
                          href={`${ETHERSCAN}${createResult.auditTxHash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cyan-400 hover:text-cyan-300 font-mono text-xs break-all flex items-center gap-1"
                        >
                          {createResult.auditTxHash} <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={closeModal}
                    className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors mt-2"
                  >
                    Close
                  </button>
                </div>
              ) : (
                <form onSubmit={handleCreate} className="space-y-4">
                  <h2 className="text-lg font-bold text-white">New Transaction</h2>
                  {createError && (
                    <div className="px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                      {createError}
                    </div>
                  )}
                  {[
                    { label: "From Wallet", key: "fromWallet", placeholder: "0x..." },
                    { label: "To Wallet", key: "toWallet", placeholder: "0x..." },
                  ].map(({ label, key, placeholder }) => (
                    <div key={key} className="space-y-1">
                      <label className="text-sm text-slate-300">{label}</label>
                      <input
                        type="text"
                        placeholder={placeholder}
                        value={form[key as keyof CreateTransactionInput] as string}
                        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                        className="w-full px-3 py-2 bg-slate-800 border border-slate-700/40 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 font-mono"
                        required
                      />
                    </div>
                  ))}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-sm text-slate-300">Amount</label>
                      <input
                        type="number"
                        min="0.000001"
                        step="any"
                        placeholder="100"
                        value={form.amount || ""}
                        onChange={(e) => setForm((f) => ({ ...f, amount: parseFloat(e.target.value) || 0 }))}
                        className="w-full px-3 py-2 bg-slate-800 border border-slate-700/40 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-sm text-slate-300">Currency</label>
                      <select
                        value={form.currency}
                        onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))}
                        className="w-full px-3 py-2 bg-slate-800 border border-slate-700/40 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500/50"
                      >
                        <option>USD</option>
                        <option>ETH</option>
                        <option>USDC</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={closeModal}
                      className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={creating}
                      className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-slate-900 font-semibold rounded-lg text-sm transition-colors"
                    >
                      {creating ? "Submitting…" : "Submit"}
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
