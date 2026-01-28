"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Mail, Lock, User, ArrowRight, Zap, Shield, TrendingUp } from "lucide-react";
import Link from "next/link";
import { signup, signin } from "@/lib/api";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      let res;
      if (isLogin) {
        res = await signin({ email, password });
      } else {
        res = await signup({ email, password, name: fullName });
      }
      const token = res?.token;
      if (typeof window !== "undefined" && token) {
        localStorage.setItem("sf_token", token);
      }
      // Redirect to dashboard
      window.location.href = "/";
    } catch (err: any) {
      const msg = err?.message || "Authentication failed";
      alert(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-b from-slate-950 via-slate-950 to-black flex items-center justify-center p-4 overflow-hidden relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute -top-40 -right-40 w-80 h-80 bg-linear-to-br from-cyan-500 via-purple-500 to-pink-500 rounded-full opacity-20 blur-3xl"
          animate={{
            x: [0, 100, 0],
            y: [0, -100, 0],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "linear",
          }}
        />
        <motion.div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-linear-to-tr from-blue-500 via-purple-500 to-cyan-500 rounded-full opacity-20 blur-3xl"
          animate={{
            x: [0, -100, 0],
            y: [0, 100, 0],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      </div>

      {/* Main Container */}
      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-8 relative z-10">
        {/* Left Side - Features */}
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
            <p className="text-xl text-slate-400">
              Real-time fraud detection powered by AI
            </p>
          </div>

          {/* Features */}
          <div className="space-y-6">
            {[
              {
                icon: Zap,
                title: "Real-time Detection",
                desc: "Detect fraud instantly with AI",
              },
              {
                icon: Shield,
                title: "Blockchain Audit",
                desc: "Immutable audit trails",
              },
              {
                icon: TrendingUp,
                title: "Advanced Analytics",
                desc: "Deep insights and trends",
              },
            ].map((feature, i) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -30 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.1 }}
                  className="flex gap-4 group cursor-pointer"
                >
                    <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-linear-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center group-hover:from-cyan-500/40 group-hover:to-purple-500/40 transition-all">
                    <Icon className="w-6 h-6 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white group-hover:text-cyan-400 transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-slate-400">{feature.desc}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>

        {/* Right Side - Auth Form */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8 }}
        >
          <div className="relative">
            {/* Glow Background */}
            <div className="absolute inset-0 bg-linear-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition" />

            {/* Card */}
            <div className="relative bg-slate-900/80 backdrop-blur-xl border border-purple-500/20 rounded-2xl p-8 space-y-6">
              {/* Tabs */}
              <div className="flex gap-4 border-b border-purple-500/10 -mx-8 px-8 pb-6">
                {["Login", "Sign Up"].map((tab) => (
                  <motion.button
                    key={tab}
                    onClick={() => setIsLogin(tab === "Login")}
                    className="relative pb-2 font-semibold text-sm transition-colors"
                  >
                    {(isLogin && tab === "Login") ||
                    (!isLogin && tab === "Sign Up") ? (
                      <>
                        <span className="text-white">{tab}</span>
                        <motion.div
                          layoutId="authTab"
                          className="absolute bottom-0 left-0 right-0 h-1 bg-linear-to-r from-cyan-400 to-purple-400"
                          initial={false}
                          transition={{ type: "spring", stiffness: 380, damping: 30 }}
                        />
                      </>
                    ) : (
                      <span className="text-slate-400 hover:text-slate-300">{tab}</span>
                    )}
                  </motion.button>
                ))}
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Full Name - Only for Sign Up */}
                {!isLogin && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-2"
                  >
                    <label className="text-sm font-medium text-slate-300">
                      Full Name
                    </label>
                    <div className="relative group">
                      <User className="absolute left-3 top-3 w-5 h-5 text-purple-400/50 group-focus-within:text-cyan-400 transition-colors" />
                      <input
                        type="text"
                        placeholder="John Doe"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-purple-500/20 rounded-lg focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 transition-all text-white placeholder-slate-500"
                      />
                    </div>
                  </motion.div>
                )}

                {/* Email */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">
                    Email Address
                  </label>
                  <div className="relative group">
                    <Mail className="absolute left-3 top-3 w-5 h-5 text-purple-400/50 group-focus-within:text-cyan-400 transition-colors" />
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-purple-500/20 rounded-lg focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 transition-all text-white placeholder-slate-500"
                      required
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">
                    Password
                  </label>
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

                {/* Remember & Forgot */}
                {isLogin && (
                  <div className="flex items-center justify-between text-sm">
                    <label className="flex items-center gap-2 cursor-pointer group">
                      <input
                        type="checkbox"
                        className="w-4 h-4 bg-slate-800 border border-purple-500/20 rounded accent-cyan-500"
                      />
                      <span className="text-slate-400 group-hover:text-slate-300">
                        Remember me
                      </span>
                    </label>
                    <Link
                      href="#"
                      className="text-cyan-400 hover:text-cyan-300 transition-colors"
                    >
                      Forgot password?
                    </Link>
                  </div>
                )}

                {/* Submit Button */}
                <motion.button
                  type="submit"
                  disabled={isLoading}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full mt-6 h-12 rounded-lg font-semibold relative overflow-hidden group"
                >
                  <div className="absolute inset-0 bg-linear-to-r from-cyan-500 via-purple-500 to-pink-500 group-hover:from-cyan-400 group-hover:via-purple-400 group-hover:to-pink-400 transition-all" />
                  <div className="absolute inset-0.5 bg-slate-900 rounded-lg flex items-center justify-center gap-2 group-hover:bg-slate-900/50 transition-all">
                    <span className="text-white font-semibold">
                      {isLoading
                        ? "Loading..."
                        : isLogin
                          ? "Login"
                          : "Create Account"}
                    </span>
                    {!isLoading && (
                      <motion.div
                        animate={{ x: [0, 4, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        <ArrowRight className="w-4 h-4 text-cyan-400" />
                      </motion.div>
                    )}
                  </div>
                </motion.button>
              </form>

              {/* Divider */}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-purple-500/10" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-slate-900/80 text-slate-400">
                    or continue with
                  </span>
                </div>
              </div>

              {/* Social Buttons */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { icon: "G", label: "Google" },
                  { icon: "G", label: "GitHub" },
                ].map((social) => (
                  <motion.button
                    key={social.label}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                    className="py-2 px-3 rounded-lg border border-purple-500/20 hover:border-purple-500/40 bg-slate-800/30 hover:bg-slate-800/60 text-slate-300 hover:text-white transition-all font-medium text-sm"
                  >
                    {social.label}
                  </motion.button>
                ))}
              </div>

              {/* Footer Text */}
              <p className="text-center text-sm text-slate-400">
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <motion.button
                  onClick={() => setIsLogin(!isLogin)}
                  className="text-cyan-400 hover:text-cyan-300 font-semibold transition-colors"
                >
                  {isLogin ? "Sign up" : "Log in"}
                </motion.button>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
