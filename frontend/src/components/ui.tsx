"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useReducedMotion } from "framer-motion";
import type { RiskTier } from "@/lib/types";
import { TIER_META } from "@/lib/format";

/** Animated count-up to a numeric target (snaps instantly for reduced-motion). */
export function CountUp({
  value,
  duration = 0.9,
  format,
}: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const dur = reduce ? 0 : duration;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = dur <= 0 ? 1 : Math.min((t - start) / (dur * 1000), 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(value * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduce]);

  return <>{format ? format(display) : Math.round(display).toLocaleString()}</>;
}

export function Panel({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`panel p-5 ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between mb-4">
          {title && <h2 className="text-sm font-semibold text-[var(--text)]">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  sub,
  accent = "var(--accent)",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: string;
}) {
  return (
    <div className="panel p-5 animate-fade-up">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: accent }} />
        <span className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</span>
      </div>
      <div className="mt-3 text-2xl font-bold text-[var(--text)]">{value}</div>
      {sub && <div className="mt-1 text-xs text-[var(--text-dim)]">{sub}</div>}
    </div>
  );
}

export function TierBadge({ tier }: { tier: RiskTier }) {
  const meta = TIER_META[tier];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold panel-2"
      style={{ color: meta.dot }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.dot }} />
      {tier}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-sm text-[var(--text-muted)]">{title}</p>
      {hint && <p className="mt-1 text-xs text-[var(--text-dim)]">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-sm text-[var(--danger)]">{message}</p>
      {onRetry && (
        <button className="btn btn-ghost mt-3" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
