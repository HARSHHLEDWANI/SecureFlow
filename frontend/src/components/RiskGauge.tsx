"use client";

import type { RiskTier } from "@/lib/types";
import { tierColor } from "@/lib/format";

/** A semicircular 0–100 risk gauge coloured by tier. */
export default function RiskGauge({ score, tier }: { score: number; tier: RiskTier }) {
  const radius = 80;
  const circumference = Math.PI * radius; // semicircle
  const pct = Math.min(Math.max(score, 0), 100) / 100;
  const dash = circumference * pct;
  const color = tierColor(tier);

  return (
    <div className="relative flex flex-col items-center">
      <svg width="200" height="120" viewBox="0 0 200 120">
        <path
          d="M 20 110 A 80 80 0 0 1 180 110"
          fill="none"
          stroke="var(--border-strong)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 20 110 A 80 80 0 0 1 180 110"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.3s ease" }}
        />
      </svg>
      <div className="absolute bottom-0 flex flex-col items-center">
        <span className="text-4xl font-bold" style={{ color }}>
          {score}
        </span>
        <span className="text-xs text-[var(--text-dim)]">/ 100 risk score</span>
      </div>
    </div>
  );
}
