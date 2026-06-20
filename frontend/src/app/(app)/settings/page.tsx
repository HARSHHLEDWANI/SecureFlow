"use client";

import { useEffect, useState } from "react";
import { Database, Server, Cpu, Boxes, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { HealthStatus } from "@/lib/types";
import { Panel, Skeleton } from "@/components/ui";

const TIERS = [
  { tier: "LOW", range: "0 – 30", action: "Allow transaction", color: "var(--success)" },
  { tier: "MEDIUM", range: "31 – 70", action: "Step-up authentication (OTP)", color: "var(--warning)" },
  { tier: "HIGH", range: "71 – 100", action: "Block & raise fraud alert", color: "var(--danger)" },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Settings & System</h1>
        <p className="text-sm text-[var(--text-muted)]">Account, system health, and risk policy</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Account">
          {user ? (
            <dl className="space-y-3 text-sm">
              <Row label="Email" value={user.email} />
              <Row label="VPA" value={user.vpa} mono />
              <Row label="Role" value={user.role} />
              <Row label="Home city" value={user.home_city} />
            </dl>
          ) : (
            <Skeleton className="h-32" />
          )}
        </Panel>

        <Panel title="System health">
          {loading ? (
            <Skeleton className="h-32" />
          ) : !health ? (
            <p className="text-sm text-[var(--danger)]">Backend unreachable</p>
          ) : (
            <div className="space-y-2">
              <Health icon={Database} label="Database" ok={health.database} />
              <Health icon={Server} label="Redis cache" ok={health.redis} note={!health.redis ? "degraded — fallback active" : undefined} />
              <Health
                icon={Cpu}
                label="ML model"
                ok={health.model_loaded}
                note={health.model_version ? `v${health.model_version}` : "heuristic fallback"}
              />
              <Health icon={Boxes} label="Blockchain" ok={health.blockchain_blocks > 0} note={`${health.blockchain_blocks} blocks`} />
              <div className="flex items-center gap-2 pt-1 text-[11px] text-[var(--text-dim)]">
                <Activity className="h-3 w-3" /> API v{health.version}
              </div>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Risk policy (tiered response)">
        <div className="space-y-2">
          {TIERS.map((t) => (
            <div key={t.tier} className="panel-2 flex items-center justify-between p-3">
              <div className="flex items-center gap-3">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: t.color }} />
                <span className="text-sm font-semibold" style={{ color: t.color }}>
                  {t.tier}
                </span>
                <span className="text-xs text-[var(--text-dim)]">score {t.range}</span>
              </div>
              <span className="text-sm text-[var(--text-muted)]">{t.action}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-[var(--text-dim)]">
          Thresholds are enforced server-side by the composite risk engine.
        </p>
      </Panel>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
      <dt className="text-[var(--text-dim)]">{label}</dt>
      <dd className={mono ? "font-mono" : ""}>{value}</dd>
    </div>
  );
}

function Health({
  icon: Icon,
  label,
  ok,
  note,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  ok: boolean;
  note?: string;
}) {
  return (
    <div className="flex items-center justify-between panel-2 p-2.5">
      <span className="flex items-center gap-2 text-sm">
        <Icon className="h-4 w-4 text-[var(--text-muted)]" />
        {label}
      </span>
      <span className="flex items-center gap-2 text-xs">
        {note && <span className="text-[var(--text-dim)]">{note}</span>}
        <span
          className="h-2 w-2 rounded-full"
          style={{ background: ok ? "var(--success)" : "var(--warning)" }}
        />
      </span>
    </div>
  );
}
