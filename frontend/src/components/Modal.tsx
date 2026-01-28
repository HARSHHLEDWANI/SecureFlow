"use client";
import { motion } from "framer-motion";
import { X } from "lucide-react";
import { ReactNode } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
}

export function Modal({ isOpen, onClose, title, children, size = "md" }: ModalProps) {
  const sizes = {
    sm: "max-w-md",
    md: "max-w-lg",
    lg: "max-w-2xl",
  };

  return (
    <>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
        />
      )}

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={isOpen ? { opacity: 1, scale: 1, y: 0 } : { opacity: 0, scale: 0.95, y: 20 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full ${sizes[size]} max-h-[90vh] overflow-y-auto z-50 ${
          isOpen ? "pointer-events-auto" : "pointer-events-none"
        }`}
      >
        <div className="glass rounded-2xl border border-zinc-200/50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-zinc-200/50">
            <h2 className="text-xl font-bold text-zinc-900">{title}</h2>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={onClose}
              className="p-2 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-zinc-600" />
            </motion.button>
          </div>

          {/* Content */}
          <div className="p-6">{children}</div>
        </div>
      </motion.div>
    </>
  );
}
