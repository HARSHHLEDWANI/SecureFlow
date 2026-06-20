import { Request, Response, NextFunction } from "express";
import { TxStatus } from "@prisma/client";
import * as txService from "../services/transactions.service";

export async function create(req: Request, res: Response, next: NextFunction) {
  try {
    const { fromWallet, toWallet, amount, currency } = req.body;
    const tx = await txService.createTransaction(
      req.user!.userId,
      fromWallet,
      toWallet,
      Number(amount),
      currency
    );
    res.status(201).json({ success: true, data: tx, error: null });
  } catch (err) {
    next(err);
  }
}

export async function list(req: Request, res: Response, next: NextFunction) {
  try {
    const limit = Math.min(Number(req.query.limit ?? 20), 100);
    const cursor = req.query.cursor as string | undefined;
    const status = req.query.status
      ? (String(req.query.status) as TxStatus)
      : undefined;
    const currency = req.query.currency
      ? String(req.query.currency)
      : undefined;

    const result = await txService.listTransactions({ cursor, limit, status, currency });
    res.json({
      success: true,
      data: result.items,
      error: null,
      meta: { nextCursor: result.nextCursor, hasMore: result.hasMore, limit },
    });
  } catch (err) {
    next(err);
  }
}

export async function getById(req: Request, res: Response, next: NextFunction) {
  try {
    const tx = await txService.getTransactionById(String(req.params.id));
    res.json({ success: true, data: tx, error: null });
  } catch (err) {
    next(err);
  }
}

export async function updateStatus(req: Request, res: Response, next: NextFunction) {
  try {
    const status = req.body.status as TxStatus;
    const tx = await txService.updateTransactionStatus(
      String(req.params.id),
      status,
      req.user!.userId
    );
    res.json({ success: true, data: tx, error: null });
  } catch (err) {
    next(err);
  }
}
