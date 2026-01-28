import { Transaction } from "@/types/transaction";

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001/api";

// ============ TRANSACTIONS ============
export async function fetchTransactions(params?: {
  status?: string;
  skip?: number;
  take?: number;
}): Promise<Transaction[]> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  if (params?.skip) queryParams.append("skip", params.skip.toString());
  if (params?.take) queryParams.append("take", params.take.toString());

  const res = await fetch(
    `${BASE_URL}/transactions${queryParams.toString() ? `?${queryParams.toString()}` : ""}`,
    {
      cache: "no-store",
    }
  );

  if (!res.ok) {
    console.error("Failed to fetch transactions:", res.statusText);
    return [];
  }

  return res.json();
}

export async function fetchTransactionById(id: string): Promise<Transaction | null> {
  const res = await fetch(`${BASE_URL}/transactions/${id}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    console.error("Failed to fetch transaction:", res.statusText);
    return null;
  }

  return res.json();
}

export async function createTransaction(data: {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
}): Promise<Transaction> {
  const res = await fetch(`${BASE_URL}/transactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error("Failed to create transaction");
  }

  return res.json();
}

// ============ AUDIT LOGS ============
export interface AuditLog {
  id: string;
  transactionId: string;
  action: string;
  status: string;
  riskScore: number;
  timestamp: string;
  auditHash: string;
  details: string;
}

export async function fetchAuditLogs(params?: {
  skip?: number;
  take?: number;
  status?: string;
}): Promise<AuditLog[]> {
  const queryParams = new URLSearchParams();
  if (params?.skip) queryParams.append("skip", params.skip.toString());
  if (params?.take) queryParams.append("take", params.take.toString());
  if (params?.status) queryParams.append("status", params.status);

  const res = await fetch(
    `${BASE_URL}/audit${queryParams.toString() ? `?${queryParams.toString()}` : ""}`,
    {
      cache: "no-store",
    }
  );

  if (!res.ok) {
    console.error("Failed to fetch audit logs:", res.statusText);
    return [];
  }

  return res.json();
}

export async function fetchAuditStats(): Promise<{
  totalAudited: number;
  successRate: number;
  averageLatency: number;
}> {
  const res = await fetch(`${BASE_URL}/audit/stats`, {
    cache: "no-store",
  });

  if (!res.ok) {
    return { totalAudited: 0, successRate: 0, averageLatency: 0 };
  }

  return res.json();
}

// ============ SETTINGS ============
export interface UserSettings {
  id: string;
  email: string;
  riskThreshold: number;
  notificationsEnabled: boolean;
  twoFactorEnabled: boolean;
  apiKeys: string[];
  createdAt: string;
  updatedAt: string;
}

export async function fetchUserSettings(): Promise<UserSettings | null> {
  const res = await fetch(`${BASE_URL}/settings`, {
    cache: "no-store",
  });

  if (!res.ok) {
    console.error("Failed to fetch settings:", res.statusText);
    return null;
  }

  return res.json();
}

export async function updateUserSettings(data: Partial<UserSettings>): Promise<UserSettings> {
  const res = await fetch(`${BASE_URL}/settings`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error("Failed to update settings");
  }

  return res.json();
}

export async function generateApiKey(): Promise<{ key: string; createdAt: string }> {
  const res = await fetch(`${BASE_URL}/settings/api-keys`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    throw new Error("Failed to generate API key");
  }

  return res.json();
}

// ============ DASHBOARD STATS ============
export interface DashboardStats {
  totalTransactions: number;
  flaggedTransactions: number;
  averageRiskScore: number;
  totalAudited: number;
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${BASE_URL}/dashboard/stats`, {
    cache: "no-store",
  });

  if (!res.ok) {
    return {
      totalTransactions: 0,
      flaggedTransactions: 0,
      averageRiskScore: 0,
      totalAudited: 0,
    };
  }

  return res.json();
}

// ============ AUTH ============
export async function signup(payload: { email: string; password: string; name?: string }) {
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.json()).error || "Signup failed");
  return res.json();
}

export async function signin(payload: { email: string; password: string }) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.json()).error || "Login failed");
  return res.json();
}

export async function getMe(token?: string) {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  else if (typeof window !== "undefined") {
    const t = localStorage.getItem("sf_token");
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }

  const res = await fetch(`${BASE_URL}/auth/me`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}
