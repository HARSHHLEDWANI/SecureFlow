import * as repo from "../repositories/transaction.repo";
import { CreateTransactionInput } from "../types/transaction";

export const createTransaction = async (
  data: CreateTransactionInput
) => {
  // Phase 4: AI fraud scoring goes here
  // Phase 5: Blockchain logging goes here

  return repo.create(data);
};

export const getAllTransactions = async () => {
  return repo.findAll();
};
