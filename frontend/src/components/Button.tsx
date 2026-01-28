"use client";
import { motion } from "framer-motion";
import { ReactNode } from "react";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  onClick,
  className = "",
}: ButtonProps) {
  const baseStyles = "font-semibold rounded-lg transition-all flex items-center justify-center gap-2";

  const variants = {
    primary: "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-400",
    secondary: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200 disabled:bg-zinc-50",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400",
    outline:
      "border border-zinc-300 text-zinc-900 hover:bg-zinc-50 disabled:opacity-50",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };

  return (
    <motion.button
      whileHover={{ scale: disabled ? 1 : 1.05 }}
      whileTap={{ scale: disabled ? 1 : 0.95 }}
      disabled={disabled || isLoading}
      onClick={onClick}
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {isLoading ? (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity }}
          className="w-4 h-4 border-2 border-current border-t-transparent rounded-full"
        />
      ) : null}
      {children}
    </motion.button>
  );
}
