import { prisma } from "../lib/prisma";

export const create = async (data: {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
}) => {
  return prisma.transaction.create({
    data: {
      fromWallet: data.fromWallet,
      toWallet: data.toWallet,
      amount: data.amount,
      currency: data.currency,
      status: "PENDING",
    },
  });
};

export const findAll = async () => {
  return prisma.transaction.findMany({
    orderBy: { createdAt: "desc" },
  });
};
