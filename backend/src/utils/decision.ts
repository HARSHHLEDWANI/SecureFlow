export type TransactionDecision =
  | "APPROVED"
  | "FLAGGED"
  | "REJECTED";

export const decideTransaction = (
  riskScore: number
): TransactionDecision => {
  if (riskScore < 0.3) return "APPROVED";
  if (riskScore < 0.7) return "FLAGGED";
  return "REJECTED";
};
