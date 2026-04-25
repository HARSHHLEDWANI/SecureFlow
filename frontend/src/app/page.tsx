"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { Shield, TrendingUp, AlertTriangle, Activity } from "lucide-react";
import { useAuth } from "@/context/auth";
import {
  fetchDashboardStats,
  fetchTransactions,
  DashboardStats,
  Transaction,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  APPROVED: "#22d3ee",
  FLAGGED: "#f59e0b",
  REJECTED: "#ef4444",
  PENDING: "#6366f1",
};

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentTx, setRecentTx] = useState<Transaction[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchDashboardStats(), fetchTransactions({ limit: 5 })])
      .then(([s, t]) => {
        setStats(s);
        setRecentTx(t.items);
      })
      .catch((e) => setError(e.message))
      .finally(() => setDataLoading(false));
  }, [user]);

  if (loading || (!user && !error)) return null;

  const kpis = stats
    ? [
        {
          label: "Total Transactions",
          value: stats.totalTransactions.toLocaleString(),
          icon: Activity,
          color: "cyan",
        },
        {
          label: "Flagged",
          value: stats.flaggedCount.toLocaleString(),
          icon: AlertTriangle,
          color: "amber",
        },
        {
          label: "Avg Risk Score",
          value: `${(stats.averageRiskScore * 100).toFixed(1)}%`,
          icon: TrendingUp,
          color: "purple",
        },
        {
          label: "Total Volume",
          value: `$${stats.totalVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
          icon: Shield,
          color: "emerald",
        },
      ]
    : [];

  const pieData = stats
    ? Object.entries(stats.statusBreakdown).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time fraud monitoring overview</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Live
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          Failed to load dashboard: {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {dataLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-28 rounded-xl bg-slate-800/40 animate-pulse" />
            ))
          : kpis.map((kpi, i) => (
              <motion.div
                key={kpi.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-5"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-slate-400 text-sm">{kpi.label}</span>
                  <kpi.icon className={`w-5 h-5 text-${kpi.color}-400`} />
                </div>
                <p className="text-2xl font-bold text-white">{kpi.value}</p>
              </motion.div>
            ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Daily Volume chart */}
        <div className="xl:col-span-2 bg-slate-900/60 border border-slate-700/40 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">7-Day Transaction Volume</h2>
          {dataLoading ? (
            <div className="h-48 rounded-lg bg-slate-800/40 animate-pulse" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={stats?.dailyVolume}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <Line type="monotone" dataKey="volume" stroke="#22d3ee" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Status breakdown pie */}
        <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Status Breakdown</h2>
          {dataLoading ? (
            <div className="h-48 rounded-full bg-slate-800/40 animate-pulse mx-auto w-48" />
          ) : pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#6366f1"} />
                  ))}
                </Pie>
                <Legend formatter={(v) => <span className="text-slate-300 text-xs">{v}</span>} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-500 text-sm text-center mt-8">No data</p>
          )}
        </div>
      </div>

      {/* Recent transactions */}
      <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Recent Transactions</h2>
        {dataLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 rounded bg-slate-800/40 animate-pulse" />
            ))}
          </div>
        ) : recentTx.length === 0 ? (
          <p className="text-slate-500 text-sm">No transactions yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-700/40">
                  <th className="text-left pb-2 font-medium">From</th>
                  <th className="text-left pb-2 font-medium">Amount</th>
                  <th className="text-left pb-2 font-medium">Status</th>
                  <th className="text-left pb-2 font-medium">Risk</th>
                  <th className="text-left pb-2 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentTx.map((tx) => (
                  <tr
                    key={tx.id}
                    className="border-b border-slate-800/40 hover:bg-slate-800/20 cursor-pointer"
                    onClick={() => router.push(`/transactions/${tx.id}`)}
                  >
                    <td className="py-2 font-mono text-slate-300 truncate max-w-[140px]">
                      {tx.fromWallet.slice(0, 10)}…
                    </td>
                    <td className="py-2 text-white">
                      {Number(tx.amount).toLocaleString()} {tx.currency}
                    </td>
                    <td className="py-2">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{
                          background: `${STATUS_COLORS[tx.status]}20`,
                          color: STATUS_COLORS[tx.status],
                        }}
                      >
                        {tx.status}
                      </span>
                    </td>
                    <td className="py-2 text-slate-300">
                      {tx.riskScore != null ? `${(tx.riskScore * 100).toFixed(0)}%` : "—"}
                    </td>
                    <td className="py-2 text-slate-400">
                      {new Date(tx.createdAt).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
