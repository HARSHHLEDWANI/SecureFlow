"use client";

import "./globals.css";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { BarChart3, LogOut, Settings, Bell, Menu, X, Home, CreditCard, FileText, Cog, ChevronRight } from "lucide-react";
import { ToastContainer } from "@/components/Toast";
import { useState } from "react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [hoveredNav, setHoveredNav] = useState<string | null>(null);

  const navItems = [
    { href: "/", label: "Dashboard", icon: Home },
    { href: "/transactions", label: "Transactions", icon: CreditCard },
    { href: "/audit", label: "Audit Logs", icon: FileText },
    { href: "/settings", label: "Settings", icon: Cog },
  ];

  return (
    <html lang="en">
      <body className="flex min-h-screen bg-slate-950">
        {/* Modern Sidebar */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.aside
              initial={{ x: -300, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -300, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="fixed left-0 top-0 h-screen w-72 z-50 flex flex-col"
            >
              {/* Gradient Background */}
              <div className="absolute inset-0 bg-linear-to-br from-slate-900 via-slate-950 to-black border-r border-purple-500/20" />
              <div className="absolute inset-0 bg-linear-to-t from-purple-500/5 via-transparent to-blue-500/5 pointer-events-none" />

              {/* Content */}
              <div className="relative z-10 flex flex-col h-full p-6">
                {/* Logo */}
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 mb-12 cursor-pointer group"
                >
                  <div className="relative w-10 h-10">
                    <div className="absolute inset-0 bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 rounded-xl blur-lg opacity-75 group-hover:opacity-100 transition-opacity" />
                    <div className="relative w-full h-full bg-slate-900 rounded-xl flex items-center justify-center overflow-hidden">
                      <BarChart3 className="w-6 h-6 text-white group-hover:scale-110 transition-transform" />
                    </div>
                  </div>
                  <div>
                    <h1 className="text-xl font-bold bg-linear-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                      SecureFlow
                    </h1>
                    <p className="text-xs text-purple-400/60">Fraud Detection</p>
                  </div>
                </motion.div>

                {/* Navigation */}
                <nav className="flex-1 space-y-3">
                  {navItems.map((item, i) => {
                    const Icon = item.icon;
                    const isHovered = hoveredNav === item.href;

                    return (
                      <motion.div
                        key={item.href}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                        onMouseEnter={() => setHoveredNav(item.href)}
                        onMouseLeave={() => setHoveredNav(null)}
                      >
                        <Link href={item.href}>
                          <div className="relative group cursor-pointer">
                            {/* Hover Background */}
                            {isHovered && (
                              <motion.div
                                layoutId="navHover"
                                className="absolute inset-0 bg-linear-to-r from-purple-500/20 via-cyan-500/10 to-transparent rounded-xl blur-md"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                              />
                            )}

                            {/* Item Container */}
                            <div className="relative px-4 py-3 rounded-xl flex items-center gap-3 transition-all border border-transparent group-hover:border-purple-500/30">
                              <div className={`transition-all ${isHovered ? "text-cyan-400" : "text-purple-400/60"}`}>
                                <Icon className="w-5 h-5" />
                              </div>
                              <span className={`font-medium transition-all ${isHovered ? "text-white" : "text-slate-300"}`}>
                                {item.label}
                              </span>
                              {isHovered && (
                                <motion.div
                                  initial={{ x: -8, opacity: 0 }}
                                  animate={{ x: 0, opacity: 1 }}
                                  className="ml-auto text-cyan-400"
                                >
                                  <ChevronRight className="w-4 h-4" />
                                </motion.div>
                              )}
                            </div>
                          </div>
                        </Link>
                      </motion.div>
                    );
                  })}
                </nav>

                {/* Bottom Actions */}
                <motion.div className="space-y-3 border-t border-purple-500/10 pt-6">
                  <button className="w-full px-4 py-3 rounded-xl flex items-center gap-3 group text-slate-300 hover:text-white transition-all border border-purple-500/10 hover:border-purple-500/30 hover:bg-purple-500/10">
                    <Bell className="w-5 h-5 text-purple-400/60 group-hover:text-cyan-400 transition-colors" />
                    <span className="font-medium flex-1 text-left">Notifications</span>
                    <span className="bg-linear-to-r from-pink-500 to-red-500 text-white text-xs rounded-full px-2 py-0.5">
                      3
                    </span>
                  </button>
                  <button className="w-full px-4 py-3 rounded-xl flex items-center gap-3 group text-slate-300 hover:text-white transition-all border border-red-500/10 hover:border-red-500/30 hover:bg-red-500/10">
                    <LogOut className="w-5 h-5 text-red-400/60 group-hover:text-red-400 transition-colors" />
                    <span className="font-medium">Sign Out</span>
                  </button>
                </motion.div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Main Content */}
        <main className={`flex-1 flex flex-col transition-all duration-300 ${sidebarOpen ? "ml-72" : "ml-0"}`}>
          {/* Header */}
          <header className="sticky top-0 z-40 h-20 border-b border-purple-500/10 backdrop-blur-xl bg-slate-950/80">
            <div className="h-full flex items-center justify-between px-8">
              {/* Toggle Button */}
              <motion.button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 hover:bg-purple-500/20 rounded-lg transition-all border border-purple-500/10 hover:border-purple-500/30"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                {sidebarOpen ? (
                  <X className="w-5 h-5 text-purple-400" />
                ) : (
                  <Menu className="w-5 h-5 text-purple-400" />
                )}
              </motion.button>

              {/* Status */}
              <motion.div className="flex items-center gap-2 text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-linear-to-r from-cyan-400 to-emerald-400 animate-pulse shadow-lg shadow-cyan-500/50" />
                <span className="text-slate-400">Live Monitoring</span>
              </motion.div>

              {/* Right Actions */}
              <div className="flex items-center gap-4">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="p-2 hover:bg-purple-500/20 rounded-lg transition-all border border-purple-500/10 hover:border-purple-500/30"
                >
                  <Bell className="w-5 h-5 text-purple-400/60 hover:text-cyan-400 transition-colors" />
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.1 }}
                  className="relative w-10 h-10 rounded-full overflow-hidden"
                >
                  <div className="absolute inset-0 bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 opacity-80" />
                  <div className="absolute inset-1 bg-slate-900 rounded-full flex items-center justify-center">
                    <span className="text-white font-bold text-sm">U</span>
                  </div>
                </motion.button>
              </div>
            </div>
          </header>

          {/* Content Area */}
          <div className="flex-1 overflow-y-auto bg-linear-to-b from-slate-950 via-slate-950 to-black">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="p-8 max-w-7xl mx-auto"
            >
              {children}
            </motion.div>
          </div>
        </main>

        {/* Toast Container */}
        <ToastContainer />
      </body>
    </html>
  );
}