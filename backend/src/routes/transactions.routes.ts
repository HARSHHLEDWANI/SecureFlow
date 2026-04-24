import { Router } from "express";
import { z } from "zod";
import { validate } from "../middleware/validate";
import { requireAuth, requireRole } from "../middleware/auth";
import * as ctrl from "../controllers/transactions.controller";

const router = Router();

const WALLET_RE = /^0x[a-fA-F0-9]{40}$/;

const createSchema = z.object({
  fromWallet: z.string().regex(WALLET_RE, "Invalid Ethereum wallet address"),
  toWallet: z.string().regex(WALLET_RE, "Invalid Ethereum wallet address"),
  amount: z.number().positive("Amount must be positive"),
  currency: z.enum(["USD", "ETH", "USDC"]),
});

const statusSchema = z.object({
  status: z.enum(["PENDING", "APPROVED", "FLAGGED", "REJECTED"]),
});

router.use(requireAuth);
router.get("/", ctrl.list);
router.post("/", validate(createSchema), ctrl.create);
router.get("/:id", ctrl.getById);
router.put("/:id/status", requireRole("ADMIN"), validate(statusSchema), ctrl.updateStatus);

export default router;
