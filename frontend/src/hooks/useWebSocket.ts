"use client";

import { useEffect, useRef, useState } from "react";
import type { Alert } from "@/lib/types";
import { getToken } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/alerts";

export type WsState = "connecting" | "open" | "closed";

/** Subscribe to the live fraud-alert stream with auto-reconnect. */
export function useAlertStream(maxAlerts = 25) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [state, setState] = useState<WsState>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let closed = false;

    function connect() {
      const token = getToken();
      const url = token ? `${WS_URL}?token=${encodeURIComponent(token)}` : WS_URL;
      setState("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setState("open");
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "fraud_alert") {
            setAlerts((prev) => [msg as Alert, ...prev].slice(0, maxAlerts));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setState("closed");
        if (!closed) retryRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      closed = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [maxAlerts]);

  return { alerts, state };
}
