import * as repo from "../repositories/transaction.repo";
import { CreateTransactionInput } from "../types/transaction";
import { getFraudRiskSafe } from "../lib/aiClient";
import { decideTransaction } from "../utils/decision";
import { logAuditOnChain } from "../lib/blockchain";

export const createTransaction = async (
  data: CreateTransactionInput
) => {
  const fraudResult = await getFraudRiskSafe(data);

  let status: "APPROVED" | "FLAGGED" | "REJECTED";
  let riskScore: number | undefined = undefined;

  // AI unavailable → safe fallback
  if (!fraudResult) {
    status = "FLAGGED";
  } else {
    riskScore = fraudResult.risk_score;
    status = decideTransaction(riskScore);
  }

  // 1️⃣ Create transaction (authoritative)
  const transaction = await repo.create({
    ...data,
    riskScore,
    status,
  });
  const auditDecision =
    transaction.status === "APPROVED" ||
    transaction.status === "FLAGGED" ||
    transaction.status === "REJECTED"
      ? transaction.status
      : null;
  // 2️⃣ Best-effort blockchain audit
if (auditDecision) {
  try {
    const audit = await logAuditOnChain({
      transactionId: transaction.id,
      decision: auditDecision,
      riskScore: transaction.riskScore,
    });

    await repo.update(transaction.id, {
      auditTxHash: audit.txHash,
      auditedAt: new Date(),
    });
  } catch (err) {
    console.error("Blockchain audit failed:", err);
  }
}


  return transaction;
};

export const getAllTransactions = async () => {
  return repo.findAll();
};
