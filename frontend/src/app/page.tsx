"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { ArrowUpRight, ArrowDownLeft, TrendingUp, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { fetchDashboardStats, fetchAuditStats } from "@/lib/api";
import { useToast } from "@/components/Toast";

// Mock chart data
const chartData = [
  { time: "00:00", risk: 15, scanned: 120, flagged: 2 },
  { time: "04:00", risk: 22, scanned: 150, flagged: 4 },
  { time: "08:00", risk: 18, scanned: 180, flagged: 3 },
  { time: "12:00", risk: 28, scanned: 200, flagged: 8 },
  { time: "16:00", risk: 24, scanned: 175, flagged: 5 },
  { time: "20:00", risk: 32, scanned: 220, flagged: 12 },
  { time: "24:00", risk: 19, scanned: 160, flagged: 3 },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
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

export default function DashboardPage() {
  const [stats, setStats] = useState({
    totalTransactions: 0,
    flaggedTransactions: 0,
    averageRiskScore: 0,
    totalAudited: 0,
  });
  const [auditStats, setAuditStats] = useState({
    totalAudited: 0,
    successRate: 0,
    averageLatency: 0,
  });
  const [loading, setLoading] = useState(true);
  const { show } = useToast();

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        const [dashboardStats, auditData] = await Promise.all([
          fetchDashboardStats(),
          fetchAuditStats(),
        ]);
        setStats(dashboardStats);
        setAuditStats(auditData);
      } catch (error) {
        console.error("Error loading dashboard data:", error);
        show("Warning", "Using demo data - backend not available", "warning");
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [show]);

  const statusData = [
    { name: "Approved", value: Math.max(1, stats.totalTransactions - stats.flaggedTransactions), color: "#10b981" },
    { name: "Flagged", value: stats.flaggedTransactions, color: "#f59e0b" },
    { name: "Rejected", value: Math.max(0, stats.flaggedTransactions - stats.flaggedTransactions * 0.7), color: "#ef4444" },
  ];
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header Section */}
      <motion.div variants={itemVariants}>
        <h1 className="text-5xl font-bold gradient-text-glow">
          System Overview
        </h1>
        <p className="text-foreground/60 text-base mt-2 text-glow">Real-time fraud monitoring and blockchain synchronization across all networks.</p>
      </motion.div>

      {/* KPI Grid */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
      >
        <StatCard
          title="Total Scanned"
          value={stats.totalTransactions.toLocaleString()}
          change={`${stats.totalTransactions > 0 ? '+' : ''}2.5%`}
          icon={<TrendingUp className="w-5 h-5" />}
          trend="up"
          delay={0}
        />
        <StatCard
          title="Flagged (24h)"
          value={stats.flaggedTransactions.toString()}
          change="+2.4%"
          icon={<AlertCircle className="w-5 h-5" />}
          trend="alert"
          delay={0.1}
        />
        <StatCard
          title="Avg Risk Score"
          value={stats.averageRiskScore.toFixed(1)}
          change="↓ 1.2%"
          icon={<CheckCircle2 className="w-5 h-5" />}
          trend="down"
          delay={0.2}
        />
        <StatCard
          title="Audit Latency"
          value={`${auditStats.averageLatency.toFixed(2)}s`}
          change="Optimized"
          icon={<Clock className="w-5 h-5" />}
          trend="stable"
          delay={0.3}
        />
      </motion.div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart */}
        <motion.div
          variants={itemVariants}
          className="lg:col-span-2 glow-card rounded-2xl p-6 border"
        >
          <div className="mb-6">
            <h2 className="text-xl font-bold gradient-text">Risk Trend Analysis</h2>
            <p className="text-sm text-foreground/60">Last 24 hours activity overview</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <defs>
                <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99, 102, 241, 0.1)" />
              <XAxis dataKey="time" stroke="rgba(255, 255, 255, 0.4)" style={{ fontSize: "12px" }} />
              <YAxis stroke="rgba(255, 255, 255, 0.4)" style={{ fontSize: "12px" }} />
              <Tooltip
                contentStyle={{
                  background: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: "12px",
                  boxShadow: "0 8px 32px rgba(99, 102, 241, 0.2)",
                }}
                labelStyle={{ color: "#e0e7ff" }}
              />
              <Legend wrapperStyle={{ color: "rgba(255, 255, 255, 0.7)" }} />
              <Line
                type="monotone"
                dataKey="risk"
                stroke="#6366f1"
                fillOpacity={1}
                fill="url(#colorRisk)"
                strokeWidth={2}
                dot={{ fill: "#3b82f6", r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Status Distribution */}
        <motion.div
          variants={itemVariants}
          className="glow-card rounded-2xl p-6 border"
        >
          <div className="mb-6">
            <h2 className="text-xl font-bold gradient-text">Transaction Status</h2>
            <p className="text-sm text-foreground/60">Distribution breakdown</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
              >
                {statusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} opacity={0.8} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: "12px",
                }}
                labelStyle={{ color: "#e0e7ff" }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-6 space-y-2">
            {statusData.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-foreground/70">{item.name}</span>
                </div>
                <span className="font-semibold text-zinc-900">{item.value}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Activity Chart */}
      <motion.div
        variants={itemVariants}
        className="glow-card rounded-2xl p-6 border"
      >
        <div className="mb-6">
          <h2 className="text-xl font-bold gradient-text">Transactions Scanned</h2>
          <p className="text-sm text-foreground/60">Daily volume comparison</p>
        </div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99, 102, 241, 0.1)" />
            <XAxis dataKey="time" stroke="rgba(255, 255, 255, 0.4)" style={{ fontSize: "12px" }} />
            <YAxis stroke="rgba(255, 255, 255, 0.4)" style={{ fontSize: "12px" }} />
            <Tooltip
              contentStyle={{
                background: "rgba(15, 23, 42, 0.95)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                borderRadius: "12px",
              }}
              labelStyle={{ color: "#e0e7ff" }}
            />
            <Legend wrapperStyle={{ color: "rgba(255, 255, 255, 0.7)" }} />
            <Bar dataKey="scanned" fill="#6366f1" radius={[8, 8, 0, 0]} />
            <Bar dataKey="flagged" fill="#f59e0b" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </motion.div>
    </motion.div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  change: string;
  icon: React.ReactNode;
  trend: "up" | "down" | "alert" | "stable";
  delay: number;
}

