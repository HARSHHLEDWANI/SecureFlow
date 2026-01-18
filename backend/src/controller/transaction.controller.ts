import { Request, Response, NextFunction } from "express";
import { createTransactionSchema } from "../types/transaction";
import * as service from "../services/transaction.service";

export const createTransaction = async (
  req: Request,
  res: Response,
  next: NextFunction
) => {
  try {
    const tx = await service.createTransaction(req.body);
    res.status(201).json(tx);
  } catch (err) {
    next(err);
  }
};

export const getTransactions = async (
  _: Request,
  res: Response,
  next: NextFunction
) => {
  try {
    const txs = await service.getAllTransactions();
    res.json(txs);
  } catch (err) {
    next(err);
  }
};
