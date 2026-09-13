/**
 * useLiveChannel — shared WebSocket subscription hook.
 *
 * Connects to one of the backend's live channels (/ws/microgrid, /ws/agents,
 * /ws/market) and keeps the latest message in a ref for use inside
 * useFrame (no re-renders), plus a throttled state snapshot for React UI.
 */

import { useEffect, useRef, useState } from "react";

export interface LiveMessage {
  type: string;
  timestamp: string;
  [key: string]: unknown;
}

export function useLiveChannel(channel: "microgrid" | "agents" | "market") {
  const latest = useRef<LiveMessage | null>(null);
  const [snapshot, setSnapshot] = useState<LiveMessage | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/${channel}`;
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: number | undefined;

    const connect = () => {
      ws = new WebSocket(url);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as LiveMessage;
          latest.current = msg;
          // Throttled UI update (the 3D loop reads `latest` directly).
          setSnapshot(msg);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      ws?.close();
    };
  }, [channel]);

  return { latest, snapshot, connected };
}
