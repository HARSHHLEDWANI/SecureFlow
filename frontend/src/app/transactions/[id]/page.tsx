"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import type { Variants } from "framer-motion";
import {
  ArrowLeft,
  Copy,
  Check,
  ExternalLink,
  Clock,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/context/auth";
import { fetchTransactionById, Transaction } from "@/lib/api";

const ETHERSCAN = "https://sepolia.etherscan.io/tx/";

const STATUS_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  APPROVED: { text: "text-cyan-400", bg: "bg-cyan-400/10", border: "border-cyan-400/30" },
  FLAGGED: { text: "text-amber-400", bg: "bg-amber-400/10", border: "border-amber-400/30" },
  REJECTED: { text: "text-red-400", bg: "bg-red-400/10", border: "border-red-400/30" },
  PENDING: { text: "text-indigo-400", bg: "bg-indigo-400/10", border: "border-indigo-400/30" },
};

const STATUS_ICON: Record<string, typeof CheckCircle2> = {
  APPROVED: CheckCircle2,
  FLAGGED: AlertTriangle,
  REJECTED: XCircle,
  PENDING: Clock,
};

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
};

export default function TransactionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tx, setTx] = useState<Transaction | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    fetchTransactionById(params.id)
      .then(setTx)
      .catch((e) => setError((e as Error).message))
      .finally(() => setDataLoading(false));
  }, [user, params.id]);

  async function copy(text: string, field: string) {
    await navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  }

  if (loading || dataLoading) {
    return (
      <div className="space-y-4 max-w-4xl">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-32 rounded-xl bg-slate-800/40 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !tx) {
    return (
      <div className="space-y-4">
        <Link href="/transactions" className="flex items-center gap-2 text-slate-400 hover:text-white text-sm">
          <ArrowLeft className="w-4 h-4" /> Back to Transactions
        </Link>
        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error ?? "Transaction not found."}
        </div>
      </div>
    );
  }

  const sc = STATUS_COLORS[tx.status] ?? STATUS_COLORS.PENDING;
  const StatusIcon = STATUS_ICON[tx.status] ?? Clock;

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-6 max-w-4xl">
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-center gap-4">
        <Link href="/transactions">
          <button className="p-2 rounded-lg border border-slate-700/40 hover:bg-slate-800/60 transition-colors">
            <ArrowLeft className="w-4 h-4 text-slate-400" />
          </button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">Transaction Details</h1>
          <p className="text-slate-500 text-xs font-mono mt-0.5">{tx.id}</p>
        </div>
      </motion.div>

      {/* Status + Amount */}
      <motion.div
        variants={itemVariants}
        className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full ${sc.bg} flex items-center justify-center`}>
            <StatusIcon className={`w-5 h-5 ${sc.text}`} />
          </div>
          <div>
            <p className="text-slate-400 text-xs mb-0.5">Status</p>
            <span className={`font-semibold text-sm ${sc.text}`}>{tx.status}</span>
          </div>
        </div>
        <div className="text-right">
          <p className="text-slate-400 text-xs mb-0.5">Amount</p>
          <p className="text-2xl font-bold text-white">
            {Number(tx.amount).toLocaleString()} {tx.currency}
          </p>
        </div>
      </motion.div>

      {/* Wallets */}
      <motion.div variants={itemVariants} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-semibold text-white">Wallet Information</h2>
        {[
          { label: "From Wallet", value: tx.fromWallet },
          { label: "To Wallet", value: tx.toWallet },
        ].map(({ label, value }) => (
          <div key={label}>
            <p className="text-slate-400 text-xs mb-1">{label}</p>
            <div className="flex items-center gap-2 px-3 py-2 bg-slate-800/60 rounded-lg border border-slate-700/30">
              <code className="flex-1 text-sm font-mono text-slate-200 break-all">{value}</code>
              <button onClick={() => copy(value, label)} className="text-slate-500 hover:text-white shrink-0">
                {copiedField === label ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </motion.div>

      {/* Risk + AI */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-3">
          <h2 className="text-base font-semibold text-white">Risk Score</h2>
          {tx.riskScore != null ? (
            <>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold text-white">
                  {(tx.riskScore * 100).toFixed(0)}
                </span>
                <span className="text-slate-400 text-lg mb-1">%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-700">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${tx.riskScore * 100}%`,
                    background:
                      tx.riskScore > 0.7 ? "#ef4444" : tx.riskScore > 0.4 ? "#f59e0b" : "#22d3ee",
                  }}
                />
              </div>
              {tx.confidence != null && (
                <p className="text-slate-400 text-xs">
                  Confidence: {(tx.confidence * 100).toFixed(1)}%
                </p>
              )}
            </>
          ) : (
            <p className="text-slate-500 text-sm">Not scored yet</p>
          )}
        </div>

        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-3">
          <h2 className="text-base font-semibold text-white">AI Explanation</h2>
          {tx.aiExplanation ? (
            <p className="text-slate-300 text-sm leading-relaxed">{tx.aiExplanation}</p>
          ) : (
            <p className="text-slate-500 text-sm">No explanation available.</p>
          )}
        </div>
      </motion.div>

      {/* Blockchain proof */}
      <motion.div variants={itemVariants} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-3">
        <h2 className="text-base font-semibold text-white">Blockchain Proof</h2>
        {tx.auditTxHash ? (
          <div className="flex items-center gap-3 px-3 py-2 bg-slate-800/60 rounded-lg border border-slate-700/30">
            <code className="flex-1 text-xs font-mono text-slate-200 break-all">{tx.auditTxHash}</code>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => copy(tx.auditTxHash!, "hash")} className="text-slate-500 hover:text-white">
                {copiedField === "hash" ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
              <a
                href={`${ETHERSCAN}${tx.auditTxHash}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-slate-600" />
            <p className="text-slate-500 text-sm">Not recorded on-chain yet.</p>
          </div>
        )}
      </motion.div>

      {/* Metadata */}
      <motion.div variants={itemVariants} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6">
        <h2 className="text-base font-semibold text-white mb-4">Details</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          {[
            { label: "Created", value: new Date(tx.createdAt).toLocaleString() },
            { label: "Updated", value: new Date(tx.updatedAt).toLocaleString() },
            { label: "Submitted by", value: tx.user?.email ?? "—" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-slate-400 text-xs mb-1">{label}</p>
              <p className="text-white">{value}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Audit log entries if included */}
      {tx.auditLogs && tx.auditLogs.length > 0 && (
        <motion.div variants={itemVariants} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-3">
          <h2 className="text-base font-semibold text-white">Audit History</h2>
          <div className="divide-y divide-slate-800/40">
            {tx.auditLogs.map((log) => (
              <div key={log.id} className="py-3 flex items-center justify-between text-sm">
                <div>
                  <span className={`font-semibold ${STATUS_COLORS[log.action]?.text ?? "text-slate-300"}`}>
                    {log.action}
                  </span>
                  <span className="text-slate-500 ml-2">by {log.actor?.email ?? log.actorId.slice(0, 8)}</span>
                </div>
                <span className="text-slate-500 text-xs">{new Date(log.createdAt).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
