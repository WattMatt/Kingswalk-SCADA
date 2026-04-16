// web/src/core/ws-client.ts
// Framework-agnostic WebSocket manager — no React imports.
import type { WsMessage } from "./types";

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

/**
 * Manages a persistent WebSocket connection with exponential back-off
 * reconnection (1 s → 2 s → 4 s … capped at 30 s, ±50 % jitter).
 */
export class WsClient {
  private ws: WebSocket | null = null;
  private backoffMs = BASE_BACKOFF_MS;
  private listeners: Array<(msg: WsMessage) => void> = [];
  private reconnecting = false;
  private url = "";
  private destroyed = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  /** Open (or re-open) the connection to `url`. */
  connect(url: string): void {
    this.url = url;
    this.destroyed = false;
    this.openSocket();
  }

  /** Permanently close the connection. No further reconnect attempts. */
  disconnect(): void {
    this.destroyed = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // prevent reconnect loop
      this.ws.close();
      this.ws = null;
    }
    this.reconnecting = false;
  }

  /**
   * Send a JSON-serialisable message if the socket is open.
   * Silently drops the message when not connected.
   */
  send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  /**
   * Subscribe to inbound messages.
   * @returns An unsubscribe function.
   */
  onMessage(handler: (msg: WsMessage) => void): () => void {
    this.listeners.push(handler);
    return () => {
      this.listeners = this.listeners.filter((h) => h !== handler);
    };
  }

  /** Send a sync_request to the server so it replays current state. */
  requestSync(): void {
    this.send({ type: "sync_request" });
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private openSocket(): void {
    if (this.destroyed) return;

    const ws = new WebSocket(this.url + "/ws/live");
    this.ws = ws;

    ws.onopen = () => {
      this.backoffMs = BASE_BACKOFF_MS;
      this.reconnecting = false;
    };

    ws.onmessage = (event: MessageEvent) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(event.data as string) as WsMessage;
      } catch {
        return; // ignore malformed frames
      }
      for (const listener of this.listeners) {
        listener(msg);
      }
    };

    ws.onerror = () => {
      // onclose fires right after onerror, let it handle reconnect
    };

    ws.onclose = () => {
      if (this.destroyed) return;
      this.reconnecting = true;
      this.scheduleReconnect();
    };
  }

  /**
   * Schedule a reconnect with exponential back-off and ±50 % jitter.
   * e.g. 1 s → 2 s → 4 s → 8 s → … → 30 s (all ± jitter).
   */
  private scheduleReconnect(): void {
    if (this.destroyed) return;

    const jitter = this.backoffMs * (0.5 + Math.random()); // 50–150 % of backoff
    const delay = Math.min(jitter, MAX_BACKOFF_MS);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.destroyed) {
        this.openSocket();
      }
    }, delay);

    // Double for next attempt, cap at max
    this.backoffMs = Math.min(this.backoffMs * 2, MAX_BACKOFF_MS);
  }
}

/** Singleton WsClient shared across the application. */
export const wsClient = new WsClient();
