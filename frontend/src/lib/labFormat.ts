// Display helpers specific to the UPI Lab.
import type { UpiDecision } from "./types";

export const DECISION_META: Record<
  UpiDecision,
  { label: string; color: string; bg: string; emoji: string }
> = {
  APPROVED: { label: "Approved", color: "var(--success)", bg: "rgba(46,160,67,0.14)", emoji: "✅" },
  STEP_UP: { label: "Step-up Auth", color: "var(--warning)", bg: "rgba(210,153,34,0.14)", emoji: "⚠️" },
  BLOCKED: { label: "Blocked", color: "var(--danger)", bg: "rgba(248,81,73,0.14)", emoji: "🚫" },
};

export const STAGE_LABELS: Record<string, string> = {
  initiated: "Transaction Initiated",
  validated: "Validating UPI",
  features_extracted: "Extracting Features",
  ml_prediction: "ML Analysis",
  risk_scored: "Risk Scoring",
  blockchain_logged: "Blockchain Logging",
  decision: "Decision",
};

// Common Indian bank UPI handles for the receiver autocomplete.
export const UPI_HANDLES = ["@ybl", "@paytm", "@oksbi", "@okaxis", "@okicici", "@okhdfc", "@upi", "@apl"];

export function upiDeepLink(pa: string, pn: string, am: number, tn?: string): string {
  const params = new URLSearchParams({ pa, pn, am: String(am), cu: "INR" });
  if (tn) params.set("tn", tn);
  return `upi://pay?${params.toString()}`;
}
