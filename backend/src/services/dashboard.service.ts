import { prisma } from "../lib/prisma";

export async function getDashboardStats() {
  const [total, statusBreakdown, riskAgg, flagged] = await Promise.all([
    prisma.transaction.count(),
    prisma.transaction.groupBy({
      by: ["status"],
      _count: { id: true },
    }),
    prisma.transaction.aggregate({
      _avg: { riskScore: true },
      _sum: { amount: true },
    }),
    prisma.transaction.count({ where: { status: "FLAGGED" } }),
  ]);

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const recentTx = await prisma.transaction.findMany({
    where: { createdAt: { gte: sevenDaysAgo } },
    select: { createdAt: true, amount: true, currency: true },
    orderBy: { createdAt: "asc" },
  });

  const dailyVolume: Record<string, number> = {};
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    dailyVolume[d.toISOString().slice(0, 10)] = 0;
  }

  for (const tx of recentTx) {
    const day = tx.createdAt.toISOString().slice(0, 10);
    if (day in dailyVolume) {
      dailyVolume[day] += Number(tx.amount);
    }
  }

  const topRiskyWallets = await prisma.transaction.groupBy({
    by: ["fromWallet"],
    _avg: { riskScore: true },
    _count: { id: true },
    orderBy: { _avg: { riskScore: "desc" } },
    take: 5,
    having: { riskScore: { _avg: { gt: 0 } } },
  });

  return {
    totalTransactions: total,
    totalVolume: Number(riskAgg._sum.amount ?? 0),
    averageRiskScore: riskAgg._avg.riskScore ?? 0,
    flaggedCount: flagged,
    statusBreakdown: Object.fromEntries(
      statusBreakdown.map((s) => [s.status, s._count.id])
    ),
    dailyVolume: Object.entries(dailyVolume).map(([date, volume]) => ({
      date,
      volume,
    })),
    topRiskyWallets: topRiskyWallets.map((w) => ({
      wallet: w.fromWallet,
      avgRiskScore: w._avg.riskScore ?? 0,
      transactionCount: w._count.id,
    })),
  };
}
