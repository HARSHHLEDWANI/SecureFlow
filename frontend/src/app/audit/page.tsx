"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchAuditLogs, fetchAuditStats, AuditLog } from "@/lib/api";
import { ChartSkeleton } from "@/components/LoadingSkeleton";
import { useToast } from "@/components/Toast";
import { CheckCircle2, AlertCircle, Clock, Search, Filter, Download } from "lucide-react";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState({ totalAudited: 0, successRate: 0, averageLatency: 0 });
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

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.transactionId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || log.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);
  const paginatedLogs = filteredLogs.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

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
        <p className="text-zinc-600 text-base mt-2">
          Complete transaction audit history with blockchain verification records.
        </p>
      </motion.div>

      {/* Stats Grid */}
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
      <motion.div variants={itemVariants} className="glass rounded-2xl p-4 border border-zinc-200/50">
        <div className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
            <input
              type="text"
              placeholder="Search by transaction ID or action..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-10 pr-4 py-2.5 bg-white/60 border border-zinc-200/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>

          {/* Filters */}
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
                className={`px-4 py-1.5 rounded-lg font-semibold text-sm transition-all ${
                  statusFilter === status
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
                }`}
              >
                {status === "all" ? "All Status" : status}
              </motion.button>
            ))}
          </div>

          {/* Export Button */}
          <div className="flex justify-end">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-semibold rounded-lg hover:bg-emerald-700 transition-all"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* Audit Logs Table */}
      <motion.div variants={itemVariants}>
        {loading ? (
          <ChartSkeleton />
        ) : (
          <div className="glass rounded-2xl overflow-hidden border border-zinc-200/50">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-linear-to-r from-zinc-50 to-white border-b border-zinc-200/50">
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Transaction ID
                    </th>
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Action
                    </th>
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Status
                    </th>
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Risk Score
                    </th>
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Timestamp
                    </th>
                    <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase">
                      Audit Hash
                    </th>
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
                          className="hover:bg-zinc-50/50 transition-colors border-b border-zinc-100 last:border-b-0"
                        >
                          <td className="px-6 py-4">
                            <code className="text-xs font-mono text-zinc-600 font-semibold">
                              {log.transactionId.slice(0, 8)}...
                            </code>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm font-medium text-zinc-900">{log.action}</span>
                          </td>
                          <td className="px-6 py-4">
                            <StatusBadge status={log.status} />
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 w-12 bg-zinc-100 rounded-full overflow-hidden">
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${log.riskScore}%` }}
                                  transition={{ duration: 0.5, delay: idx * 0.03 }}
                                  className={`h-full rounded-full ${
                                    log.riskScore > 70
                                      ? "bg-red-500"
                                      : log.riskScore > 30
                                      ? "bg-amber-500"
                                      : "bg-emerald-500"
                                  }`}
                                />
                              </div>
                              <span className="text-xs font-bold text-zinc-600 w-8 text-right">
                                {log.riskScore}%
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-xs text-zinc-500 font-mono">
                              {new Date(log.timestamp).toLocaleDateString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <a
                              href="#"
                              className="text-xs font-mono text-blue-600 hover:text-blue-700 font-semibold"
                            >
                              {log.auditHash.slice(0, 8)}...
                            </a>
                          </td>
                        </motion.tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="px-6 py-12 text-center">
                          <div className="text-zinc-500">
                            <p className="text-sm font-medium">No audit logs found</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </motion.div>

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-between"
        >
          <div className="text-sm text-zinc-600">
            Page <span className="font-bold">{currentPage}</span> of{" "}
            <span className="font-bold">{totalPages}</span>
          </div>
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-700 font-semibold hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </motion.button>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  color: string;
}

function StatCard({ icon, title, value, color }: StatCardProps) {
  const bgColor = {
    emerald: "bg-emerald-50",
    blue: "bg-blue-50",
    amber: "bg-amber-50",
  };

  const iconColor = {
    emerald: "text-emerald-600",
    blue: "text-blue-600",
    amber: "text-amber-600",
  };

  return (
    <motion.div
      whileHover={{ y: -5 }}
      className={`${bgColor[color as keyof typeof bgColor]} rounded-2xl p-6 border border-zinc-200/50`}
    >
      <div className={`w-12 h-12 rounded-lg bg-white/60 flex items-center justify-center ${
        iconColor[color as keyof typeof iconColor]
      }`}>
        {icon}
      </div>
      <p className="text-sm font-medium text-zinc-600 uppercase tracking-wide mt-4">{title}</p>
      <p className="text-3xl font-bold text-zinc-900 mt-2">{value}</p>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles = {
    success: "bg-emerald-100 text-emerald-700 border-emerald-300/50",
    failed: "bg-red-100 text-red-700 border-red-300/50",
    pending: "bg-amber-100 text-amber-700 border-amber-300/50",
  };

  return (
    <motion.span
      whileHover={{ scale: 1.1 }}
      className={`px-3 py-1 rounded-lg text-[10px] font-bold tracking-tight uppercase inline-block border ${
        styles[status as keyof typeof styles] || styles.pending
      }`}
    >
      {status}
    </motion.span>
  );
}
