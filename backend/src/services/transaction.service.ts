import * as repo from "../repositories/transaction.repo";

export const createTransaction = async (data: any) => {
  // Later: AI risk check + blockchain logic
  return repo.create(data);
};

export const getAllTransactions = async () => {
  return repo.findAll();
};
