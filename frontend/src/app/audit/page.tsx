"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Variants } from "framer-motion";

import {
  fetchAuditLogs,
  fetchAuditStats,
  AuditLog,
} from "@/lib/api";
import { ChartSkeleton } from "@/components/LoadingSkeleton";
import { useToast } from "@/components/Toast";
import {
  CheckCircle2,
  AlertCircle,
  Clock,
  Search,
  Download,
} from "lucide-react";

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

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState({
    totalAudited: 0,
    successRate: 0,
    averageLatency: 0,
  });
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const { show } = useToast();

  const itemsPerPage = 10;

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [logsData, statsData] = await Promise.all([
          fetchAuditLogs({ take: 100 }),
          fetchAuditStats(),
        ]);
        setLogs(logsData);
        setStats(statsData);
      } catch (error) {
        console.error("Error loading audit logs:", error);
        show("Error", "Failed to load audit logs", "error");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [show]);

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.transactionId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || log.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);
  const paginatedLogs = filteredLogs.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className="text-4xl font-bold bg-gradient-to-r from-zinc-900 to-zinc-700 bg-clip-text text-transparent">
          Audit Logs
        </h1>
        <p className="text-zinc-600 mt-2">
          Complete transaction audit history with blockchain verification records.
        </p>
      </motion.div>

      {/* Stats */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
      >
        <StatCard
          icon={<CheckCircle2 className="w-6 h-6" />}
          title="Total Audited"
          value={stats.totalAudited.toString()}
          color="emerald"
        />
        <StatCard
          icon={<CheckCircle2 className="w-6 h-6" />}
          title="Success Rate"
          value={`${stats.successRate.toFixed(1)}%`}
          color="blue"
        />
        <StatCard
          icon={<Clock className="w-6 h-6" />}
          title="Avg Latency"
          value={`${stats.averageLatency.toFixed(2)}s`}
          color="amber"
        />
      </motion.div>

      {/* Filters */}
      <motion.div
        variants={itemVariants}
        className="glass rounded-2xl p-4 border"
      >
        <div className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
            <input
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search by transaction ID or action..."
              className="w-full pl-10 pr-4 py-2.5 border rounded-lg"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {["all", "success", "failed", "pending"].map((status) => (
              <motion.button
                key={status}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => {
                  setStatusFilter(status);
                  setCurrentPage(1);
                }}
                className={`px-4 py-1.5 rounded-lg font-semibold text-sm ${
                  statusFilter === status
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-100 text-zinc-700"
                }`}
              >
                {status === "all" ? "All Status" : status}
              </motion.button>
            ))}
          </div>

          <div className="flex justify-end">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* Table */}
      <motion.div variants={itemVariants}>
        {loading ? (
          <ChartSkeleton />
        ) : (
          <div className="glass rounded-2xl border overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  {[
                    "Transaction ID",
                    "Action",
                    "Status",
                    "Risk",
                    "Timestamp",
                    "Audit Hash",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-6 py-4 text-xs font-semibold uppercase text-zinc-700"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                <AnimatePresence mode="wait">
                  {paginatedLogs.length > 0 ? (
                    paginatedLogs.map((log, idx) => (
                      <motion.tr
                        key={log.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ delay: idx * 0.03 }}
                        className="border-b last:border-b-0"
                      >
                        <td className="px-6 py-4 font-mono text-xs">
                          {log.transactionId.slice(0, 8)}...
                        </td>
                        <td className="px-6 py-4">{log.action}</td>
                        <td className="px-6 py-4">
                          <StatusBadge status={log.status} />
                        </td>
                        <td className="px-6 py-4">{log.riskScore}%</td>
                        <td className="px-6 py-4 text-xs">
                          {new Date(log.timestamp).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-xs font-mono text-blue-600">
                          {log.auditHash.slice(0, 8)}...
                        </td>
                      </motion.tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center">
                        No audit logs found
                      </td>
                    </tr>
                  )}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex justify-between"
        >
          <span className="text-sm">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 bg-zinc-100 rounded-lg"
            >
              Previous
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg"
            >
              Next
            </motion.button>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

/* ---------------- COMPONENTS ---------------- */

function StatCard({
  icon,
  title,
  value,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  color: "emerald" | "blue" | "amber";
}) {
  return (
    <motion.div
      whileHover={{ y: -5 }}
      className={`rounded-2xl p-6 border bg-${color}-50`}
    >
      <div className="w-12 h-12 rounded-lg bg-white flex items-center justify-center">
        {icon}
      </div>
      <p className="text-sm uppercase mt-4">{title}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles = {
    success: "bg-emerald-100 text-emerald-700",
    failed: "bg-red-100 text-red-700",
    pending: "bg-amber-100 text-amber-700",
  };

  return (
    <motion.span
      whileHover={{ scale: 1.1 }}
      className={`px-3 py-1 rounded-lg text-xs font-bold ${
        styles[status as keyof typeof styles] || styles.pending
      }`}
    >
      {status}
    </motion.span>
  );
}
