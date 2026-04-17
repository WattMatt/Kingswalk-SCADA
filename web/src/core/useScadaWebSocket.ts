// web/src/core/useScadaWebSocket.ts
import { useEffect, useRef } from "react";
import { useBreakerStore } from "./breaker-store";
import type { BreakerState, BreakerStateValue, ServerMessage } from "./types";

// ---------------------------------------------------------------------------
// Mock snapshot — 104 breakers across 9 boards (MB01: 12, MB02–MB08: 12 each,
// MB09: 8 = 12*8 + 8 = 104 total)
// ---------------------------------------------------------------------------
const BOARD_SIZES: Record<string, number> = {
  MB01: 12,
  MB02: 12,
  MB03: 12,
  MB04: 12,
  MB05: 12,
  MB06: 12,
  MB07: 12,
  MB08: 12,
  MB09: 8,
};

function buildMockSnapshot(): BreakerState[] {
  const breakers: BreakerState[] = [];
  for (const [board, count] of Object.entries(BOARD_SIZES)) {
    for (let i = 1; i <= count; i++) {
      const num = String(i).padStart(2, "0");
      const asset_id = `${board}-B${num}`;
      breakers.push({
        asset_id,
        label: asset_id,
        main_board_ref: board,
        state: "closed",
        comms_loss: false,
        last_seen: new Date().toISOString(),
      });
    }
  }
  return breakers;
}

// ---------------------------------------------------------------------------
// Derive WebSocket base URL from the current window origin (same-origin API).
// The api-client uses a relative /api path, so we use window.location.origin.
// ---------------------------------------------------------------------------
function getWsBaseUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}`;
}

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 500;

export function useScadaWebSocket(): { connectionStatus: string } {
  const { setSnapshot, applyUpdate, setConnectionStatus, connectionStatus } =
    useBreakerStore();

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const mockIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mockBreakersRef = useRef<BreakerState[]>([]);

  useEffect(() => {
    unmountedRef.current = false;

    // ------------------------------------------------------------------
    // MOCK MODE — VITE_MOCK_WS=true
    // ------------------------------------------------------------------
    if (import.meta.env.VITE_MOCK_WS === "true") {
      const snapshot = buildMockSnapshot();
      mockBreakersRef.current = [...snapshot];
      setSnapshot(snapshot);
      setConnectionStatus("connected");

      // Simulate a random breaker flipping to "tripped" every 5 seconds
      mockIntervalRef.current = setInterval(() => {
        if (unmountedRef.current) return;

        const breakers = mockBreakersRef.current;
        if (breakers.length === 0) return;

        const idx = Math.floor(Math.random() * breakers.length);
        const target = breakers[idx];
        if (target === undefined) return;

        // Toggle: if tripped → closed, else → tripped
        const nextState: BreakerState["state"] =
          target.state === "tripped" ? "closed" : "tripped";
        const now = new Date().toISOString();
        const updated: BreakerState = {
          asset_id: target.asset_id,
          label: target.label,
          main_board_ref: target.main_board_ref,
          comms_loss: target.comms_loss,
          state: nextState,
          last_seen: now,
        };
        mockBreakersRef.current = breakers.map((b, i) =>
          i === idx ? updated : b,
        );

        applyUpdate({
          type: "breaker_update",
          asset_id: updated.asset_id ?? "",
          label: updated.label ?? "",
          main_board_ref: updated.main_board_ref ?? "",
          state: updated.state as BreakerStateValue,
          comms_loss: updated.comms_loss ?? false,
          timestamp: now,
        });
      }, 5_000);

      return () => {
        unmountedRef.current = true;
        if (mockIntervalRef.current !== null) {
          clearInterval(mockIntervalRef.current);
        }
      };
    }

    // ------------------------------------------------------------------
    // REAL WebSocket connection
    // ------------------------------------------------------------------
    function connect() {
      if (unmountedRef.current) return;

      setConnectionStatus("connecting");

      const url = `${getWsBaseUrl()}/api/ws`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmountedRef.current) {
          ws.close();
          return;
        }
        backoffRef.current = INITIAL_BACKOFF_MS;
        setConnectionStatus("connected");
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        if (unmountedRef.current) return;

        let msg: ServerMessage;
        try {
          msg = JSON.parse(event.data) as ServerMessage;
        } catch {
          console.warn("[SCADA WS] Failed to parse message:", event.data);
          return;
        }

        switch (msg.type) {
          case "full_snapshot":
            setSnapshot(msg.breakers);
            break;
          case "breaker_update":
            applyUpdate(msg);
            break;
          case "comms_loss":
            console.warn(
              `[SCADA WS] Comms loss reported for gateway: ${msg.gateway_id} at ${msg.timestamp}`,
            );
            break;
          default:
            // Exhaustiveness guard — log unknown messages
            console.warn("[SCADA WS] Unknown message type:", msg);
        }
      };

      ws.onerror = () => {
        // onerror is always followed by onclose; handle reconnect there
        setConnectionStatus("error");
      };

      ws.onclose = (event) => {
        if (unmountedRef.current) return;

        // Code 1000 = normal closure (e.g. component unmounted via ws.close())
        if (event.code === 1000) return;

        setConnectionStatus("connecting"); // "RECONNECTING" state

        const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);

        console.info(`[SCADA WS] Reconnecting in ${delay}ms...`);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current !== null) {
        wsRef.current.onclose = null; // prevent reconnect loop on intentional close
        wsRef.current.close(1000);
      }
      setConnectionStatus("disconnected");
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { connectionStatus };
}
