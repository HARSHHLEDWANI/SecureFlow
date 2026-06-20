"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, ShieldAlert, KeyRound } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { getDeviceId, useAuth } from "@/lib/auth";
import type { LoginResult } from "@/lib/types";
import { TierBadge } from "@/components/ui";

type Mode = "login" | "register";

export default function AuthPage() {
  const router = useRouter();
  const { user, loading, setSession } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [vpa, setVpa] = useState("");
  const [homeCity, setHomeCity] = useState("Mumbai");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [challenge, setChallenge] = useState<LoginResult | null>(null);
  const [otp, setOtp] = useState("");

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  function finish(result: LoginResult) {
    if (result.access_token) {
      setSession(result.access_token, result.user);
      router.replace("/");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        await api.register({ email, password, vpa, home_city: homeCity });
      }
      const result = await api.login({ email, password, device_id: getDeviceId() });
      if (result.step_up_required) {
        setChallenge(result);
      } else {
        finish(result);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function handleStepUp(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge?.challenge_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.verifyStepUp({ challenge_id: challenge.challenge_id, otp });
      finish(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      <div className="app-backdrop pointer-events-none absolute inset-0" />
      <div className="relative w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)]">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold">SecureFlow</h1>
            <p className="text-xs text-[var(--text-dim)]">UPI fraud detection console</p>
          </div>
        </div>

        {challenge ? (
          <form onSubmit={handleStepUp} className="panel p-6 animate-fade-up">
            <div className="mb-4 flex items-center gap-2 text-[var(--warning)]">
              <ShieldAlert className="h-5 w-5" />
              <h2 className="text-sm font-semibold">Step-up verification required</h2>
            </div>
            <p className="mb-4 text-sm text-[var(--text-muted)]">
              This sign-in was scored{" "}
              <span className="font-semibold text-[var(--text)]">
                {challenge.login_risk_score}/100
              </span>{" "}
              (<TierBadge tier={challenge.login_risk_tier} />). Enter the one-time code to continue.
            </p>
            {challenge.demo_otp && (
              <p className="mb-3 rounded-md panel-2 p-2 text-center text-xs text-[var(--text-dim)]">
                Demo OTP (normally sent via SMS):{" "}
                <span className="font-mono text-[var(--accent-cyan)]">{challenge.demo_otp}</span>
              </p>
            )}
            <label className="mb-1 block text-xs text-[var(--text-muted)]">One-time code</label>
            <input
              className="field mb-4 text-center tracking-[0.4em]"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              maxLength={6}
              placeholder="------"
              inputMode="numeric"
            />
            {error && <p className="mb-3 text-sm text-[var(--danger)]">{error}</p>}
            <button className="btn btn-primary w-full" disabled={busy}>
              <KeyRound className="h-4 w-4" />
              {busy ? "Verifying…" : "Verify & continue"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} className="panel p-6 animate-fade-up">
            <div className="mb-5 flex gap-1 rounded-lg panel-2 p-1">
              {(["login", "register"] as Mode[]).map((m) => (
                <button
                  type="button"
                  key={m}
                  onClick={() => {
                    setMode(m);
                    setError(null);
                  }}
                  className={`flex-1 rounded-md py-1.5 text-sm font-medium capitalize transition ${
                    mode === m ? "bg-[var(--accent)] text-white" : "text-[var(--text-muted)]"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            <label className="mb-1 block text-xs text-[var(--text-muted)]">Email</label>
            <input
              className="field mb-3"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />

            {mode === "register" && (
              <>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  Virtual Payment Address (VPA)
                </label>
                <input
                  className="field mb-3"
                  value={vpa}
                  onChange={(e) => setVpa(e.target.value)}
                  placeholder="yourname@okhdfc"
                  required
                />
                <label className="mb-1 block text-xs text-[var(--text-muted)]">Home city</label>
                <input
                  className="field mb-3"
                  value={homeCity}
                  onChange={(e) => setHomeCity(e.target.value)}
                  placeholder="Mumbai"
                />
              </>
            )}

            <label className="mb-1 block text-xs text-[var(--text-muted)]">Password</label>
            <input
              className="field mb-4"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              minLength={8}
              required
            />

            {error && <p className="mb-3 text-sm text-[var(--danger)]">{error}</p>}
            <button className="btn btn-primary w-full" disabled={busy}>
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
            <p className="mt-3 text-center text-[11px] text-[var(--text-dim)]">
              Logins are themselves risk-scored. Unrecognised devices trigger step-up auth.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
