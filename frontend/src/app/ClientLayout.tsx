"use client";

import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  LogOut,
  Bell,
  Menu,
  X,
  Home,
  CreditCard,
  FileText,
  Cog,
  ChevronRight,
} from "lucide-react";
import { ToastContainer } from "@/components/Toast";
import { useState } from "react";

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [hoveredNav, setHoveredNav] = useState<string | null>(null);

  const navItems = [
    { href: "/", label: "Dashboard", icon: Home },
    { href: "/transactions", label: "Transactions", icon: CreditCard },
    { href: "/audit", label: "Audit Logs", icon: FileText },
    { href: "/settings", label: "Settings", icon: Cog },
  ];

  return (
    <div className="flex min-h-screen bg-slate-950">
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            initial={{ x: -300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -300, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed left-0 top-0 z-50 h-screen w-72 flex flex-col"
          >
            <div className="absolute inset-0 bg-linear-to-br from-slate-900 via-slate-950 to-black border-r border-purple-500/20" />
            <div className="relative z-10 flex flex-col h-full p-6">
              {/* Logo */}
              <div className="flex items-center gap-3 mb-12">
                <div className="w-10 h-10 rounded-xl bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">SecureFlow</h1>
                  <p className="text-xs text-purple-400/60">Fraud Detection</p>
                </div>
              </div>

              {/* Nav */}
              <nav className="flex-1 space-y-3">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isHovered = hoveredNav === item.href;

                  return (
                    <div
                      key={item.href}
                      onMouseEnter={() => setHoveredNav(item.href)}
                      onMouseLeave={() => setHoveredNav(null)}
                    >
                      <Link href={item.href}>
                        <div className="relative px-4 py-3 rounded-xl flex items-center gap-3 hover:bg-purple-500/10 transition">
                          <Icon className="w-5 h-5 text-purple-400" />
                          <span className="text-slate-300">{item.label}</span>
                          {isHovered && (
                            <ChevronRight className="ml-auto w-4 h-4 text-cyan-400" />
                          )}
                        </div>
                      </Link>
                    </div>
                  );
                })}
              </nav>

              {/* Bottom */}
              <div className="border-t border-purple-500/10 pt-6 space-y-3">
                <button className="w-full px-4 py-3 rounded-xl flex items-center gap-3 text-slate-300 hover:bg-purple-500/10">
                  <Bell className="w-5 h-5 text-purple-400" />
                  Notifications
                </button>
                <button className="w-full px-4 py-3 rounded-xl flex items-center gap-3 text-red-400 hover:bg-red-500/10">
                  <LogOut className="w-5 h-5" />
                  Sign Out
                </button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main */}
      <main
        className={`flex-1 flex flex-col transition-all duration-300 ${
          sidebarOpen ? "ml-72" : "ml-0"
        }`}
      >
        {/* Header */}
        <header className="h-20 border-b border-purple-500/10 backdrop-blur bg-slate-950/80 flex items-center justify-between px-8">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg border border-purple-500/10 hover:bg-purple-500/20"
          >
            {sidebarOpen ? (
              <X className="w-5 h-5 text-purple-400" />
            ) : (
              <Menu className="w-5 h-5 text-purple-400" />
            )}
          </button>

          <div className="flex items-center gap-2 text-sm">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-400">Live Monitoring</span>
          </div>

          <div className="w-10 h-10 rounded-full bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 flex items-center justify-center">
            <span className="text-white font-bold text-sm">U</span>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-8 max-w-7xl mx-auto w-full">
          {children}
        </div>
      </main>

      <ToastContainer />
    </div>
  );
}
