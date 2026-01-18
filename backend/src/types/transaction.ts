import { z } from "zod";

export const createTransactionSchema = z.object({
  fromWallet: z.string().min(1),
  toWallet: z.string().min(1),
  amount: z.number().positive(),
  currency: z.string().min(1),
});

export type CreateTransactionInput = z.infer<
  typeof createTransactionSchema
>;
