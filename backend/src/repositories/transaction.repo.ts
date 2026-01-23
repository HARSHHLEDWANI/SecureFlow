import { prisma } from "../lib/prisma";

export const create = async (data: {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
  riskScore?: number;
  status: "APPROVED" | "FLAGGED" | "REJECTED";
}) => {
  return prisma.transaction.create({
    data: {
      fromWallet: data.fromWallet,
      toWallet: data.toWallet,
      amount: data.amount,
      currency: data.currency,
      riskScore: data.riskScore,
      status: data.status,
    },
  });
};
export const update = async (
  id: string,
  data: {
    auditTxHash?: string;
    auditedAt?: Date;
  }
) => {
  return prisma.transaction.update({
    where: { id },
    data,
  });
};

export const findAll = async () => {
  return prisma.transaction.findMany({
    orderBy: { createdAt: "desc" },
  });
};
