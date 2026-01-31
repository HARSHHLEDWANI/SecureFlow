"use client";
import { Transaction } from "@/types/transaction";
import { motion, AnimatePresence } from "framer-motion";
import { useState, useMemo } from "react";
import { Search, Filter, ChevronUp, ChevronDown } from "lucide-react";

interface Props {
  transactions: Transaction[];
}

type SortKey = "date" | "amount" | "risk";
type SortOrder = "asc" | "desc";

export default function TransactionList({ transactions }: Props) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Filter and sort transactions
  const filteredTransactions = useMemo(() => {
    let filtered = transactions.filter((tx) => {
      const matchesSearch =
        tx.fromWallet.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tx.toWallet.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tx.id.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus = statusFilter === "all" || tx.status === statusFilter;

      return matchesSearch && matchesStatus;
    });

    // Sort
    filtered.sort((a, b) => {
      let aVal: any, bVal: any;

      switch (sortKey) {
        case "date":
          aVal = new Date(a.createdAt).getTime();
          bVal = new Date(b.createdAt).getTime();
          break;
        case "amount":
          aVal = a.amount;
          bVal = b.amount;
          break;
        case "risk":
          aVal = a.riskScore || 0;
          bVal = b.riskScore || 0;
          break;
      }

      return sortOrder === "asc" ? aVal - bVal : bVal - aVal;
    });

    return filtered;
  }, [transactions, searchTerm, statusFilter, sortKey, sortOrder]);

  // Pagination
  const totalPages = Math.ceil(filteredTransactions.length / itemsPerPage);
  const startIdx = (currentPage - 1) * itemsPerPage;
  const paginatedTransactions = filteredTransactions.slice(
    startIdx,
    startIdx + itemsPerPage
  );

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  const SortHeader = ({ label, sortKey: key }: { label: string; sortKey: SortKey }) => (
    <button
      onClick={() => handleSort(key)}
      className="flex items-center gap-1 hover:text-zinc-700 transition-colors group"
    >
      {label}
      {sortKey === key && (
        <span className="text-blue-600">
          {sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      )}
    </button>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Filter and Search Bar */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-4 border border-zinc-200/50 space-y-4"
      >
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
          <input
            type="text"
            placeholder="Search by wallet address or transaction ID..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full pl-10 pr-4 py-2.5 bg-white/60 border border-zinc-200/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-transparent transition-all"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          {["all", "APPROVED", "FLAGGED", "REJECTED", "PENDING"].map((status) => (
            <motion.button
              key={status}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                setStatusFilter(status);
                setCurrentPage(1);
              }}
              className={`px-4 py-1.5 rounded-lg font-semibold text-sm transition-all ${
                statusFilter === status
                  ? "bg-blue-600 text-white shadow-lg"
                  : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
            >
              {status === "all" ? "All Status" : status}
            </motion.button>
          ))}
        </div>

        {/* Results count */}
        <div className="text-sm text-zinc-600">
          Found <span className="font-bold text-zinc-900">{filteredTransactions.length}</span> transaction
          {filteredTransactions.length !== 1 ? "s" : ""}
        </div>
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="glass rounded-2xl overflow-hidden border border-zinc-200/50"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-linear-to-r from-zinc-50 to-white border-b border-zinc-200/50">
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider">
                  From / To
                </th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider cursor-pointer hover:text-blue-600">
                  <SortHeader label="Amount" sortKey="amount" />
                </th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider cursor-pointer hover:text-blue-600">
                  <SortHeader label="Risk" sortKey="risk" />
                </th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider cursor-pointer hover:text-blue-600">
                  <SortHeader label="Date" sortKey="date" />
                </th>
                <th className="px-6 py-4 text-xs font-semibold text-zinc-700 uppercase tracking-wider">
                  Proof
                </th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence mode="wait">
                {paginatedTransactions.length > 0 ? (
                  paginatedTransactions.map((tx, idx) => (
                    <motion.tr
                      key={tx.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ delay: idx * 0.03 }}
                      className="hover:bg-zinc-50/50 transition-colors border-b border-zinc-100 last:border-b-0 cursor-pointer group"
                    >
                      <td className="px-6 py-4">
                        <StatusTag status={tx.status} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1">
                          <code className="text-xs font-mono text-zinc-600 truncate w-40 hover:text-blue-600 group-hover:text-blue-600 transition-colors">
                            {tx.fromWallet}
                          </code>
                          <code className="text-[10px] text-zinc-400 font-mono">→ {tx.toWallet.slice(0, 20)}...</code>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-semibold text-zinc-900">
                          {tx.amount.toLocaleString()} <span className="text-xs text-zinc-500">{tx.currency}</span>
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 w-16 bg-zinc-100 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${tx.riskScore}%` }}
                              transition={{ duration: 0.5, delay: idx * 0.03 }}
                              className={`h-full rounded-full ${
                                tx.riskScore! > 70
                                  ? "bg-red-500"
                                  : tx.riskScore! > 30
                                  ? "bg-amber-500"
                                  : "bg-emerald-500"
                              }`}
                            />
                          </div>
                          <span className={`text-xs font-bold w-8 text-right ${
                            tx.riskScore! > 70
                              ? "text-red-600"
                              : tx.riskScore! > 30
                              ? "text-amber-600"
                              : "text-emerald-600"
                          }`}>
                            {tx.riskScore}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs text-zinc-500 font-mono">
                          {new Date(tx.createdAt).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {tx.auditTxHash ? (
                          <a
                            href="#"
                            className="text-xs font-mono text-blue-600 hover:text-blue-700 font-semibold transition-colors"
                          >
                            {tx.auditTxHash.slice(0, 8)}...
                          </a>
                        ) : (
                          <span className="text-xs text-zinc-400">—</span>
                        )}
                      </td>
                    </motion.tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center">
                      <div className="text-zinc-500">
                        <p className="text-sm font-medium">No transactions found</p>
                        <p className="text-xs mt-1">Try adjusting your search filters</p>
                      </div>
                    </td>
                  </tr>
                )}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-between"
        >
          <div className="text-sm text-zinc-600">
            Page <span className="font-bold">{currentPage}</span> of <span className="font-bold">{totalPages}</span>
          </div>
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-700 font-semibold hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Previous
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Next
            </motion.button>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

function StatusTag({ status }: { status: Transaction["status"] }) {
  const styles = {
    APPROVED: "bg-emerald-100 text-emerald-700 border border-emerald-300/50",
    FLAGGED: "bg-amber-100 text-amber-700 border border-amber-300/50",
    REJECTED: "bg-red-100 text-red-700 border border-red-300/50",
    PENDING: "bg-zinc-100 text-zinc-600 border border-zinc-300/50",
  };

  return (
    <motion.span
      whileHover={{ scale: 1.1 }}
      className={`px-3 py-1 rounded-lg text-[10px] font-bold tracking-tight uppercase inline-block ${styles[status]}`}
    >
      {status}
    </motion.span>
  );
}