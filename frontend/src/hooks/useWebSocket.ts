"use client";

import { useCallback, useEffect } from "react";
import { useSyncExternalStore } from "react";
import type { Alert } from "@/lib/types";
import { getToken } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/alerts";
const MAX_ALERTS = 25;

export type WsState = "connecting" | "open" | "closed";

// ── Shared, ref-counted connection ────────────────────────────────────────────
//
// A single WebSocket is shared across every component that subscribes (dashboard,
// app shell, etc.) so we never open duplicate sockets. The connection is opened
// on the first subscriber and torn down when the last one unmounts. The backend
// requires a valid access token on the handshake (?token=), so we never attempt
// an anonymous connection.

let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let refCount = 0;
let state: WsState = "closed";
let alerts: Alert[] = [];
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function connect() {
  const token = getToken();
  if (!token) {
    state = "closed"; // no anonymous feed — a token is required
    emit();
    return;
  }
  state = "connecting";
  emit();
  const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
  socket = ws;
  ws.onopen = () => {
    state = "open";
    emit();
  };
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "fraud_alert") {
        alerts = [msg as Alert, ...alerts].slice(0, MAX_ALERTS);
        emit();
      }
    } catch {
      /* ignore malformed frames */
    }
  };
  ws.onclose = () => {
    state = "closed";
    socket = null;
    emit();
    if (refCount > 0) retry = setTimeout(connect, 3000);
  };
  ws.onerror = () => ws.close();
}

function acquire() {
  refCount += 1;
  if (refCount === 1) connect();
}

function release() {
  refCount -= 1;
  if (refCount <= 0) {
    refCount = 0;
    if (retry) clearTimeout(retry);
    socket?.close();
    socket = null;
    state = "closed";
  }
}

/** Subscribe to the live fraud-alert stream (shared socket, auto-reconnect). */
export function useAlertStream() {
  const subscribe = useCallback((cb: () => void) => {
    listeners.add(cb);
    return () => listeners.delete(cb);
  }, []);

  useEffect(() => {
    acquire();
    return () => release();
  }, []);

  const liveAlerts = useSyncExternalStore(subscribe, () => alerts, () => alerts);
  const liveState = useSyncExternalStore(subscribe, () => state, () => state);
  return { alerts: liveAlerts, state: liveState };
}
