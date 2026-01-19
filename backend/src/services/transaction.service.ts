import * as repo from "../repositories/transaction.repo";
import { CreateTransactionInput } from "../types/transaction";
import { getFraudRiskSafe } from "../lib/aiClient";
import { decideTransaction } from "../utils/decision";

export const createTransaction = async (
  data: CreateTransactionInput
) => {
  const fraudResult = await getFraudRiskSafe(data);

  // AI unavailable → safe fallback
  if (!fraudResult) {
    return repo.create({
      ...data,
      status: "FLAGGED",
    });
  }

  // AI available → normal decision
  const decision = decideTransaction(fraudResult.risk_score);

  return repo.create({
    ...data,
    riskScore: fraudResult.risk_score,
    status: decision,
  });
};

export const getAllTransactions = async () => {
  return repo.findAll();
};
