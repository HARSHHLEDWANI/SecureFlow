"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
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
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/lab", label: "UPI Lab", icon: FlaskConical, badge: "LAB" },
  { href: "/analyze", label: "Transaction Analysis", icon: ScanSearch },
  { href: "/blockchain", label: "Blockchain Explorer", icon: Boxes },
  { href: "/governance", label: "Admin Governance", icon: Landmark, badge: "4✓", governanceOnly: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--text-muted)]">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] p-4">
        <div className="flex items-center gap-2.5 px-2 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)]">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold leading-tight">SecureFlow</p>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
              UPI Fraud Defense
            </p>
          </div>
        </div>

        <nav className="mt-6 flex flex-1 flex-col gap-1">
          {NAV.filter((n) => !n.governanceOnly || user.governance_access).map(({ href, label, icon: Icon, badge }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border-strong)]"
                    : "text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--text)]"
                }`}
              >
                <Icon className="h-4 w-4" style={active ? { color: "var(--accent)" } : undefined} />
                <span className="flex-1">{label}</span>
                {badge && (
                  <span className="rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide"
                    style={{ background: "rgba(34,211,238,0.15)", color: "var(--accent-cyan)" }}>
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="mt-4 border-t border-[var(--border)] pt-4">
          <div className="px-2 pb-3">
            <p className="truncate text-xs font-medium text-[var(--text)]">{user.vpa}</p>
            <p className="truncate text-[10px] text-[var(--text-dim)]">
              {user.email} · {user.role}
            </p>
          </div>
          <button
            onClick={async () => {
              await logout();
              router.replace("/auth");
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--danger)]"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      <main className="relative flex-1 overflow-x-hidden">
        <div className="app-backdrop pointer-events-none absolute inset-0 h-64" />
        <div className="relative mx-auto w-full max-w-6xl px-5 py-6 md:px-8 md:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
