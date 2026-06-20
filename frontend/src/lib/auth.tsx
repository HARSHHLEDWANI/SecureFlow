"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api";
import type { AuthUser } from "./types";

const DEVICE_KEY = "sf_device_id";

/** A stable per-browser device fingerprint used by the risk engine. */
export function getDeviceId(): string {
  if (typeof window === "undefined") return "web-default";
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = `web-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  setSession: (token: string, user: AuthUser) => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setSession = useCallback((token: string, u: AuthUser) => {
    setToken(token);
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    } finally {
      clearToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, setSession, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
