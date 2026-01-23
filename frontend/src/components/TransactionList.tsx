import { Transaction } from "@/types/transaction";
import { TransactionCard } from "./TransactionCard";

export function TransactionList({
  transactions,
}: {
  transactions: Transaction[];
}) {
  if (transactions.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No transactions found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {transactions.map((tx) => (
        <TransactionCard key={tx.id} tx={tx} />
      ))}
    </div>
  );
}
