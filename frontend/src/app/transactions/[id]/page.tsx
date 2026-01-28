"use client";
import { motion } from "framer-motion";
import { ArrowLeft, Copy, Download, Share2, CheckCircle2, AlertCircle, Clock, Shield } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

export default function TransactionDetailPage({ params }: { params: { id: string } }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Mock transaction data
  const tx = {
    id: params.id,
    status: "FLAGGED",
    amount: 15000,
    currency: "USD",
    fromWallet: "0x1234567890abcdef1234567890abcdef12345678",
    toWallet: "0xabcdef1234567890abcdef1234567890abcdef12",
    riskScore: 78,
    createdAt: new Date().toISOString(),
    auditTxHash: "0x7a2f8b9e4d1c6a3f9e2b4d7c1a6f3e9b2d4c7f1a",
    aiInsight: "High Risk Pattern Detected - The wallet address has been associated with 3 rapid-fire transfers in the last 120 seconds, tripping the 'Velocity Threshold' policy.",
    blockchainStatus: "Confirmed",
    timestamp: "2026-01-23 16:45:01 UTC",
  };

  const timeline = [
    { icon: Clock, label: "Transaction Created", time: "16:44:58 UTC", color: "blue" },
    { icon: AlertCircle, label: "AI Risk Analysis", time: "16:44:59 UTC", status: "High Risk", color: "amber" },
    { icon: Shield, label: "Blockchain Verification", time: "16:45:00 UTC", status: "Confirmed", color: "emerald" },
    { icon: CheckCircle2, label: "Audit Log Posted", time: "16:45:01 UTC", status: "Success", color: "emerald" },
  ];

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/transactions">
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              className="p-2 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-zinc-600" />
            </motion.button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-zinc-900">Transaction Details</h1>
            <p className="text-sm text-zinc-600">ID: {tx.id}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="px-4 py-2 flex items-center gap-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-all"
          >
            <Download className="w-4 h-4" />
            Export PDF
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="px-4 py-2 flex items-center gap-2 rounded-lg bg-zinc-100 text-zinc-700 font-semibold hover:bg-zinc-200 transition-all"
          >
            <Share2 className="w-4 h-4" />
            Share
          </motion.button>
        </div>
      </motion.div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Primary Info */}
        <motion.div variants={itemVariants} className="lg:col-span-2 space-y-6">
          {/* Status Card */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-zinc-900">Transaction Status</h2>
              <motion.span
                whileHover={{ scale: 1.05 }}
                className="px-4 py-1.5 rounded-full font-bold text-sm bg-amber-100 text-amber-700 border border-amber-300/50"
              >
                FLAGGED
              </motion.span>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-50/50 rounded-xl border border-blue-100/50">
                  <p className="text-xs text-zinc-500 font-bold uppercase mb-2">Amount</p>
                  <p className="text-2xl font-bold text-zinc-900">
                    {tx.amount.toLocaleString()} <span className="text-sm text-zinc-600">{tx.currency}</span>
                  </p>
                </div>
                <div className="p-4 bg-gradient-to-br from-amber-50 to-amber-50/50 rounded-xl border border-amber-100/50">
                  <p className="text-xs text-zinc-500 font-bold uppercase mb-2">Risk Score</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <div className="w-full h-2 bg-zinc-200 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: "78%" }}
                          transition={{ duration: 0.6, delay: 0.3 }}
                          className="h-full rounded-full bg-gradient-to-r from-amber-400 to-red-500"
                        />
                      </div>
                    </div>
                    <span className="text-2xl font-bold text-amber-600 w-12 text-right">78%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Wallet Information */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h3 className="text-lg font-bold text-zinc-900 mb-4">Wallet Information</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-2 block">From Address</label>
                <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-zinc-200 group hover:border-zinc-300 transition-all">
                  <code className="flex-1 text-sm font-mono text-zinc-700 break-all">{tx.fromWallet}</code>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => copyToClipboard(tx.fromWallet)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-2"
                  >
                    <Copy className="w-4 h-4 text-zinc-400 hover:text-zinc-600" />
                  </motion.button>
                </div>
              </div>

              <div className="flex justify-center py-2">
                <motion.div
                  animate={{ y: [0, 4, 0] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="text-zinc-400"
                >
                  ↓
                </motion.div>
              </div>

              <div>
                <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-2 block">To Address</label>
                <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-zinc-200 group hover:border-zinc-300 transition-all">
                  <code className="flex-1 text-sm font-mono text-zinc-700 break-all">{tx.toWallet}</code>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => copyToClipboard(tx.toWallet)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-2"
                  >
                    <Copy className="w-4 h-4 text-zinc-400 hover:text-zinc-600" />
                  </motion.button>
                </div>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h3 className="text-lg font-bold text-zinc-900 mb-6">Transaction Timeline</h3>
            <div className="space-y-4">
              {timeline.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="flex gap-4"
                  >
                    <div className="flex flex-col items-center">
                      <motion.div
                        whileHover={{ scale: 1.2 }}
                        className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold
                          ${item.color === 'blue' ? 'bg-blue-500' : item.color === 'amber' ? 'bg-amber-500' : 'bg-emerald-500'}`}
                      >
                        <Icon className="w-5 h-5" />
                      </motion.div>
                      {idx < timeline.length - 1 && <div className="w-0.5 h-12 bg-zinc-200 my-2" />}
                    </div>
                    <div className="pb-4">
                      <p className="font-semibold text-zinc-900">{item.label}</p>
                      <p className="text-xs text-zinc-500 font-mono">{item.time}</p>
                      {item.status && (
                        <p className={`text-xs font-bold mt-1 ${
                          item.color === 'emerald' ? 'text-emerald-600' : 'text-amber-600'
                        }`}>
                          ✓ {item.status}
                        </p>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </motion.div>

        {/* Right Column - Insights */}
        <motion.div variants={itemVariants} className="space-y-6">
          {/* AI Insight */}
          <div className="glass-dark rounded-2xl p-6 border border-zinc-700/50 text-white">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-5 h-5 text-amber-400" />
              <h3 className="text-lg font-bold">AI Risk Analysis</h3>
            </div>
            <div className="space-y-3">
              <p className="text-sm leading-relaxed text-zinc-300">
                {tx.aiInsight}
              </p>
              <motion.button
                whileHover={{ scale: 1.05 }}
                className="w-full mt-4 py-2 px-3 rounded-lg bg-amber-600/20 border border-amber-400/50 text-amber-300 font-semibold text-sm hover:bg-amber-600/30 transition-all"
              >
                View Full Analysis
              </motion.button>
            </div>
          </div>

          {/* Blockchain Proof */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5 text-emerald-600" />
              <h3 className="text-lg font-bold text-zinc-900">Blockchain Proof</h3>
            </div>
            <div className="space-y-3">
              <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200/50">
                <p className="text-xs text-zinc-600 font-bold uppercase mb-1">Status</p>
                <p className="text-sm font-semibold text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  {tx.blockchainStatus}
                </p>
              </div>

              <div>
                <p className="text-xs text-zinc-600 font-bold uppercase mb-2">Transaction Hash</p>
                <div className="flex items-center gap-2 p-2 bg-zinc-50 rounded border border-zinc-200 group hover:border-zinc-300 transition-all">
                  <code className="flex-1 text-xs font-mono text-zinc-600 truncate">{tx.auditTxHash}</code>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => copyToClipboard(tx.auditTxHash)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1"
                  >
                    <Copy className="w-3.5 h-3.5 text-zinc-400 hover:text-zinc-600" />
                  </motion.button>
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-600 font-bold uppercase mb-2">Timestamp</p>
                <p className="text-xs font-mono text-zinc-700">{tx.timestamp}</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <motion.div
            whileHover={{ scale: 1.02 }}
            className="glass rounded-2xl p-6 border border-zinc-200/50"
          >
            <h3 className="text-lg font-bold text-zinc-900 mb-4">Actions</h3>
            <div className="space-y-2">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="w-full py-2 px-3 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition-all"
              >
                Approve Transaction
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="w-full py-2 px-3 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 transition-all"
              >
                Block & Report
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </motion.div>
  );
}