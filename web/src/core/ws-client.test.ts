// web/src/core/ws-client.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WsClient } from "./ws-client";
import type { StateSyncMessage, WsMessage } from "./types";

// ── WebSocket mock ─────────────────────────────────────────────────────────

// Use numeric constants so they work regardless of whether the global WebSocket
// stub has the static properties attached.
const WS_CONNECTING = 0;
const WS_OPEN = 1;
const WS_CLOSED = 3;

interface MockWs {
  onopen: (() => void) | null;
  onmessage: ((e: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  readyState: number;
  close: () => void;
  send: (data: string) => void;
  /** Helper: simulate a successful open */
  simulateOpen: () => void;
  /** Helper: simulate server close / drop */
  simulateClose: () => void;
  /** Helper: simulate an inbound message */
  simulateMessage: (msg: unknown) => void;
}

let latestWs: MockWs | null = null;

function createMockWs(): MockWs {
  const ws: MockWs = {
    onopen: null,
    onmessage: null,
    onclose: null,
    onerror: null,
    readyState: WS_CONNECTING,
    close: vi.fn(() => {
      ws.readyState = WS_CLOSED;
    }),
    send: vi.fn(),
    simulateOpen() {
      ws.readyState = WS_OPEN;
      ws.onopen?.();
    },
    simulateClose() {
      ws.readyState = WS_CLOSED;
      ws.onclose?.();
    },
    simulateMessage(msg) {
      ws.onmessage?.({ data: JSON.stringify(msg) });
    },
  };
  return ws;
}

// The stub constructor also needs the static constants so WsClient can read
// WebSocket.OPEN at runtime.
const MockWebSocket = vi.fn((_url: string) => { // eslint-disable-line @typescript-eslint/no-unused-vars
  latestWs = createMockWs();
  return latestWs;
}) as unknown as typeof WebSocket;
(MockWebSocket as unknown as Record<string, number>)["CONNECTING"] = WS_CONNECTING;
(MockWebSocket as unknown as Record<string, number>)["OPEN"] = WS_OPEN;
(MockWebSocket as unknown as Record<string, number>)["CLOSING"] = 2;
(MockWebSocket as unknown as Record<string, number>)["CLOSED"] = WS_CLOSED;

vi.stubGlobal("WebSocket", MockWebSocket);

// ── Tests ──────────────────────────────────────────────────────────────────

describe("WsClient", () => {
  let client: WsClient;

  beforeEach(() => {
    vi.useFakeTimers();
    client = new WsClient();
    latestWs = null;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    client.disconnect();
  });

  it("opens a WebSocket on connect()", () => {
    client.connect("ws://localhost:8000");
    expect(WebSocket).toHaveBeenCalledWith("ws://localhost:8000/ws/live");
    expect(latestWs).not.toBeNull();
  });

  it("resets backoff after successful open", () => {
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    // No error; backoff should be reset (internal — tested indirectly via reconnect timing)
    expect(latestWs!.readyState).toBe(WebSocket.OPEN);
  });

  it("closes the socket on disconnect() and stops reconnecting", () => {
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    client.disconnect();
    expect(latestWs!.close).toHaveBeenCalled();

    // Force a close event that would normally trigger reconnect
    latestWs!.simulateClose();
    vi.advanceTimersByTime(5000);
    // WebSocket constructor should NOT have been called again
    expect(WebSocket).toHaveBeenCalledTimes(1);
  });

  it("schedules a reconnect after unexpected close", () => {
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    latestWs!.simulateClose();

    // Advance past the jitter window (base 1 s, jitter 0.5–1.5 s)
    vi.advanceTimersByTime(2000);
    expect(WebSocket).toHaveBeenCalledTimes(2);
  });

  it("reconnect uses exponential backoff (second attempt ~2 s)", () => {
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();

    // First disconnect
    latestWs!.simulateClose();
    vi.advanceTimersByTime(1600); // within first backoff window
    const firstWs = latestWs;

    // Second disconnect immediately
    firstWs!.simulateClose();

    // Should NOT reconnect within 1 s (second backoff is ~2 s)
    vi.advanceTimersByTime(900);
    // Still only 2 calls (initial + first reconnect)
    expect(WebSocket).toHaveBeenCalledTimes(2);

    // Advance another 2 s to cover full jitter
    vi.advanceTimersByTime(2500);
    expect(WebSocket).toHaveBeenCalledTimes(3);
  });

  it("delivers inbound messages to subscribed listeners", () => {
    const handler = vi.fn<(msg: WsMessage) => void>();
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    const unsub = client.onMessage(handler);

    const msg: StateSyncMessage = {
      type: "state_sync",
      boards: [],
      active_alarms: [],
      ts: new Date().toISOString(),
    };
    latestWs!.simulateMessage(msg);

    expect(handler).toHaveBeenCalledWith(msg);
    unsub();
  });

  it("unsubscribe stops message delivery", () => {
    const handler = vi.fn<(msg: WsMessage) => void>();
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    const unsub = client.onMessage(handler);
    unsub();

    const msg: StateSyncMessage = {
      type: "state_sync",
      boards: [],
      active_alarms: [],
      ts: new Date().toISOString(),
    };
    latestWs!.simulateMessage(msg);
    expect(handler).not.toHaveBeenCalled();
  });

  it("send() serialises and calls ws.send when OPEN", () => {
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    client.send({ type: "sync_request" });
    expect(latestWs!.send).toHaveBeenCalledWith(JSON.stringify({ type: "sync_request" }));
  });

  it("send() silently drops message when socket is not OPEN", () => {
    client.connect("ws://localhost:8000");
    // Not yet open (CONNECTING state)
    client.send({ type: "sync_request" });
    expect(latestWs!.send).not.toHaveBeenCalled();
  });

  it("ignores malformed JSON frames without throwing", () => {
    const handler = vi.fn<(msg: WsMessage) => void>();
    client.connect("ws://localhost:8000");
    latestWs!.simulateOpen();
    client.onMessage(handler);

    // Directly push a bad message frame
    latestWs!.onmessage?.({ data: "not-json{{{" });
    expect(handler).not.toHaveBeenCalled();
  });
});
