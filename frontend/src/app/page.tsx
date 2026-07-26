"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  ShieldCheck,
  ArrowRight,
  PlayCircle,
  Boxes,
  Cpu,
  Gauge,
  Radio,
  Landmark,
  ShieldAlert,
  Github,
  BookOpen,
  Layers,
  Database,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import RiskGauge from "@/components/RiskGauge";
import SmoothScroll from "@/components/landing/SmoothScroll";
import BlockchainCanvas from "@/components/landing/BlockchainCanvas";
import type { RiskTier } from "@/lib/types";

const REPO_URL = "https://github.com/HARSHHLEDWANI/SecureFlow";

// ── Small scroll-reveal wrapper ───────────────────────────────────────────────
// `initial`/`whileInView` are kept deterministic (identical on server + client) so
// there is no hydration mismatch. Reduced-motion is expressed via the transition
// (a 0-duration snap), which is client-only and never part of the SSR'd style —
// the server can't know the user's motion preference, so we must not branch the
// rendered markup on it.
function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={reduce ? { duration: 0 } : { duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

// ── Hero gauge that cycles through the three risk tiers ───────────────────────
const CYCLE: { score: number; tier: RiskTier; label: string }[] = [
  { score: 12, tier: "LOW", label: "ALLOW" },
  { score: 54, tier: "MEDIUM", label: "STEP-UP OTP" },
  { score: 91, tier: "HIGH", label: "BLOCK" },
];

function LiveGauge() {
  const [i, setI] = useState(0);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setI((v) => (v + 1) % CYCLE.length), 2600);
    return () => clearInterval(id);
  }, [reduce]);
  const cur = CYCLE[i];
  return (
    <div className="flex flex-col items-center">
      <RiskGauge score={cur.score} tier={cur.tier} />
      <div
        className="tier-chip mt-3"
        style={{
          color:
            cur.tier === "LOW" ? "var(--success)" : cur.tier === "MEDIUM" ? "var(--warning)" : "var(--danger)",
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background:
              cur.tier === "LOW" ? "var(--success)" : cur.tier === "MEDIUM" ? "var(--warning)" : "var(--danger)",
          }}
        />
        {cur.tier} → {cur.label}
      </div>
    </div>
  );
}

// ── Pipeline stages (real terminology from the codebase) ──────────────────────
const STAGES = [
  { icon: Layers, title: "Signals", body: "Velocity, impossible-travel geo checks, new-device / new-beneficiary, amount z-score and time-of-day are gathered from Redis history (with a Postgres fallback)." },
  { icon: Cpu, title: "Machine learning", body: "A RandomForest (fraud probability) and an IsolationForest (anomaly score) score the transaction. The model is advisory — one signal among several, not the sole authority." },
  { icon: Gauge, title: "Risk engine", body: "ML output is blended with rule-based signals into a single 0–100 composite score and a LOW / MEDIUM / HIGH tier." },
  { icon: Boxes, title: "Blockchain", body: "The scored result is sealed into a custom SHA-256 proof-of-work chain as an immutable audit record — the source of truth for tamper detection." },
  { icon: ShieldCheck, title: "Decision", body: "LOW allows the payment, MEDIUM triggers a step-up OTP challenge, HIGH blocks it and fires a live alert over the WebSocket stream." },
];

const TECH = [
  "FastAPI", "SQLAlchemy 2.0", "PostgreSQL", "Redis 7", "scikit-learn",
  "Next.js 16", "React 19", "Tailwind v4", "React Three Fiber", "PyJWT + bcrypt",
];

