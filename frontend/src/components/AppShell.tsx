"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  LayoutDashboard,
  ScanSearch,
  Boxes,
  BarChart3,
  Settings as SettingsIcon,
  ShieldCheck,
  FlaskConical,
  Landmark,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { isStaff, useAuth } from "@/lib/auth";
import { useAlertStream } from "@/hooks/useWebSocket";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/lab", label: "UPI Lab", icon: FlaskConical, badge: "LAB" },
  { href: "/analyze", label: "Transaction Analysis", icon: ScanSearch },
  { href: "/blockchain", label: "Blockchain Explorer", icon: Boxes, staffOnly: true },
  { href: "/governance", label: "Admin Governance", icon: Landmark, badge: "4✓", governanceOnly: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3, staffOnly: true },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/dashboard"
    ? pathname === "/dashboard" || pathname === "/"
    : pathname.startsWith(href);
}

/** Pulses when a new HIGH-risk alert arrives over the live stream. */
function useHighAlertPulse(): boolean {
  const { alerts } = useAlertStream();
  const [pulse, setPulse] = useState(false);
  const seen = useRef(0);

  useEffect(() => {
    if (alerts.length > seen.current) {
      const fresh = alerts.slice(0, alerts.length - seen.current);
      if (fresh.some((a) => a.risk_tier === "HIGH")) {
        // Flashing the nav badge in response to a new HIGH alert from the live
        // WebSocket stream is exactly "react to an external system" — the timed
        // reset below runs in a callback, so only this initial set is flagged.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setPulse(true);
        const t = setTimeout(() => setPulse(false), 2200);
        seen.current = alerts.length;
        return () => clearTimeout(t);
      }
    }
    seen.current = alerts.length;
  }, [alerts]);

  return pulse;
}

function NavList({
  pathname,
  governanceAccess,
  staff,
  onNavigate,
  pulse,
}: {
  pathname: string;
  governanceAccess: boolean;
  staff: boolean;
  onNavigate?: () => void;
  pulse: boolean;
}) {
  return (
    <nav className="mt-6 flex flex-1 flex-col gap-1">
      {NAV.filter(
        (n) => (!n.governanceOnly || governanceAccess) && (!n.staffOnly || staff),
      ).map(
        ({ href, label, icon: Icon, badge }) => {
          const active = isActive(pathname, href);
          const isLab = href === "/lab";
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                active
                  ? "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border-strong)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--text)]"
              }`}
            >
              {active && (
                <span
                  className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full"
                  style={{ background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }}
                />
              )}
              <Icon className="h-4 w-4" style={active ? { color: "var(--accent)" } : undefined} />
              <span className="flex-1">{label}</span>
              {isLab && pulse && (
                <span className="absolute right-2 h-2 w-2 animate-ping rounded-full bg-[var(--danger)]" />
              )}
              {badge && (
                <span
                  className="rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide"
                  style={{ background: "rgba(34,211,238,0.15)", color: "var(--accent-cyan)" }}
                >
                  {badge}
                </span>
              )}
            </Link>
          );
        },
      )}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 px-2 py-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)]">
        <ShieldCheck className="h-5 w-5 text-white" />
      </div>
      <div>
        <p className="text-sm font-bold leading-tight">SecureFlow</p>
        <p className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
          UPI Fraud Defense
        </p>
      </div>
    </Link>
  );
}

// Routes reachable without authentication (the UPI Lab is a public demo surface).
function isPublicRoute(pathname: string): boolean {
  return pathname === "/lab" || pathname.startsWith("/lab/");
}

/** Minimal top bar shown around public routes (e.g. the Lab) for logged-out visitors. */
function PublicChrome({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen">
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-elevated)]/95 px-5 py-2.5 backdrop-blur">
        <Brand />
        <div className="flex items-center gap-2">
          <Link href="/" className="btn btn-ghost">
            Home
          </Link>
          <Link href="/auth" className="btn btn-primary">
            Sign in
          </Link>
        </div>
      </header>
      <main className="relative overflow-x-hidden">
        <div className="app-backdrop pointer-events-none absolute inset-0 h-64" />
        <div className="relative mx-auto w-full max-w-6xl px-5 py-6 md:px-8 md:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const pulse = useHighAlertPulse();
  const publicRoute = isPublicRoute(pathname);

  useEffect(() => {
    if (!loading && !user && !publicRoute) router.replace("/auth");
  }, [loading, user, router, publicRoute]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--text-muted)]">
        Loading…
      </div>
    );
  }

  // Logged-out visitor on a public route → lightweight chrome, no redirect.
  if (!user) {
    if (publicRoute) return <PublicChrome>{children}</PublicChrome>;
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--text-muted)]">
        Loading…
      </div>
    );
  }

  const signOut = async () => {
    await logout();
    router.replace("/auth");
  };

  const UserFooter = (
    <div className="mt-4 border-t border-[var(--border)] pt-4">
      <div className="px-2 pb-3">
        <p className="truncate text-xs font-medium text-[var(--text)]">{user.vpa}</p>
        <p className="truncate text-[10px] text-[var(--text-dim)]">
          {user.email} · {user.role}
        </p>
      </div>
      <button
        onClick={signOut}
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--danger)]"
      >
        <LogOut className="h-4 w-4" />
        Sign out
      </button>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] p-4">
        <Brand />
        <NavList
          pathname={pathname}
          governanceAccess={!!user.governance_access}
          staff={isStaff(user)}
          pulse={pulse}
        />
        {UserFooter}
      </aside>

      {/* Mobile header */}
      <header className="fixed inset-x-0 top-0 z-40 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-elevated)]/95 px-4 py-2.5 backdrop-blur md:hidden">
        <Brand />
        <button
          aria-label="Open navigation menu"
          aria-expanded={drawerOpen}
          onClick={() => setDrawerOpen(true)}
          className="relative rounded-lg border border-[var(--border-strong)] p-2 text-[var(--text-muted)]"
        >
          <Menu className="h-5 w-5" />
          {pulse && (
            <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-ping rounded-full bg-[var(--danger)]" />
          )}
        </button>
      </header>

      {/* Mobile drawer */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDrawerOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 flex w-[82%] max-w-xs flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] p-4 md:hidden"
              initial={reduceMotion ? { opacity: 0 } : { x: "-100%" }}
              animate={reduceMotion ? { opacity: 1 } : { x: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { x: "-100%" }}
              transition={{ type: "tween", duration: 0.25, ease: "easeOut" }}
              role="dialog"
              aria-label="Navigation"
            >
              <div className="flex items-center justify-between">
                <Brand />
                <button
                  aria-label="Close navigation menu"
                  onClick={() => setDrawerOpen(false)}
                  className="rounded-lg border border-[var(--border-strong)] p-2 text-[var(--text-muted)]"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <NavList
                pathname={pathname}
                governanceAccess={!!user.governance_access}
                staff={isStaff(user)}
                onNavigate={() => setDrawerOpen(false)}
                pulse={pulse}
              />
              {UserFooter}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <main className="relative flex-1 overflow-x-hidden pt-14 md:pt-0">
        <div className="app-backdrop pointer-events-none absolute inset-0 h-64" />
        <div className="relative mx-auto w-full max-w-6xl px-5 py-6 md:px-8 md:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
