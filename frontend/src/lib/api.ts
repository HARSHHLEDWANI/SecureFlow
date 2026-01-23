import { Transaction } from "@/types/transaction";
const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL;


if (!BASE_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not defined");
}





export async function fetchTransactions(): Promise<Transaction[]> {
  const res = await fetch(`${BASE_URL}/transactions`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to fetch transactions");
  }

  return res.json();
}

export async function createTransaction(data: {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
}) {
  const res = await fetch(`${BASE_URL}/transactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error("Failed to create transaction");
  }

  return res.json();
}
