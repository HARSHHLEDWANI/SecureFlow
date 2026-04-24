import { Prisma, TxStatus } from "@prisma/client";
import { prisma } from "../lib/prisma";
import { predictRisk } from "./ai.service";
import { logToBlockchain } from "./blockchain.service";
import { AppError } from "../middleware/errorHandler";
import { logger } from "../lib/logger";

const WALLET_RE = /^0x[a-fA-F0-9]{40}$/;

function decideStatus(riskScore: number, threshold: number): TxStatus {
  if (riskScore >= threshold) return TxStatus.FLAGGED;
  if (riskScore >= 0.7) return TxStatus.REJECTED;
  return TxStatus.APPROVED;
}

export async function createTransaction(
  userId: string,
  fromWallet: string,
  toWallet: string,
  amount: number,
  currency: string
) {
  if (!WALLET_RE.test(fromWallet)) throw new AppError(400, "Invalid fromWallet address");
  if (!WALLET_RE.test(toWallet)) throw new AppError(400, "Invalid toWallet address");

  const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000);
  const velocityCount = await prisma.transaction.count({
    where: { fromWallet, createdAt: { gte: tenMinutesAgo } },
  });

  const ai = await predictRisk(fromWallet, toWallet, amount, currency, velocityCount);

  const user = await prisma.user.findUnique({ where: { id: userId } });
  const riskThreshold = 0.4;

  const riskScore = ai?.risk_score ?? (velocityCount > 5 ? 0.75 : 0.5);
  const confidence = ai?.confidence ?? null;
  const aiExplanation = ai?.explanation ?? (ai === null ? "AI service unavailable" : null);

  const status = decideStatus(riskScore, riskThreshold);

  const tx = await prisma.transaction.create({
    data: {
      fromWallet,
      toWallet,
      amount: new Prisma.Decimal(amount),
      currency,
      status,
      riskScore,
      confidence,
      aiExplanation,
      userId,
    },
  });

  const auditLog = await prisma.auditLog.create({
    data: {
      transactionId: tx.id,
      action: status,
      actorId: userId,
      riskScore,
      metadata: { currency, amount, confidence, velocityCount },
    },
  });

  let auditTxHash: string | null = null;
  try {
    auditTxHash = await logToBlockchain(
      tx.id,
      fromWallet,
      toWallet,
      amount,
      riskScore,
      status
    );
    if (auditTxHash) {
      await prisma.transaction.update({
        where: { id: tx.id },
        data: { auditTxHash },
      });
      await prisma.auditLog.update({
        where: { id: auditLog.id },
        data: { blockchainHash: auditTxHash },
      });
    }
  } catch (err) {
    logger.error({ err }, "Blockchain step failed");
  }

  return { ...tx, auditTxHash };
}

export async function listTransactions(params: {
  cursor?: string;
  limit: number;
  status?: TxStatus;
  currency?: string;
}) {
  const { cursor, limit, status, currency } = params;

  const where: Prisma.TransactionWhereInput = {};
  if (status) where.status = status;
  if (currency) where.currency = currency;
  if (cursor) where.createdAt = { lt: new Date(cursor) };

  const items = await prisma.transaction.findMany({
    where,
    take: limit + 1,
    orderBy: { createdAt: "desc" },
    include: {
      user: { select: { email: true, role: true } },
    },
  });

  const hasMore = items.length > limit;
  const results = hasMore ? items.slice(0, limit) : items;
  const nextCursor = hasMore
    ? results[results.length - 1].createdAt.toISOString()
    : null;

  return { items: results, nextCursor, hasMore };
}

export async function getTransactionById(id: string) {
  const tx = await prisma.transaction.findUnique({
    where: { id },
    include: {
      auditLogs: { orderBy: { createdAt: "desc" } },
      user: { select: { email: true, role: true } },
    },
  });
  if (!tx) throw new AppError(404, "Transaction not found");
  return tx;
}

export async function updateTransactionStatus(
  id: string,
  status: TxStatus,
  actorId: string
) {
  const tx = await prisma.transaction.findUnique({ where: { id } });
  if (!tx) throw new AppError(404, "Transaction not found");

  const updated = await prisma.transaction.update({
    where: { id },
    data: { status },
  });

  await prisma.auditLog.create({
    data: {
      transactionId: id,
      action: `MANUAL_${status}`,
      actorId,
      riskScore: tx.riskScore ?? undefined,
      metadata: { previousStatus: tx.status, newStatus: status },
    },
  });

  return updated;
}
