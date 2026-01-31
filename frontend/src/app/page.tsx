"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { Variants } from "framer-motion";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import {
  ArrowUpRight,
  ArrowDownLeft,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";

import { fetchDashboardStats, fetchAuditStats } from "@/lib/api";
import { useToast } from "@/components/Toast";

/* ---------------- VARIANTS (FIXED & TYPED) ---------------- */

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
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

/* ---------------- MOCK DATA ---------------- */

const chartData = [
  { time: "00:00", risk: 15, scanned: 120, flagged: 2 },
  { time: "04:00", risk: 22, scanned: 150, flagged: 4 },
  { time: "08:00", risk: 18, scanned: 180, flagged: 3 },
  { time: "12:00", risk: 28, scanned: 200, flagged: 8 },
  { time: "16:00", risk: 24, scanned: 175, flagged: 5 },
  { time: "20:00", risk: 32, scanned: 220, flagged: 12 },
  { time: "24:00", risk: 19, scanned: 160, flagged: 3 },
];

/* ---------------- PAGE ---------------- */

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
    const loadData = async () => {
      try {
        setLoading(true);
        const [dashboardStats, auditData] = await Promise.all([
          fetchDashboardStats(),
          fetchAuditStats(),
        ]);
        setStats(dashboardStats);
        setAuditStats(auditData);
      } catch (err) {
        console.error(err);
        show("Warning", "Using demo data – backend unavailable", "warning");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [show]);

  const statusData = [
    {
      name: "Approved",
      value: Math.max(
        1,
        stats.totalTransactions - stats.flaggedTransactions
      ),
      color: "#10b981",
    },
    {
      name: "Flagged",
      value: stats.flaggedTransactions,
      color: "#f59e0b",
    },
    {
      name: "Rejected",
      value: Math.max(
        0,
        stats.flaggedTransactions - stats.flaggedTransactions * 0.7
      ),
      color: "#ef4444",
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
      <motion.div variants={itemVariants}>
        <h1 className="text-5xl font-bold gradient-text-glow">
          System Overview
        </h1>
        <p className="text-foreground/60 mt-2">
          Real-time fraud monitoring and blockchain synchronization.
        </p>
      </motion.div>

      {/* KPI Grid */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
      >
        <StatCard
          title="Total Scanned"
          value={stats.totalTransactions.toLocaleString()}
          change="+2.5%"
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

      {/* Charts */}
      <motion.div
        variants={itemVariants}
        className="glow-card rounded-2xl p-6 border"
      >
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line dataKey="risk" stroke="#6366f1" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </motion.div>
    </motion.div>
  );
}

/* ---------------- STAT CARD ---------------- */

interface StatCardProps {
  title: string;
  value: string;
  change: string;
  icon: React.ReactNode;
  trend: "up" | "down" | "alert" | "stable";
  delay: number;
}

function StatCard({
  title,
  value,
  change,
  icon,
  trend,
  delay,
}: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      className="glow-card rounded-2xl p-6 border"
    >
      <div className="flex items-center gap-3 mb-3">{icon}</div>
      <p className="text-xs text-foreground/60 uppercase">{title}</p>
      <h3 className="text-3xl font-bold">{value}</h3>
      <p className="text-sm">{change}</p>
    </motion.div>
  );
}
