// Display formatting helpers.
import type { RiskTier } from "./types";

export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n);
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortHash(hash: string | null, len = 10): string {
  if (!hash) return "—";
  return hash.length > len * 2 ? `${hash.slice(0, len)}…${hash.slice(-6)}` : hash;
}

export const TIER_META: Record<RiskTier, { label: string; className: string; dot: string }> = {
  LOW: { label: "Low risk", className: "tier-low", dot: "var(--success)" },
  MEDIUM: { label: "Medium risk", className: "tier-medium", dot: "var(--warning)" },
  HIGH: { label: "High risk", className: "tier-high", dot: "var(--danger)" },
};

export function tierColor(tier: RiskTier): string {
  return tier === "HIGH"
    ? "var(--danger)"
    : tier === "MEDIUM"
      ? "var(--warning)"
      : "var(--success)";
}
