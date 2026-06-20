import { PrismaClient, Role, TxStatus } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

const wallets = [
  "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "0xab5801a7d398351b8be11c439e05c5b3259aec9b",
  "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
  "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
  "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",
  "0xFE9e8709d3215310075d67E3ed32A380CCf451C8",
  "0x220866B1A2219f40e72f5c628B65D54268cA3A9D",
  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
];

const currencies = ["USD", "ETH", "USDC"];

function randomBetween(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function randomElement<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomStatus(riskScore: number): TxStatus {
  if (riskScore >= 0.7) return TxStatus.REJECTED;
  if (riskScore >= 0.4) return TxStatus.FLAGGED;
  if (riskScore >= 0.2) return TxStatus.APPROVED;
  return TxStatus.APPROVED;
}

async function main() {
  console.log("Seeding database...");

  await prisma.auditLog.deleteMany();
  await prisma.apiKey.deleteMany();
  await prisma.transaction.deleteMany();
  await prisma.user.deleteMany();

  const passwordHash = await bcrypt.hash("SecureFlow123!", 12);

  const admin = await prisma.user.create({
    data: {
      email: "admin@secureflow.dev",
      passwordHash,
      role: Role.ADMIN,
    },
  });

  const analyst = await prisma.user.create({
    data: {
      email: "analyst@secureflow.dev",
      passwordHash,
      role: Role.ANALYST,
    },
  });

  console.log("Created users:", admin.email, analyst.email);

  const transactionData: Array<{
    fromWallet: string;
    toWallet: string;
    amount: number;
    currency: string;
    riskScore: number;
    confidence: number;
    aiExplanation: string;
    userId: string;
    daysAgo: number;
  }> = [
    {
      fromWallet: wallets[0],
      toWallet: wallets[1],
      amount: 150.0,
      currency: "USD",
      riskScore: 0.12,
      confidence: 0.91,
      aiExplanation: "Low-value transaction from established wallet. No anomalies detected.",
      userId: admin.id,
      daysAgo: 1,
    },
    {
      fromWallet: wallets[2],
      toWallet: wallets[3],
      amount: 10000.0,
      currency: "USD",
      riskScore: 0.78,
      confidence: 0.87,
      aiExplanation: "Large round-number transaction at unusual hour. High velocity from this wallet in the last hour.",
      userId: admin.id,
      daysAgo: 1,
    },
    {
      fromWallet: wallets[4],
      toWallet: wallets[5],
      amount: 0.5,
      currency: "ETH",
      riskScore: 0.35,
      confidence: 0.74,
      aiExplanation: "Cross-currency transaction with moderate wallet entropy. Flagged for review.",
      userId: analyst.id,
      daysAgo: 2,
    },
    {
      fromWallet: wallets[1],
      toWallet: wallets[6],
      amount: 25000.0,
      currency: "USDC",
      riskScore: 0.92,
      confidence: 0.95,
      aiExplanation: "Extremely large transaction from low-entropy wallet address. Multiple red flags: round number, off-hours, new wallet.",
      userId: admin.id,
      daysAgo: 2,
    },
    {
      fromWallet: wallets[6],
      toWallet: wallets[0],
      amount: 89.99,
      currency: "USD",
      riskScore: 0.08,
      confidence: 0.96,
      aiExplanation: "Normal transaction pattern. Amount and timing consistent with legitimate use.",
      userId: analyst.id,
      daysAgo: 3,
    },
    {
      fromWallet: wallets[3],
      toWallet: wallets[7],
      amount: 5000.0,
      currency: "USD",
      riskScore: 0.65,
      confidence: 0.82,
      aiExplanation: "Round-number large transfer. Wallet has 6 outbound transactions in the last 10 minutes (velocity flag).",
      userId: admin.id,
      daysAgo: 3,
    },
    {
      fromWallet: wallets[7],
      toWallet: wallets[2],
      amount: 1.25,
      currency: "ETH",
      riskScore: 0.19,
      confidence: 0.88,
      aiExplanation: "ETH transfer within normal range. Wallet activity looks legitimate.",
      userId: analyst.id,
      daysAgo: 4,
    },
    {
      fromWallet: wallets[5],
      toWallet: wallets[4],
      amount: 0.001,
      currency: "ETH",
      riskScore: 0.41,
      confidence: 0.69,
      aiExplanation: "Micro-transaction flagged. Could be wallet probing or dust attack.",
      userId: admin.id,
      daysAgo: 4,
    },
    {
      fromWallet: wallets[0],
      toWallet: wallets[3],
      amount: 320.5,
      currency: "USDC",
      riskScore: 0.15,
      confidence: 0.93,
      aiExplanation: "Standard USDC transfer. No anomalies detected.",
      userId: analyst.id,
      daysAgo: 5,
    },
    {
      fromWallet: wallets[2],
      toWallet: wallets[6],
      amount: 100000.0,
      currency: "USD",
      riskScore: 0.97,
      confidence: 0.99,
      aiExplanation: "CRITICAL: Extremely large round-number transaction. Wallet entropy extremely low. High velocity. Off-hours activity. All fraud indicators present.",
      userId: admin.id,
      daysAgo: 5,
    },
    {
      fromWallet: wallets[4],
      toWallet: wallets[1],
      amount: 750.0,
      currency: "USD",
      riskScore: 0.22,
      confidence: 0.85,
      aiExplanation: "Moderate transaction. Timing and amount consistent with normal patterns.",
      userId: analyst.id,
      daysAgo: 6,
    },
    {
      fromWallet: wallets[6],
      toWallet: wallets[5],
      amount: 2.0,
      currency: "ETH",
      riskScore: 0.55,
      confidence: 0.77,
      aiExplanation: "Round ETH amount. Unusual hour. Moderate risk — manual review recommended.",
      userId: admin.id,
      daysAgo: 6,
    },
    {
      fromWallet: wallets[7],
      toWallet: wallets[0],
      amount: 50.0,
      currency: "USDC",
      riskScore: 0.09,
      confidence: 0.97,
      aiExplanation: "Small USDC transfer from known wallet. Low risk.",
      userId: analyst.id,
      daysAgo: 7,
    },
    {
      fromWallet: wallets[1],
      toWallet: wallets[4],
      amount: 3000.0,
      currency: "USD",
      riskScore: 0.71,
      confidence: 0.84,
      aiExplanation: "Large transaction. Sender wallet has suspicious entropy pattern. Recommend hold.",
      userId: admin.id,
      daysAgo: 7,
    },
    {
      fromWallet: wallets[3],
      toWallet: wallets[2],
      amount: 14.75,
      currency: "ETH",
      riskScore: 0.33,
      confidence: 0.79,
      aiExplanation: "Large ETH value but non-round amount. Weekend transaction. Borderline risk.",
      userId: analyst.id,
      daysAgo: 8,
    },
    {
      fromWallet: wallets[5],
      toWallet: wallets[7],
      amount: 200.0,
      currency: "USD",
      riskScore: 0.18,
      confidence: 0.91,
      aiExplanation: "Low-risk transfer. Normal amount and timing.",
      userId: admin.id,
      daysAgo: 9,
    },
    {
      fromWallet: wallets[0],
      toWallet: wallets[6],
      amount: 0.05,
      currency: "ETH",
      riskScore: 0.44,
      confidence: 0.72,
      aiExplanation: "Micro ETH transaction. Could be gas fee test or probing.",
      userId: analyst.id,
      daysAgo: 10,
    },
    {
      fromWallet: wallets[2],
      toWallet: wallets[7],
      amount: 8500.0,
      currency: "USDC",
      riskScore: 0.68,
      confidence: 0.81,
      aiExplanation: "High-value USDC transfer. Round-number amount, multiple transactions from this wallet today.",
      userId: admin.id,
      daysAgo: 11,
    },
    {
      fromWallet: wallets[4],
      toWallet: wallets[0],
      amount: 99.0,
      currency: "USD",
      riskScore: 0.11,
      confidence: 0.94,
      aiExplanation: "Low-risk just-below-round-number transaction. Common in legitimate e-commerce.",
      userId: analyst.id,
      daysAgo: 12,
    },
    {
      fromWallet: wallets[6],
      toWallet: wallets[3],
      amount: 50000.0,
      currency: "USDC",
      riskScore: 0.89,
      confidence: 0.93,
      aiExplanation: "Very large round-number USDC transfer. New wallet (low historical activity). Suspicious cross-chain pattern detected.",
      userId: admin.id,
      daysAgo: 13,
    },
  ];

  for (const txData of transactionData) {
    const { daysAgo, userId, ...txFields } = txData;
    const createdAt = new Date();
    createdAt.setDate(createdAt.getDate() - daysAgo);
    createdAt.setHours(Math.floor(Math.random() * 24));

    const status = randomStatus(txFields.riskScore);

    const tx = await prisma.transaction.create({
      data: {
        ...txFields,
        amount: txFields.amount,
        status,
        auditTxHash: status !== TxStatus.PENDING
          ? `0x${Math.random().toString(16).slice(2).padEnd(64, "0")}`
          : null,
        userId,
        createdAt,
        updatedAt: createdAt,
      },
    });

    const actorId = status === TxStatus.APPROVED || status === TxStatus.REJECTED
      ? admin.id
      : analyst.id;

    await prisma.auditLog.create({
      data: {
        transactionId: tx.id,
        action: status === TxStatus.REJECTED
          ? "REJECTED"
          : status === TxStatus.FLAGGED
          ? "FLAGGED"
          : "APPROVED",
        actorId,
        riskScore: txFields.riskScore,
        blockchainHash: tx.auditTxHash,
        metadata: {
          currency: txFields.currency,
          amount: txFields.amount,
          confidence: txFields.confidence,
        },
        createdAt,
      },
    });
  }

  console.log(`Created ${transactionData.length} transactions with audit logs`);
  console.log("\nSeed complete. Credentials:");
  console.log("  admin@secureflow.dev   / SecureFlow123!");
  console.log("  analyst@secureflow.dev / SecureFlow123!");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
