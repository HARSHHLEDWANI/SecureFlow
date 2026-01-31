"use client";
import { Transaction } from "@/types/transaction";
import { AuditBadge } from "./AuditBadge";
import { StatusExplanation } from "./StatusExplanation";
import { motion } from "framer-motion";
import { Copy, ExternalLink } from "lucide-react";
import { useState } from "react";

function statusColor(status: Transaction["status"]) {
  switch (status) {
    case "APPROVED":
      return "bg-emerald-500/10 text-emerald-600 border-emerald-500/30";
    case "FLAGGED":
      return "bg-amber-500/10 text-amber-600 border-amber-500/30";
    case "REJECTED":
      return "bg-red-500/10 text-red-600 border-red-500/30";
    default:
      return "bg-zinc-500/10 text-zinc-600 border-zinc-500/30";
  }
}

function statusGlowColor(status: Transaction["status"]) {
  switch (status) {
    case "APPROVED":
      return "bg-emerald-500";
    case "FLAGGED":
      return "bg-amber-500";
    case "REJECTED":
      return "bg-red-500";
    default:
      return "bg-zinc-500";
  }
}

export function TransactionCard({ tx }: { tx: Transaction }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.96 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      whileHover={{ 
        y: -4,
        boxShadow: "0 20px 40px -12px rgba(0,0,0,0.12)",
        transition: { duration: 0.2 }
      }}
      className="glass group relative overflow-hidden rounded-2xl p-6 border border-zinc-200/60 bg-white/70 backdrop-blur-md cursor-pointer"
    >
      {/* Decorative animated glow */}
      <motion.div
        className={`absolute -right-6 -top-6 w-32 h-32 blur-3xl opacity-0 group-hover:opacity-20 transition-opacity duration-500 ${statusGlowColor(tx.status)}`}
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0, 0.15, 0],
        }}
        transition={{ duration: 3, repeat: Infinity }}
      />

      {/* Status indicator with pulse */}
      <div className="flex justify-between items-start mb-5">
        <div className="flex items-center gap-3">
          <div className="relative">
            <span className={`animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full opacity-75 ${
              tx.status === 'FLAGGED' ? 'bg-amber-400' : tx.status === 'APPROVED' ? 'bg-emerald-400' : 'bg-red-400'
            }`} />
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
              tx.status === 'FLAGGED' ? 'bg-amber-500' : tx.status === 'APPROVED' ? 'bg-emerald-500' : 'bg-red-500'
            }`} />
          </div>
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-[11px] font-mono font-bold text-zinc-500 uppercase tracking-wider"
          >
            {new Date(tx.createdAt).toLocaleString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })}
          </motion.span>
        </div>

        <div className="flex items-center gap-2">
          <motion.span
            whileHover={{ scale: 1.05 }}
            className={`text-[10px] font-bold px-3 py-1.5 rounded-lg border font-mono ${statusColor(tx.status)}`}
          >
            {tx.status}
          </motion.span>
          <AuditBadge status={tx.auditTxHash ? 'verified' : 'pending'} />
        </div>
      </div>

      {/* Main content */}
      <div className="space-y-4">
        {/* Wallet addresses with copy action */}
        <div className="space-y-2.5 bg-linear-to-br from-zinc-50/50 to-white rounded-xl p-4 border border-zinc-100/50">
          <div className="flex items-center justify-between group/row">
            <span className="text-[11px] text-zinc-500 font-bold uppercase tracking-wider">From Wallet</span>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => copyToClipboard(tx.fromWallet)}
              className="opacity-0 group-hover/row:opacity-100 transition-opacity p-1"
            >
              <Copy className="w-3.5 h-3.5 text-zinc-400 hover:text-zinc-600" />
            </motion.button>
          </div>
          <code className="block text-xs font-mono text-zinc-700 break-all bg-white rounded p-2 border border-zinc-200/50">
            {tx.fromWallet}
          </code>

          <div className="flex items-center justify-between group/row pt-2">
            <span className="text-[11px] text-zinc-500 font-bold uppercase tracking-wider">To Wallet</span>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => copyToClipboard(tx.toWallet)}
              className="opacity-0 group-hover/row:opacity-100 transition-opacity p-1"
            >
              <Copy className="w-3.5 h-3.5 text-zinc-400 hover:text-zinc-600" />
            </motion.button>
          </div>
          <code className="block text-xs font-mono text-zinc-700 break-all bg-white rounded p-2 border border-zinc-200/50">
            {tx.toWallet}
          </code>
        </div>

        {/* Amount and Risk Score */}
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-100">
          <motion.div
            whileHover={{ scale: 1.02 }}
            className="p-3 rounded-lg bg-linear-to-br from-blue-50 to-blue-50/50 border border-blue-100/50"
          >
            <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mb-1">Amount</p>
            <p className="text-lg font-bold text-zinc-900">
              {tx.amount.toLocaleString()}{" "}
              <span className="text-sm font-medium text-zinc-600">{tx.currency}</span>
            </p>
          </motion.div>

          <motion.div
            whileHover={{ scale: 1.02 }}
            className="p-3 rounded-lg bg-linear-to-br from-amber-50 to-amber-50/50 border border-amber-100/50"
          >
            <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mb-1">Risk Score</p>
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <div className="w-full h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${tx.riskScore}%` }}
                    transition={{ duration: 0.6, delay: 0.2 }}
                    className={`h-full rounded-full ${
                      tx.riskScore! > 70
                        ? "bg-red-500"
                        : tx.riskScore! > 30
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                  />
                </div>
              </div>
              <span className={`text-sm font-bold ${
                tx.riskScore! > 70
                  ? "text-red-600"
                  : tx.riskScore! > 30
                  ? "text-amber-600"
                  : "text-emerald-600"
              }`}>
                {typeof tx.riskScore === "number" ? tx.riskScore.toFixed(0) : "—"}%
              </span>
            </div>
          </motion.div>
        </div>

        {/* Action button */}
        <motion.button
          whileHover={{ scale: 1.02, backgroundColor: "rgba(59, 130, 246, 0.1)" }}
          whileTap={{ scale: 0.98 }}
          className="w-full mt-2 py-2 px-3 rounded-lg bg-blue-50/50 border border-blue-200/50 text-blue-600 text-sm font-semibold flex items-center justify-center gap-2 hover:border-blue-300 transition-colors group/btn"
        >
          <ExternalLink className="w-4 h-4 group-hover/btn:translate-x-0.5 transition-transform" />
          View Details
        </motion.button>
      </div>
    </motion.div>
  );
}