import express from "express";
import cors from "cors";
// import transactionRoutes from "./routes/transaction.routes";
import { errorHandler } from "./middleware/error.middleware";
import authRoutes from "./routes/auth.routes";


const app = express();

app.use(cors());
app.use(express.json());

// Temporarily disable transaction routes that need Prisma
// app.use("/api/transactions", transactionRoutes);

// Auth routes (signup / login / me)
app.use("/api/auth", authRoutes);

// Dashboard stats endpoint
app.get("/api/dashboard/stats", (req, res) => {
  res.json({
    totalTransactions: 12842,
    flaggedTransactions: 18,
    averageRiskScore: 24.1,
    totalAudited: 12842,
  });
});

// Mock transactions endpoint
app.get("/api/transactions", (req, res) => {
  res.json([
    {
      id: "tx-1",
      fromWallet: "0x1234567890abcdef",
      toWallet: "0xfedcba0987654321",
      amount: 100.5,
      currency: "ETH",
      status: "APPROVED",
      riskScore: 15,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    {
      id: "tx-2",
      fromWallet: "0xabcdef1234567890",
      toWallet: "0x0987654321fedcba",
      amount: 250.0,
      currency: "ETH",
      status: "FLAGGED",
      riskScore: 68,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    {
      id: "tx-3",
      fromWallet: "0x1111111111111111",
      toWallet: "0x2222222222222222",
      amount: 50.25,
      currency: "ETH",
      status: "APPROVED",
      riskScore: 22,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  ]);
});

// Post transaction endpoint (mock)
app.post("/api/transactions", (req, res) => {
  const { fromWallet, toWallet, amount, currency } = req.body;
  
  if (!fromWallet || !toWallet || !amount || !currency) {
    return res.status(400).json({ error: "Missing required fields" });
  }
  
  res.status(201).json({
    id: `tx-${Date.now()}`,
    fromWallet,
    toWallet,
    amount,
    currency,
    status: "APPROVED",
    riskScore: 10,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
});

// Audit routes
app.get("/api/audit", (req, res) => {
  res.json([
    {
      id: "audit-1",
      transactionId: "tx-1",
      action: "Scanned",
      status: "success",
      riskScore: 15,
      timestamp: new Date().toISOString(),
      auditHash: "0x1234567890abcdef",
      details: "Transaction verified",
    },
    {
      id: "audit-2",
      transactionId: "tx-2",
      action: "Flagged",
      status: "pending",
      riskScore: 68,
      timestamp: new Date().toISOString(),
      auditHash: "0xfedcba0987654321",
      details: "High risk detected",
    },
  ]);
});

app.get("/api/audit/stats", (req, res) => {
  res.json({
    totalAudited: 12842,
    successRate: 98.5,
    averageLatency: 1.2,
  });
});

// Settings routes
app.get("/api/settings", (req, res) => {
  res.json({
    id: "user-1",
    email: "admin@secureflow.com",
    riskThreshold: 50,
    notificationsEnabled: true,
    twoFactorEnabled: false,
    apiKeys: ["sk_live_1234567890"],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
});

app.put("/api/settings", (req, res) => {
  res.json({
    id: "user-1",
    email: req.body.email || "admin@secureflow.com",
    riskThreshold: req.body.riskThreshold || 50,
    notificationsEnabled: req.body.notificationsEnabled ?? true,
    twoFactorEnabled: req.body.twoFactorEnabled ?? false,
    apiKeys: req.body.apiKeys || ["sk_live_1234567890"],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
});

app.post("/api/settings/api-keys", (req, res) => {
  res.json({
    key: `sk_live_${Math.random().toString(36).substring(2, 15)}`,
    createdAt: new Date().toISOString(),
  });
});

app.use(errorHandler);

export default app;
