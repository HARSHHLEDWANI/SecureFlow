"use client";

import { useState } from "react";
import { createTransaction } from "@/lib/api";
import { refreshTransactions } from "@/app/actions";

export function CreateTransactionForm() {
  const [fromWallet, setFromWallet] = useState("");
  const [toWallet, setToWallet] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
        await createTransaction({
            fromWallet,
            toWallet,
            amount: Number(amount),
            currency,
        });
        await refreshTransactions();

      // reset form
      setFromWallet("");
      setToWallet("");
      setAmount("");
    } catch (err) {
      setError("Failed to create transaction");
    } finally {
      setLoading(false);   
    }
  }


  return (
    <form
      onSubmit={handleSubmit}
      className="border rounded-lg p-4 space-y-4 mb-8"
    >
      <h2 className="text-lg font-semibold">
        Create Transaction
      </h2>

      <div className="space-y-2">
        <input
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="From wallet"
          value={fromWallet}
          onChange={(e) => setFromWallet(e.target.value)}
          required
        />

        <input
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="To wallet"
          value={toWallet}
          onChange={(e) => setToWallet(e.target.value)}
          required
        />

        <input
          type="number"
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />

        <input
          className="w-full border rounded px-3 py-2 text-sm"
          placeholder="Currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          required
        />
      </div>

      {error && (
        <div className="text-sm text-red-600">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="bg-black text-white text-sm px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Submitting..." : "Create"}
      </button>
    </form>
  );
}