function StatCard({ title, value, change, icon, trend, delay }: StatCardProps) {
  const trendColors = {
    up: "text-emerald-400 text-glow",
    down: "text-slate-400",
    alert: "text-amber-400 text-glow",
    stable: "text-cyan-400 text-glow",
  };

  const bgColors = {
    up: "bg-emerald-500/10 border-emerald-500/30",
    down: "bg-slate-500/10 border-slate-500/30",
    alert: "bg-amber-500/10 border-amber-500/30",
    stable: "bg-cyan-500/10 border-cyan-500/30",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delay * 0.1, duration: 0.5 }}
      whileHover={{ y: -8, transition: { duration: 0.2 } }}
      className="group glow-card rounded-2xl p-6 border cursor-pointer overflow-hidden relative"
    >
      {/* Animated background gradient on hover */}
      <div className="absolute inset-0 bg-linear-to-br from-indigo-500/0 via-purple-500/0 to-transparent group-hover:via-indigo-500/10 transition-all duration-500 -z-10 rounded-2xl" />

      <div className="flex items-start justify-between mb-4">
        <div className={`p-3 rounded-xl ${bgColors[trend]} border group-hover:scale-110 transition-transform duration-300 glow-card`}>
          <div className={trendColors[trend]}>{icon}</div>
        </div>
      </div>

      <p className="text-xs font-medium text-foreground/60 uppercase tracking-widest mb-2">{title}</p>
      <h3 className="text-3xl font-bold gradient-text mb-3 group-hover:translate-x-1 transition-transform">
        {value}
      </h3>

      <div className={`flex items-center gap-1 text-sm font-semibold ${trendColors[trend]}`}>
        {trend === "up" && <ArrowUpRight className="w-4 h-4" />}
        {trend === "down" && <ArrowDownLeft className="w-4 h-4" />}
        <span>{change}</span>
      </div>
    </motion.div>
  );
}