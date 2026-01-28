"use client";
import { motion } from "framer-motion";

export function CardSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="glass rounded-2xl p-6 border border-zinc-200/50"
    >
      <div className="space-y-4">
        <div className="h-4 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded-full w-2/3 animate-pulse" />
        <div className="h-8 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded-full w-3/4 animate-pulse" />
        <div className="h-3 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded-full w-full animate-pulse" />
        <div className="h-3 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded-full w-5/6 animate-pulse" />
      </div>
    </motion.div>
  );
}

export function TableRowSkeleton() {
  return (
    <tr className="border-b border-zinc-100">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <td key={i} className="px-6 py-4">
          <div className="h-4 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  );
}

export function ChartSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="glass rounded-2xl p-6 border border-zinc-200/50"
    >
      <div className="h-6 bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200 rounded-full w-1/3 mb-6 animate-pulse" />
      <div className="h-64 bg-gradient-to-r from-zinc-100 via-zinc-50 to-zinc-100 rounded-lg animate-pulse" />
    </motion.div>
  );
}
