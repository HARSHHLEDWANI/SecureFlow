"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Search } from "lucide-react";
import { useAuth } from "@/context/auth";
import { fetchAuditLogs, fetchAuditStats, AuditLog } from "@/lib/api";

const ETHERSCAN = "https://sepolia.etherscan.io/tx/";

const ACTION_COLORS: Record<string, string> = {
  APPROVED: "text-cyan-400",
  FLAGGED: "text-amber-400",
  REJECTED: "text-red-400",
  PENDING: "text-indigo-400",
};

export default function AuditPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<{ total: number; byAction: Record<string, number> } | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [dataLoading, setDataLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [user, loading, router]);

  const load = useCallback(
    async (cursor?: string) => {
      if (!user) return;
      try {
        const [logsRes, statsRes] = await Promise.all([
          fetchAuditLogs({ cursor, limit: 20, action: actionFilter || undefined }),
          cursor ? Promise.resolve(null) : fetchAuditStats(),
        ]);
        setLogs((prev) => (cursor ? [...prev, ...logsRes.items] : logsRes.items));
        setNextCursor(logsRes.meta?.nextCursor ?? null);
        setHasMore(logsRes.meta?.hasMore ?? false);
        if (statsRes) setStats(statsRes);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setDataLoading(false);
      }
    },
    [user, actionFilter]
  );

  useEffect(() => {
    setDataLoading(true);
    setLogs([]);
    load();
  }, [load]);

  const filtered = logs.filter(
    (log) =>
      !search ||
      log.transactionId.toLowerCase().includes(search.toLowerCase()) ||
      log.actor?.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
          <p className="text-slate-400 text-sm mt-1">Immutable record of every decision made</p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
            <p className="text-slate-400 text-xs mb-1">Total Audits</p>
            <p className="text-2xl font-bold text-white">{stats.total}</p>
          </div>
          {["APPROVED", "FLAGGED", "REJECTED"].map((action) => (
            <div key={action} className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-4">
              <p className="text-slate-400 text-xs mb-1">{action}</p>
              <p className={`text-2xl font-bold ${ACTION_COLORS[action] ?? "text-white"}`}>
                {stats.byAction[action] ?? 0}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by transaction ID or actor…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-800/60 border border-slate-700/40 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="py-2 px-3 bg-slate-800/60 border border-slate-700/40 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All actions</option>
          <option value="APPROVED">Approved</option>
          <option value="FLAGGED">Flagged</option>
          <option value="REJECTED">Rejected</option>
        </select>
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
          <p className="text-slate-500 text-sm p-8 text-center">No audit logs found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-700/40 bg-slate-900/40">
                  {["Action", "Transaction", "Actor", "Risk", "Blockchain Hash", "Time"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((log) => (
                  <tr key={log.id} className="border-b border-slate-800/30 hover:bg-slate-800/20">
                    <td className="px-4 py-3">
                      <span className={`font-semibold ${ACTION_COLORS[log.action] ?? "text-slate-300"}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300 text-xs">
                      {log.transactionId.slice(0, 12)}…
                    </td>
                    <td className="px-4 py-3 text-slate-300 text-xs">
                      {log.actor?.email ?? log.actorId.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3">
                      {log.riskScore != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 rounded-full bg-slate-700">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${log.riskScore * 100}%`,
                                background: log.riskScore > 0.7 ? "#ef4444" : log.riskScore > 0.4 ? "#f59e0b" : "#22d3ee",
                              }}
                            />
                          </div>
                          <span className="text-slate-300 text-xs">{(log.riskScore * 100).toFixed(0)}%</span>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {log.blockchainHash ? (
                        <a
                          href={`${ETHERSCAN}${log.blockchainHash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-xs font-mono"
                        >
                          {log.blockchainHash.slice(0, 10)}… <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : <span className="text-slate-600 text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {new Date(log.createdAt).toLocaleString()}
                    </td>
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
    </div>
  );
}
