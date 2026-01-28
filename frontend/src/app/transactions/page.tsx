"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { fetchTransactions } from "@/lib/api";
import { Transaction } from "@/types/transaction";
import TransactionList from "@/components/TransactionList";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { useToast } from "@/components/Toast";
import { Plus } from "lucide-react";

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const { show } = useToast();

  useEffect(() => {
    const loadTransactions = async () => {
      try {
        setLoading(true);
        const data = await fetchTransactions({ take: 100 });
        setTransactions(data);
      } catch (error) {
        console.error("Error loading transactions:", error);
        show("Error", "Failed to load transactions", "error");
      } finally {
        setLoading(false);
      }
    };

    loadTransactions();
  }, [show]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: "easeOut" },
    },
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-zinc-900 to-zinc-700 bg-clip-text text-transparent">
            Transactions
          </h1>
          <p className="text-zinc-600 text-base mt-2">
            View and manage all your blockchain transactions with real-time monitoring.
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-all shadow-lg"
        >
          <Plus className="w-5 h-5" />
          New Transaction
        </motion.button>
      </motion.div>

      {/* Stats Cards */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Total Transactions"
          value={transactions.length.toString()}
          change="This month"
          color="blue"
        />
        <StatCard
          title="Flagged"
          value={transactions.filter((t) => t.status === "FLAGGED").length.toString()}
          change="Need review"
          color="amber"
        />
        <StatCard
          title="Success Rate"
          value={`${(
            (transactions.filter((t) => t.status === "APPROVED").length / transactions.length) *
            100
          ).toFixed(1)}%`}
          change="Last 30 days"
          color="emerald"
        />
      </motion.div>

      {/* Transactions List */}
      <motion.div variants={itemVariants}>
        {loading ? (
          <div className="space-y-4">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        ) : transactions.length > 0 ? (
          <TransactionList transactions={transactions} />
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass rounded-2xl p-12 border border-zinc-200/50 text-center"
          >
            <div className="text-zinc-500">
              <p className="text-lg font-medium">No transactions found</p>
              <p className="text-sm mt-1">Create your first transaction to get started</p>
            </div>
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  change: string;
  color: "blue" | "amber" | "emerald";
}

function StatCard({ title, value, change, color }: StatCardProps) {
  const colors = {
    blue: "bg-blue-50",
    amber: "bg-amber-50",
    emerald: "bg-emerald-50",
  };

  const textColors = {
    blue: "text-blue-600",
    amber: "text-amber-600",
    emerald: "text-emerald-600",
  };

  return (
    <motion.div
      whileHover={{ y: -5 }}
      className={`${colors[color]} rounded-2xl p-6 border border-zinc-200/50`}
    >
      <p className="text-sm font-medium text-zinc-600 uppercase tracking-wide">{title}</p>
      <p className="text-3xl font-bold text-zinc-900 mt-2">{value}</p>
      <p className={`text-xs font-medium mt-3 ${textColors[color]}`}>{change}</p>
    </motion.div>
  );
}
