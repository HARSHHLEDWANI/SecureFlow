import { Router } from "express";
import { createTransaction, getTransactions } from "../controller/transaction.controller";

const router = Router();

router.post("/", createTransaction);
router.get("/", getTransactions);

export default router;
