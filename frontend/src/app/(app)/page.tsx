"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Radio } from "lucide-react";
import { api } from "@/lib/api";
import type { Alert, DashboardStats, TransactionSummary } from "@/lib/types";
import { formatDateTime, formatINR, formatNumber, tierColor } from "@/lib/format";
import { useAlertStream } from "@/hooks/useWebSocket";
import { EmptyState, Panel, Skeleton, StatCard, TierBadge } from "@/components/ui";

const CHART_AXIS = { fontSize: 11, fill: "var(--text-dim)" };

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<TransactionSummary[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const { alerts: liveAlerts, state: wsState } = useAlertStream();

  const load = useCallback(async () => {
    try {
      const [s, t, a] = await Promise.all([
        api.dashboard(),
        api.transactions({ limit: 8 }),
        api.recentAlerts(8),
      ]);
      setStats(s);
      setRecent(t);
      setRecentAlerts(a);
    } catch {
      /* surfaced via empty states */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [load]);

  const mergedAlerts = [...liveAlerts, ...recentAlerts].slice(0, 10);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Fraud Monitoring</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Real-time UPI transaction risk overview
          </p>
        </div>
        <span className="inline-flex items-center gap-2 panel-2 px-3 py-1.5 text-xs">
          <Radio
            className="h-3.5 w-3.5"
            style={{ color: wsState === "open" ? "var(--success)" : "var(--text-dim)" }}
          />
          {wsState === "open" ? "Live" : wsState === "connecting" ? "Connecting…" : "Offline"}
        </span>
      </header>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <StatCard label="Transactions analyzed" value={formatNumber(stats.total_transactions)} />
            <StatCard
              label="Fraud detected"
              value={formatNumber(stats.fraud_detected)}
              accent="var(--danger)"
              sub={`${(stats.fraud_rate * 100).toFixed(1)}% of volume`}
            />
            <StatCard
              label="Avg risk score"
              value={stats.average_risk_score.toFixed(1)}
              accent="var(--warning)"
            />
            <StatCard
              label="Blocked / Step-up"
              value={`${stats.blocked_count} / ${stats.step_up_count}`}
              accent="var(--accent-cyan)"
            />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Risk score distribution" className="lg:col-span-2">
          {stats ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={stats.risk_score_histogram}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="range" tick={CHART_AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={CHART_AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: "var(--surface-2)" }}
                  contentStyle={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {stats.risk_score_histogram.map((_, i) => (
                    <Cell
                      key={i}
                      fill={i < 3 ? "var(--success)" : i < 7 ? "var(--warning)" : "var(--danger)"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Skeleton className="h-60" />
          )}
        </Panel>

        <Panel title="Live fraud alerts">
          <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
            {mergedAlerts.length === 0 ? (
              <EmptyState title="No alerts yet" hint="High-risk transactions appear here in real time." />
            ) : (
              mergedAlerts.map((a, i) => (
                <div
                  key={`${a.transaction_id}-${i}`}
                  className="panel-2 flex items-center justify-between p-2.5 animate-fade-up"
                >
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium">{a.to_vpa}</p>
                    <p className="text-[10px] text-[var(--text-dim)]">{formatINR(a.amount_inr)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold" style={{ color: tierColor(a.risk_tier) }}>
                      {a.risk_score}
                    </span>
                    <TierBadge tier={a.risk_tier} />
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Daily transaction volume (7d)" className="lg:col-span-2">
          {stats ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={stats.daily_volume}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={CHART_AXIS}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(d: string) => d.slice(5)}
                />
                <YAxis tick={CHART_AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "var(--accent)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Skeleton className="h-56" />
          )}
        </Panel>

        <Panel title="Recent transactions">
          <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
            {recent.length === 0 ? (
              <EmptyState title="No transactions yet" hint="Analyze one to get started." />
            ) : (
              recent.map((t) => (
                <div key={t.id} className="panel-2 flex items-center justify-between p-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium">{t.to_vpa}</p>
                    <p className="text-[10px] text-[var(--text-dim)]">{formatDateTime(t.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--text-muted)]">{formatINR(t.amount_inr)}</span>
                    <TierBadge tier={t.risk_tier} />
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>

      <p className="flex items-center gap-1.5 text-[11px] text-[var(--text-dim)]">
        <Activity className="h-3 w-3" /> Auto-refreshing every 6 seconds.
      </p>
    </div>
  );
}
