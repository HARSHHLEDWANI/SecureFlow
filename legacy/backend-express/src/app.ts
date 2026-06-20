import express from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import cookieParser from "cookie-parser";
import { rateLimit } from "express-rate-limit";

import authRoutes from "./routes/auth.routes";
import transactionRoutes from "./routes/transactions.routes";
import auditRoutes from "./routes/audit.routes";
import dashboardRoutes from "./routes/dashboard.routes";
import settingsRoutes from "./routes/settings.routes";
import { errorHandler } from "./middleware/errorHandler";

const app = express();

const allowedOrigins = [
  "http://localhost:3000",
  process.env.FRONTEND_URL,
].filter(Boolean) as string[];

app.use(
  cors({
    origin: (origin, cb) => {
      if (!origin || allowedOrigins.includes(origin)) return cb(null, true);
      cb(new Error("CORS: origin not allowed"));
    },
    credentials: true,
  })
);

app.use(helmet());
app.use(morgan(process.env.NODE_ENV === "production" ? "combined" : "dev"));
app.use(express.json());
app.use(cookieParser());

const isTest = process.env.NODE_ENV === "test";

const generalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: isTest ? 10000 : 100,
  standardHeaders: true,
  legacyHeaders: false,
});

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: isTest ? 10000 : 5,
  standardHeaders: true,
  legacyHeaders: false,
});

app.use(generalLimiter);

app.get("/api/health", (_req, res) => {
  res.json({
    success: true,
    data: { status: "ok", timestamp: new Date().toISOString(), version: "1.0.0" },
    error: null,
  });
});

app.use("/api/auth", authLimiter, authRoutes);
app.use("/api/transactions", transactionRoutes);
app.use("/api/audit", auditRoutes);
app.use("/api/dashboard", dashboardRoutes);
app.use("/api/settings", settingsRoutes);

app.use(errorHandler);

export default app;
