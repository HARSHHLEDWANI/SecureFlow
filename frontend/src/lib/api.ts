// Typed API client for the SecureFlow FastAPI backend.
// Access token is kept in localStorage; the refresh token is an httpOnly cookie.
//
// Response contract: every body, success or failure, is the envelope
// { success, data, error } - including HTTP errors (previously { detail }) and 422
// validation failures (error = summary, data.errors = per-field). Status codes are unchanged.
import type {
  Alert,
  AnalyzeResult,
  AuthUser,
  Block,
  Council,
  DashboardStats,
  HealthStatus,
  IntegrityResult,
  LoginResult,
  ModelMetrics,
  Proposal,
  TransactionSummary,
  UpiDemoUser,
  UpiHistory,
  UpiPayResult,
  UpiScenario,
  UpiScenarioRun,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "sf_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

interface Envelope<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retry && token) {
    if (await tryRefresh()) return request<T>(path, options, false);
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/auth";
    throw new ApiError("Session expired", 401);
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }

  if (!res.ok) {
    const detail =
      (body as { error?: string })?.error ??
      (body as { detail?: string })?.detail ?? // legacy shape, kept for older backends
      `HTTP ${res.status}`;
    throw new ApiError(detail, res.status);
  }
  return (body as Envelope<T>).data;
}

