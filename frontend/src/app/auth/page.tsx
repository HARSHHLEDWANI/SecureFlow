"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Mail, Lock, ArrowRight, Zap, Shield, TrendingUp } from "lucide-react";
import { useAuth } from "@/context/auth";

export default function AuthPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError((err as Error).message || "Invalid credentials");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-b from-slate-950 via-slate-950 to-black flex items-center justify-center p-4 overflow-hidden relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute -top-40 -right-40 w-80 h-80 bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 rounded-full opacity-20 blur-3xl"
          animate={{ x: [0, 100, 0], y: [0, -100, 0] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-linear-to-tr from-blue-500 via-purple-500 to-cyan-500 rounded-full opacity-20 blur-3xl"
          animate={{ x: [0, -100, 0], y: [0, 100, 0] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-8 relative z-10">
        <motion.div
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8 }}
          className="hidden lg:flex flex-col justify-center space-y-8"
        >
          <div>
            <h1 className="text-5xl font-bold mb-4 bg-linear-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              SecureFlow
            </h1>
            <p className="text-xl text-slate-400">Real-time fraud detection powered by AI</p>
          </div>
          <div className="space-y-6">
            {[
              { icon: Zap, title: "Real-time Detection", desc: "Detect fraud instantly with ML scoring" },
              { icon: Shield, title: "Blockchain Audit", desc: "Immutable on-chain audit trails on Sepolia" },
              { icon: TrendingUp, title: "Advanced Analytics", desc: "7-day volume trends and risk breakdowns" },
            ].map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.1 }}
                className="flex gap-4"
              >
                <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-linear-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center">
                  <feature.icon className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white">{feature.title}</h3>
                  <p className="text-sm text-slate-400">{feature.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8 }}
        >
          <div className="relative">
            <div className="absolute inset-0 bg-linear-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-2xl blur opacity-20" />
            <div className="relative bg-slate-900/80 backdrop-blur-xl border border-purple-500/20 rounded-2xl p-8 space-y-6">
              <div className="pb-4 border-b border-purple-500/10">
                <h2 className="text-2xl font-bold text-white">Sign in</h2>
                <p className="text-sm text-slate-400 mt-1">Use your SecureFlow credentials</p>
              </div>

              {error && (
                <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">Email Address</label>
                  <div className="relative group">
                    <Mail className="absolute left-3 top-3 w-5 h-5 text-purple-400/50 group-focus-within:text-cyan-400 transition-colors" />
                    <input
                      type="email"
                      placeholder="admin@secureflow.dev"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-purple-500/20 rounded-lg focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 transition-all text-white placeholder-slate-500"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">Password</label>
                  <div className="relative group">
                    <Lock className="absolute left-3 top-3 w-5 h-5 text-purple-400/50 group-focus-within:text-cyan-400 transition-colors" />
                    <input
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-purple-500/20 rounded-lg focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 transition-all text-white placeholder-slate-500"
                      required
                    />
                  </div>
                </div>

                <motion.button
                  type="submit"
                  disabled={isLoading}
                  whileHover={{ scale: isLoading ? 1 : 1.02 }}
                  whileTap={{ scale: isLoading ? 1 : 0.98 }}
                  className="w-full mt-6 h-12 rounded-lg font-semibold relative overflow-hidden group disabled:opacity-60"
                >
                  <div className="absolute inset-0 bg-linear-to-r from-cyan-500 via-purple-500 to-pink-500 group-hover:from-cyan-400 group-hover:via-purple-400 group-hover:to-pink-400 transition-all" />
                  <div className="absolute inset-0.5 bg-slate-900 rounded-lg flex items-center justify-center gap-2 group-hover:bg-slate-900/50 transition-all">
                    <span className="text-white font-semibold">
                      {isLoading ? "Signing in…" : "Sign In"}
                    </span>
                    {!isLoading && (
                      <motion.div animate={{ x: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity }}>
                        <ArrowRight className="w-4 h-4 text-cyan-400" />
                      </motion.div>
                    )}
                  </div>
                </motion.button>
              </form>

              <p className="text-center text-xs text-slate-500">
                Demo credentials: admin@secureflow.dev / SecureFlow123!
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
