"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { Variants } from "framer-motion";

import {
  ArrowLeft,
  Copy,
  Download,
  Share2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Shield,
} from "lucide-react";
import Link from "next/link";

/* ---------------- VARIANTS (FIXED & TYPED) ---------------- */

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

/* ---------------- PAGE ---------------- */

export default function TransactionDetailPage({
  params,
}: {
  params: { id: string };
}) {
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
    auditTxHash:
      "0x7a2f8b9e4d1c6a3f9e2b4d7c1a6f3e9b2d4c7f1a",
    aiInsight:
      "High Risk Pattern Detected - The wallet address has been associated with 3 rapid-fire transfers in the last 120 seconds, tripping the 'Velocity Threshold' policy.",
    blockchainStatus: "Confirmed",
    timestamp: "2026-01-23 16:45:01 UTC",
  };

  const timeline = [
    {
      icon: Clock,
      label: "Transaction Created",
      time: "16:44:58 UTC",
      color: "blue",
    },
    {
      icon: AlertCircle,
      label: "AI Risk Analysis",
      time: "16:44:59 UTC",
      status: "High Risk",
      color: "amber",
    },
    {
      icon: Shield,
      label: "Blockchain Verification",
      time: "16:45:00 UTC",
      status: "Confirmed",
      color: "emerald",
    },
    {
      icon: CheckCircle2,
      label: "Audit Log Posted",
      time: "16:45:01 UTC",
      status: "Success",
      color: "emerald",
    },
  ];

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div
        variants={itemVariants}
        className="flex items-center justify-between"
      >
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
            <h1 className="text-3xl font-bold text-zinc-900">
              Transaction Details
            </h1>
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
        {/* Left Column */}
        <motion.div
          variants={itemVariants}
          className="lg:col-span-2 space-y-6"
        >
          {/* Status Card */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h2 className="text-xl font-bold text-zinc-900 mb-4">
              Transaction Status
            </h2>
            <span className="inline-block px-4 py-1.5 rounded-full font-bold text-sm bg-amber-100 text-amber-700 border border-amber-300/50">
              FLAGGED
            </span>
          </div>

          {/* Wallet Info */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h3 className="text-lg font-bold text-zinc-900 mb-4">
              Wallet Information
            </h3>

            <div className="space-y-4">
              {[tx.fromWallet, tx.toWallet].map((addr, idx) => (
                <div key={idx}>
                  <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-zinc-200">
                    <code className="flex-1 text-sm font-mono text-zinc-700 break-all">
                      {addr}
                    </code>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => copyToClipboard(addr)}
                    >
                      <Copy className="w-4 h-4 text-zinc-400" />
                    </motion.button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Timeline */}
          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h3 className="text-lg font-bold text-zinc-900 mb-6">
              Transaction Timeline
            </h3>

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
                    <Icon className="w-5 h-5 text-zinc-500" />
                    <div>
                      <p className="font-semibold text-zinc-900">
                        {item.label}
                      </p>
                      <p className="text-xs text-zinc-500">{item.time}</p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </motion.div>

        {/* Right Column */}
        <motion.div variants={itemVariants} className="space-y-6">
          <div className="glass-dark rounded-2xl p-6 border border-zinc-700/50 text-white">
            <h3 className="text-lg font-bold mb-3">AI Risk Analysis</h3>
            <p className="text-sm text-zinc-300">{tx.aiInsight}</p>
          </div>

          <div className="glass rounded-2xl p-6 border border-zinc-200/50">
            <h3 className="text-lg font-bold text-zinc-900 mb-4">
              Blockchain Proof
            </h3>
            <p className="text-sm font-mono text-zinc-600">
              {tx.auditTxHash}
            </p>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