// Refresh tokens are single-use (rotated server-side), so concurrent 401s must share ONE
// refresh call: a second call with the old cookie would look like token theft.
let refreshInFlight: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function doRefresh(attempt = 0): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" });
    // 409: another tab rotated the cookie a moment ago - retry once with the new one.
    if (res.status === 409 && attempt < 1) return doRefresh(attempt + 1);
    if (!res.ok) return false;
    const json = (await res.json()) as Envelope<{ accessToken: string }>;
    if (json.data?.accessToken) {
      setToken(json.data.accessToken);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

// UPI Lab writes need a short-lived demo session (POST /upi/session), sent as
// X-Demo-Session. Fetched lazily and on Lab page load; renewed shortly before expiry.
let demoSession: { token: string; expiresAt: number } | null = null;

async function demoHeaders(): Promise<Record<string, string>> {
  if (!demoSession || Date.now() > demoSession.expiresAt - 30_000) {
    const s = await request<{ token: string; expires_in: number }>(
      "/upi/session",
      { method: "POST" },
      false,
    );
    demoSession = { token: s.token, expiresAt: Date.now() + s.expires_in * 1000 };
  }
  return { "X-Demo-Session": demoSession.token };
}

async function demoRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      // retry=false: a 401 here is about the demo session, not the user's login.
      return await request<T>(path, { ...options, headers: await demoHeaders() }, false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401 && attempt === 0) {
        demoSession = null; // expired or rejected: get a fresh one and retry once
        continue;
      }
      throw e;
    }
  }
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const api = {
  register: (body: { email: string; password: string; vpa: string; home_city?: string }) =>
    request<AuthUser>("/auth/register", { method: "POST", body: JSON.stringify(body) }),

  login: (body: { email: string; password: string; device_id: string }) =>
    request<LoginResult>("/auth/login", { method: "POST", body: JSON.stringify(body) }, false),

  verifyStepUp: (body: { challenge_id: string; otp: string }) =>
    request<LoginResult>("/auth/verify-step-up", { method: "POST", body: JSON.stringify(body) }),

  me: () => request<AuthUser>("/auth/me"),
  logout: () => request<unknown>("/auth/logout", { method: "POST" }),

  // ── Transactions ────────────────────────────────────────────────────────────
  analyze: (body: {
    to_vpa: string;
    amount_inr: number;
    txn_type: string;
    device_id: string;
    location_lat?: number;
    location_lon?: number;
  }) => request<AnalyzeResult>("/transaction/analyze", { method: "POST", body: JSON.stringify(body) }),

  transactions: (params?: { limit?: number; tier?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.tier) qs.set("tier", params.tier);
    const q = qs.toString() ? `?${qs}` : "";
    return request<TransactionSummary[]>(`/transaction${q}`);
  },

  explain: (txnId: string) =>
    request<import("./types").Explanation>(`/transaction/${txnId}/explain`, { method: "POST" }),

  riskProfile: (userId: string) =>
    request<{ transaction_count: number; average_risk_score: number; flagged_count: number }>(
      `/risk-score/${userId}`,
    ),

  // ── Blockchain ──────────────────────────────────────────────────────────────
  chain: () => request<{ length: number; chain: Block[] }>("/blockchain/chain"),
  validateChain: () =>
    request<{ valid: boolean; tampered_block: number | null; message: string }>("/blockchain/validate"),
  chainStats: () =>
    request<{ blocks: number; total_transactions: number; difficulty: number; valid: boolean }>(
      "/blockchain/stats",
    ),

  // ── Analytics ───────────────────────────────────────────────────────────────
  dashboard: () => request<DashboardStats>("/analytics/dashboard"),
  recentAlerts: (limit = 20) => request<Alert[]>(`/analytics/recent-alerts?limit=${limit}`),
  modelMetrics: () => request<ModelMetrics | null>("/analytics/model-metrics"),

  health: () => request<HealthStatus>("/health"),

  // ── UPI Simulation Lab (public reads; writes need a demo session) ───────────
  upi: {
    ensureSession: async () => {
      await demoHeaders();
    },
    users: () =>
      request<{ users: UpiDemoUser[]; demo_password: string; cities: Record<string, [number, number]> }>(
        "/upi/users",
      ),
    scenarios: () => request<{ scenarios: UpiScenario[] }>("/upi/scenarios"),
    pay: (body: {
      sender_vpa: string;
      receiver_vpa: string;
      amount_inr: number;
      txn_type: string;
      note?: string | null;
      city?: string | null;
      device_id?: string | null;
    }) => demoRequest<UpiPayResult>("/upi/pay", { method: "POST", body: JSON.stringify(body) }),
    runScenario: (id: string) =>
      demoRequest<UpiScenarioRun>(`/upi/scenario/${id}`, { method: "POST" }),
    history: (vpa: string, limit = 25) =>
      request<UpiHistory>(`/upi/user/${encodeURIComponent(vpa)}/history?limit=${limit}`),
    reset: () =>
      demoRequest<{ reset: boolean; users_seeded: number }>("/upi/reset", { method: "POST" }),
  },

  // ── Multi-admin governance (ADMIN only) ──────────────────────────────────────
  governance: {
    council: () => request<Council>("/governance/council"),
    proposals: (status?: string) =>
      request<Proposal[]>(`/governance/proposals${status ? `?status=${status}` : ""}`),
    proposal: (id: string) => request<Proposal>(`/governance/proposals/${id}`),
    createProposal: (body: { transaction_id: string; proposed_status: string; reason: string }) =>
      request<Proposal>("/governance/proposals", { method: "POST", body: JSON.stringify(body) }),
    vote: (id: string, vote: "APPROVE" | "REJECT") =>
      request<Proposal>(`/governance/proposals/${id}/vote`, { method: "POST", body: JSON.stringify({ vote }) }),
    integrity: (txnId: string) => request<IntegrityResult>(`/governance/integrity/${txnId}`),
    rollback: (txnId: string) =>
      request<{ restored: boolean; before: { status: string }; after: { status: string }; block_index: number }>(
        `/governance/integrity/${txnId}/rollback`,
        { method: "POST" },
      ),
    simulateTamper: (txnId: string, newStatus: string) =>
      request<{ transaction_id: string; tampered_to: string; was: string }>(
        `/governance/integrity/${txnId}/simulate-tamper`,
        { method: "POST", body: JSON.stringify({ new_status: newStatus }) },
      ),
    watchdog: () =>
      request<{
        enabled: boolean;
        interval_seconds: number;
        last_run: string | null;
        runs: number;
        checked: number;
        healed_total: number;
        recent: { transaction_id: string; from_status: string; to_status: string; block_index: number; at: string }[];
      }>("/governance/watchdog"),
    watchdogScan: () =>
      request<{ checked: number; healed: { transaction_id: string; from_status: string; to_status: string; block_index: number; at: string }[] }>(
        "/governance/watchdog/scan",
        { method: "POST" },
      ),

    // ── Model feedback loop (Feature B) ────────────────────────────────────────
    feedbackSummary: () => request<import("./types").FeedbackSummary>("/governance/feedback/summary"),
    feedbackRetrain: () =>
      request<{ scheduled: boolean; pending_corrections: number }>(
        "/governance/feedback/retrain",
        { method: "POST" },
      ),
    feedbackPromote: (version: number, force = false) =>
      request<{ promoted_version: number; consumed: number; forced: boolean }>(
        "/governance/feedback/promote",
        { method: "POST", body: JSON.stringify({ version, force }) },
      ),
  },
};