export default function LandingPage() {
  const { user } = useAuth();
  const reduce = useReducedMotion();
  // Hero entrance transitions snap instantly for reduced-motion users. (The
  // `initial`/`animate` markup stays deterministic so SSR and client hydration
  // agree regardless of the viewer's motion preference.)
  const heroT = (delay: number) =>
    reduce ? { duration: 0 } : { duration: 0.6, delay };

  return (
    <SmoothScroll>
      <main className="relative min-h-screen overflow-x-hidden bg-[var(--bg)] text-[var(--text)]">
        {/* Top nav */}
        <nav className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)]">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <span className="font-bold">SecureFlow</span>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost hidden sm:inline-flex"
              >
                <Github className="h-4 w-4" /> GitHub
              </a>
              <Link href={user ? "/dashboard" : "/auth"} className="btn btn-primary">
                {user ? "Open Dashboard" : "Sign in"}
              </Link>
            </div>
          </div>
        </nav>

        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <section className="relative">
          <div className="cyber-grid pointer-events-none absolute inset-0" />
          <div className="scanlines pointer-events-none absolute inset-0" />
          <BlockchainCanvas className="pointer-events-none absolute inset-0 opacity-70" />

          <div className="relative mx-auto grid max-w-6xl gap-10 px-5 py-20 md:grid-cols-2 md:py-28">
            <div>
              <motion.span
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={heroT(0)}
                className="tier-chip mb-5 text-[var(--accent-cyan)]"
              >
                <Radio className="h-3.5 w-3.5" /> Real-time UPI fraud defense
              </motion.span>
              <motion.h1
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={heroT(0.05)}
                className="text-4xl font-extrabold leading-[1.08] md:text-6xl"
              >
                <span className="text-glow">Every UPI payment,</span>
                <br />
                scored, sealed &amp; audited.
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={heroT(0.12)}
                className="mt-5 max-w-md text-[var(--text-muted)]"
              >
                SecureFlow scores every transaction 0–100 for fraud risk with machine learning and
                rule-based signals, takes a tiered action, and seals the result into a tamper-evident
                blockchain audit trail — in real time.
              </motion.p>
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={heroT(0.2)}
                className="mt-8 flex flex-wrap gap-3"
              >
                <Link href="/lab" className="btn btn-primary text-base">
                  <PlayCircle className="h-5 w-5" /> Try the Live Demo
                </Link>
                <Link href={user ? "/dashboard" : "/auth"} className="btn btn-ghost text-base">
                  {user ? "Open Dashboard" : "Sign in"} <ArrowRight className="h-4 w-4" />
                </Link>
              </motion.div>
              <p className="mt-3 text-xs text-[var(--text-dim)]">
                The demo replays real payments through the live pipeline — no signup required.
              </p>
            </div>

            <div className="flex items-center justify-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={heroT(0.15)}
                className="glow-ring rounded-2xl bg-[var(--surface)]/70 p-8 backdrop-blur-sm"
              >
                <p className="mb-4 text-center text-[10px] uppercase tracking-[0.25em] text-[var(--text-dim)]">
                  Live risk decision
                </p>
                <LiveGauge />
              </motion.div>
            </div>
          </div>
          <div className="glow-line mx-auto max-w-6xl" />
        </section>

        {/* ── How it works ───────────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-5 py-20">
          <Reveal>
            <p className="text-sm font-semibold uppercase tracking-widest text-[var(--accent-cyan)]">
              The pipeline
            </p>
            <h2 className="mt-2 text-3xl font-bold md:text-4xl">How a payment is judged</h2>
            <p className="mt-3 max-w-xl text-[var(--text-muted)]">
              One shared pipeline scores every transaction — the same code path runs for the live API
              and the demo Lab. Each stage below is a real module in the codebase.
            </p>
          </Reveal>

          <div className="mt-12 space-y-4">
            {STAGES.map((s, i) => (
              <Reveal key={s.title} delay={i * 0.05}>
                <div className="panel flex items-start gap-4 p-5 md:p-6">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-2)]">
                    <s.icon className="h-5 w-5 text-[var(--accent)]" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="mono text-xs text-[var(--text-dim)]">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <h3 className="font-semibold">{s.title}</h3>
                    </div>
                    <p className="mt-1.5 text-sm text-[var(--text-muted)]">{s.body}</p>
                  </div>
                  {i < STAGES.length - 1 && (
                    <ArrowRight className="mt-3 hidden h-4 w-4 rotate-90 text-[var(--text-dim)] md:block" />
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ── What makes it different: governance + watchdog ─────────────── */}
        <section className="relative border-y border-[var(--border)] bg-[var(--bg-elevated)]">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <Reveal>
              <p className="text-sm font-semibold uppercase tracking-widest text-[var(--accent-cyan)]">
                What makes it different
              </p>
              <h2 className="mt-2 text-3xl font-bold md:text-4xl">
                Consensus governance &amp; a self-healing watchdog
              </h2>
              <p className="mt-3 max-w-2xl text-[var(--text-muted)]">
                Reversing a fraud decision is the most dangerous admin action in the system. SecureFlow
                makes it impossible for any single admin to do it quietly.
              </p>
            </Reveal>

            <div className="mt-12 grid gap-6 md:grid-cols-2">
              <Reveal>
                <div className="panel h-full p-6">
                  <Landmark className="h-6 w-6 text-[var(--accent)]" />
                  <h3 className="mt-4 text-lg font-semibold">4-admin unanimous consensus</h3>
                  <p className="mt-2 text-sm text-[var(--text-muted)]">
                    A decision reversal is a <em>proposal</em>, not a write. It commits only on unanimous
                    approval from the governance council. Each vote independently attests to the record&apos;s
                    state hash, so any mid-vote tampering is detected as divergence and discarded.
                  </p>
                </div>
              </Reveal>

              <Reveal delay={0.08}>
                <div className="panel h-full p-6">
                  <ShieldAlert className="h-6 w-6 text-[var(--danger)]" />
                  <h3 className="mt-4 text-lg font-semibold">Self-healing integrity watchdog</h3>
                  <p className="mt-2 text-sm text-[var(--text-muted)]">
                    A background loop continuously compares the live database against the immutable
                    on-chain state. If a rogue direct DB edit is found, it auto-rolls the record back to
                    the blockchain&apos;s agreed value and emits a live alert — no human needed.
                  </p>
                </div>
              </Reveal>
            </div>

            <Reveal delay={0.1}>
              <div className="terminal mt-6 p-5 text-xs leading-relaxed text-[var(--text-muted)]">
                <div className="mb-3 flex items-center gap-1.5">
                  <span className="terminal-dot" style={{ background: "#f85149" }} />
                  <span className="terminal-dot" style={{ background: "#d29922" }} />
                  <span className="terminal-dot" style={{ background: "#2ea043" }} />
                  <span className="ml-2 text-[var(--text-dim)]">watchdog.scan()</span>
                </div>
                <p><span className="text-[var(--accent-cyan)]">→</span> checked 128 chain-anchored transactions</p>
                <p><span className="text-[var(--danger)]">!</span> divergence on txn 5e3f… — DB says ALLOWED, chain says BLOCKED</p>
                <p><span className="text-[var(--success)]">✓</span> auto-healed txn 5e3f… → BLOCKED (sealed in block #129)</p>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ── Resilience strip ───────────────────────────────────────────── */}
        <section className="mx-auto max-w-6xl px-5 py-16">
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { icon: Zap, t: "Fail-open resilience", d: "Every Redis call degrades gracefully — if the cache is down the app stays correct, just slower, using Postgres." },
              { icon: Database, t: "Durable audit trail", d: "Blocks persist to Postgres in production, so the immutable chain survives redeploys on ephemeral hosting." },
              { icon: Radio, t: "Live alert stream", d: "HIGH-risk transactions and auto-heals fan out over an authenticated WebSocket to the dashboard in real time." },
            ].map((c) => (
              <Reveal key={c.t}>
                <div className="panel-2 h-full p-5">
                  <c.icon className="h-5 w-5 text-[var(--accent-cyan)]" />
                  <h3 className="mt-3 text-sm font-semibold">{c.t}</h3>
                  <p className="mt-1.5 text-xs text-[var(--text-muted)]">{c.d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ── Tech + footer ──────────────────────────────────────────────── */}
        <footer className="border-t border-[var(--border)] bg-[var(--bg-elevated)]">
          <div className="mx-auto max-w-6xl px-5 py-14">
            <Reveal>
              <p className="text-center text-xs uppercase tracking-widest text-[var(--text-dim)]">
                Built with
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {TECH.map((t) => (
                  <span key={t} className="tier-chip text-[var(--text-muted)]">
                    {t}
                  </span>
                ))}
              </div>
            </Reveal>

            <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-[var(--border)] pt-8 sm:flex-row">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)]">
                  <ShieldCheck className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold">SecureFlow</p>
                  <p className="text-[11px] text-[var(--text-dim)]">
                    A portfolio project — not a production fintech system.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="btn btn-ghost">
                  <Github className="h-4 w-4" /> Source
                </a>
                <a
                  href={`${REPO_URL}/tree/main/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-ghost"
                >
                  <BookOpen className="h-4 w-4" /> Docs
                </a>
                <Link href="/lab" className="btn btn-primary">
                  <PlayCircle className="h-4 w-4" /> Live Demo
                </Link>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </SmoothScroll>
  );
}
