import { fetchTransactions } from "@/lib/api";
import { TransactionList } from "@/components/TransactionList";
import { CreateTransactionForm } from "@/components/CreateTransactionForm";

export default async function HomePage() {
  const transactions = await fetchTransactions();

  return (
    <main className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-6">
        SecureFlow Transactions
      </h1>

      <CreateTransactionForm />

      <TransactionList transactions={transactions} />
    </main>
  );
}
