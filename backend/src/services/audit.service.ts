import { Prisma } from "@prisma/client";
import { prisma } from "../lib/prisma";

export async function listAuditLogs(params: {
  cursor?: string;
  limit: number;
  action?: string;
}) {
  const { cursor, limit, action } = params;

  const where: Prisma.AuditLogWhereInput = {};
  if (action) where.action = { contains: action, mode: "insensitive" };
  if (cursor) where.createdAt = { lt: new Date(cursor) };

  const items = await prisma.auditLog.findMany({
    where,
    take: limit + 1,
    orderBy: { createdAt: "desc" },
    include: {
      actor: { select: { email: true, role: true } },
      transaction: { select: { fromWallet: true, toWallet: true, amount: true, currency: true } },
    },
  });

  const hasMore = items.length > limit;
  const results = hasMore ? items.slice(0, limit) : items;
  const nextCursor = hasMore
    ? results[results.length - 1].createdAt.toISOString()
    : null;

  return { items: results, nextCursor, hasMore };
}

export async function getAuditStats() {
  const breakdown = await prisma.auditLog.groupBy({
    by: ["action"],
    _count: { id: true },
  });

  return {
    total: breakdown.reduce((s, b) => s + b._count.id, 0),
    byAction: Object.fromEntries(breakdown.map((b) => [b.action, b._count.id])),
  };
}
