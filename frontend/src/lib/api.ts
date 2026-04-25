const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000/api";

// ── token helpers ──────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sf_token");
}

export function setAccessToken(token: string) {
  localStorage.setItem("sf_token", token);
}

export function clearTokens() {
  localStorage.removeItem("sf_token");
}

// ── fetch wrapper ──────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return apiFetch<T>(path, options, false);
    clearTokens();
    if (typeof window !== "undefined") window.location.href = "/auth";
    throw new Error("Session expired");
  }

  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((json as { error?: string }).error ?? `HTTP ${res.status}`);
  return json as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const json = (await res.json()) as { data?: { accessToken?: string } };
    if (json.data?.accessToken) {
      setAccessToken(json.data.accessToken);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

// ── response envelope ──────────────────────────────────────────────────────

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
  meta?: {
    nextCursor: string | null;
    hasMore: boolean;
    limit: number;
  };
}

// ── auth ───────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  role: "ADMIN" | "ANALYST" | "VIEWER";
}

export async function login(email: string, password: string) {
  const res = await apiFetch<ApiResponse<{ accessToken: string; user: AuthUser }>>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
      credentials: "include",
    },
    false
  );
  setAccessToken(res.data.accessToken);
  return res.data;
}

export async function logout() {
  try {
    await apiFetch("/auth/logout", { method: "POST", credentials: "include" });
  } finally {
    clearTokens();
  }
}

export async function getMe() {
  const res = await apiFetch<ApiResponse<AuthUser>>("/auth/me");
  return res.data;
}

// ── dashboard ──────────────────────────────────────────────────────────────

export interface DashboardStats {
  totalTransactions: number;
  totalVolume: number;
  averageRiskScore: number;
  flaggedCount: number;
  statusBreakdown: Record<string, number>;
  dailyVolume: { date: string; volume: number }[];
  topRiskyWallets: { wallet: string; avgRiskScore: number; transactionCount: number }[];
}

export async function fetchDashboardStats() {
  const res = await apiFetch<ApiResponse<DashboardStats>>("/dashboard/stats");
  return res.data;
}

// ── transactions ───────────────────────────────────────────────────────────

export interface Transaction {
  id: string;
  fromWallet: string;
  toWallet: string;
  amount: string;
  currency: string;
  status: "PENDING" | "APPROVED" | "FLAGGED" | "REJECTED";
  riskScore: number | null;
  confidence: number | null;
  aiExplanation: string | null;
  auditTxHash: string | null;
  createdAt: string;
  updatedAt: string;
  user?: { email: string; role: string };
  auditLogs?: AuditLog[];
}

export interface CreateTransactionInput {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
}

export async function fetchTransactions(params?: {
  cursor?: string;
  limit?: number;
  status?: string;
  currency?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.cursor) qs.set("cursor", params.cursor);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.status) qs.set("status", params.status);
  if (params?.currency) qs.set("currency", params.currency);
  const query = qs.toString() ? `?${qs}` : "";
  const res = await apiFetch<ApiResponse<Transaction[]>>(`/transactions${query}`);
  return { items: res.data, meta: res.meta };
}

export async function fetchTransactionById(id: string) {
  const res = await apiFetch<ApiResponse<Transaction>>(`/transactions/${id}`);
  return res.data;
}

export async function createTransaction(data: CreateTransactionInput) {
  const res = await apiFetch<ApiResponse<Transaction>>("/transactions", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateTransactionStatus(id: string, status: string) {
  const res = await apiFetch<ApiResponse<Transaction>>(
    `/transactions/${id}/status`,
    { method: "PUT", body: JSON.stringify({ status }) }
  );
  return res.data;
}

// ── audit logs ─────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string;
  transactionId: string;
  action: string;
  actorId: string;
  riskScore: number | null;
  blockchainHash: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  actor?: { email: string; role: string };
  transaction?: { fromWallet: string; toWallet: string; amount: string; currency: string };
}

export async function fetchAuditLogs(params?: {
  cursor?: string;
  limit?: number;
  action?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.cursor) qs.set("cursor", params.cursor);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.action) qs.set("action", params.action);
  const query = qs.toString() ? `?${qs}` : "";
  const res = await apiFetch<ApiResponse<AuditLog[]>>(`/audit${query}`);
  return { items: res.data, meta: res.meta };
}

export async function fetchAuditStats() {
  const res = await apiFetch<ApiResponse<{ total: number; byAction: Record<string, number> }>>(
    "/audit/stats"
  );
  return res.data;
}

// ── settings ───────────────────────────────────────────────────────────────

export interface UserSettings {
  id: string;
  email: string;
  role: string;
  createdAt: string;
  updatedAt: string;
  apiKeys: {
    id: string;
    name: string;
    lastUsedAt: string | null;
    expiresAt: string | null;
    createdAt: string;
  }[];
}

export async function fetchUserSettings() {
  const res = await apiFetch<ApiResponse<UserSettings>>("/settings");
  return res.data;
}

export async function updateUserSettings(data: { email?: string }) {
  const res = await apiFetch<ApiResponse<UserSettings>>("/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function generateApiKey(name: string) {
  const res = await apiFetch<
    ApiResponse<{ id: string; name: string; key: string; createdAt: string }>
  >("/settings/api-keys", { method: "POST", body: JSON.stringify({ name }) });
  return res.data;
}

export async function revokeApiKey(id: string) {
  await apiFetch(`/settings/api-keys/${id}`, { method: "DELETE" });
}
