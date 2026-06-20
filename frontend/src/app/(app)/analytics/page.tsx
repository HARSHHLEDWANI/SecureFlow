"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { ModelMetrics } from "@/lib/types";
import { EmptyState, Panel, Skeleton, StatCard } from "@/components/ui";

const CHART_AXIS = { fontSize: 11, fill: "var(--text-dim)" };

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .modelMetrics()
      .then(setMetrics)
      .catch(() => setMetrics(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (!metrics) {
    return (
      <Panel title="Model performance">
        <EmptyState
          title="Model metrics unavailable"
          hint="Train the model (python -m app.ml.training) to populate metrics."
        />
      </Panel>
    );
  }

  const cm = metrics.confusion_matrix;
  const topFeatures = metrics.feature_importance.slice(0, 10);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Model Analytics</h1>
        <p className="text-sm text-[var(--text-muted)]">
          RandomForest classifier v{metrics.version} · trained on {metrics.n_train.toLocaleString()}{" "}
          samples
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Accuracy" value={`${(metrics.accuracy * 100).toFixed(1)}%`} accent="var(--success)" />
        <StatCard label="Precision" value={`${(metrics.precision * 100).toFixed(1)}%`} accent="var(--accent)" />
        <StatCard label="Recall" value={`${(metrics.recall * 100).toFixed(1)}%`} accent="var(--warning)" />
        <StatCard label="AUC-ROC" value={metrics.auc_roc.toFixed(3)} accent="var(--accent-cyan)" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Feature importance" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={topFeatures} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" tick={CHART_AXIS} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="feature"
                tick={{ ...CHART_AXIS, fontSize: 10 }}
                width={120}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "var(--surface-2)" }}
                contentStyle={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="importance" fill="var(--accent)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Confusion matrix">
          <div className="grid grid-cols-2 gap-2 text-center">
            <Cell label="True legit" value={cm[0][0]} good />
            <Cell label="False fraud" value={cm[0][1]} />
            <Cell label="Missed fraud" value={cm[1][0]} />
            <Cell label="Caught fraud" value={cm[1][1]} good />
          </div>
          <div className="mt-4 space-y-1 text-xs text-[var(--text-dim)]">
            <p>F1 score: {(metrics.f1 * 100).toFixed(1)}%</p>
            <p>5-fold CV AUC: {metrics.cv_auc_mean.toFixed(3)}</p>
            <p>Test set: {metrics.n_test.toLocaleString()} transactions</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Cell({ label, value, good }: { label: string; value: number; good?: boolean }) {
  return (
    <div className="panel-2 p-4">
      <p className="text-2xl font-bold" style={{ color: good ? "var(--success)" : "var(--danger)" }}>
        {value}
      </p>
      <p className="mt-1 text-[11px] text-[var(--text-dim)]">{label}</p>
    </div>
  );
}
