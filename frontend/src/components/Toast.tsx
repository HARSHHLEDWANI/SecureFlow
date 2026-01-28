"use client";
import { motion, AnimatePresence } from "framer-motion";
import { X, AlertCircle, CheckCircle2, Info } from "lucide-react";
import { useState, useCallback, useEffect } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

let toastId = 0;
const toastListeners = new Set<(toast: ToastMessage) => void>();

export function useToast() {
  const show = useCallback(
    (
      title: string,
      message?: string,
      type: ToastType = "info",
      duration = 3000
    ) => {
      const id = String(toastId++);
      const toast: ToastMessage = { id, type, title, message };

      toastListeners.forEach((listener) => listener(toast));

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }

      return id;
    },
    []
  );

  return { show };
}

function removeToast(id: string) {
  toastListeners.forEach((listener) => listener({ id, type: "info", title: "" }));
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: ToastMessage) => {
    if (!toast.title) {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id));
    } else {
      setToasts((prev) => {
        const exists = prev.find((t) => t.id === toast.id);
        return exists ? prev : [...prev, toast];
      });
    }
  }, []);

  const removeFromList = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Register listener
  useEffect(() => {
    toastListeners.add(addToast);
    return () => {
      toastListeners.delete(addToast);
    };
  }, [addToast]);

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            {...toast}
            onClose={() => removeFromList(toast.id)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

function Toast({
  id,
  type,
  title,
  message,
  onClose,
}: ToastMessage & { onClose: () => void }) {
  const colors = {
    success: {
      bg: "bg-emerald-50 border-emerald-200/50",
      icon: CheckCircle2,
      iconColor: "text-emerald-600",
      titleColor: "text-emerald-900",
    },
    error: {
      bg: "bg-red-50 border-red-200/50",
      icon: AlertCircle,
      iconColor: "text-red-600",
      titleColor: "text-red-900",
    },
    warning: {
      bg: "bg-amber-50 border-amber-200/50",
      icon: AlertCircle,
      iconColor: "text-amber-600",
      titleColor: "text-amber-900",
    },
    info: {
      bg: "bg-blue-50 border-blue-200/50",
      icon: Info,
      iconColor: "text-blue-600",
      titleColor: "text-blue-900",
    },
  };

  const config = colors[type];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className={`glass rounded-lg p-4 border ${config.bg} flex items-start gap-3 pointer-events-auto max-w-sm`}
    >
      <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${config.iconColor}`} />
      <div className="flex-1">
        <p className={`font-semibold text-sm ${config.titleColor}`}>{title}</p>
        {message && <p className="text-xs text-zinc-600 mt-1">{message}</p>}
      </div>
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        onClick={onClose}
        className="shrink-0 text-zinc-400 hover:text-zinc-600 transition-colors"
      >
        <X className="w-4 h-4" />
      </motion.button>
    </motion.div>
  );
}
