// web/src/core/alarm-store.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAlarmStore } from "./alarm-store";
import type { ScadaEvent } from "./types";

// ── Mock api-client ────────────────────────────────────────────────────────

vi.mock("./api-client", () => ({
  apiClient: {
    events: {
      ack: vi.fn().mockResolvedValue({ message: "acknowledged" }),
    },
  },
}));

// ── Helpers ────────────────────────────────────────────────────────────────

function makeAlarm(overrides: Partial<ScadaEvent> = {}): ScadaEvent {
  return {
    id: 1,
    ts: "2026-04-16T10:00:00Z",
    asset_id: null,
    severity: "warning",
    kind: "THRESHOLD_BREACH",
    message: "Test alarm",
    payload: {},
    acknowledged_by: null,
    acknowledged_at: null,
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("useAlarmStore", () => {
  beforeEach(() => {
    useAlarmStore.setState({
      alarms: [],
      isConnected: false,
      isReconnecting: false,
    });
    vi.clearAllMocks();
  });

  it("starts empty", () => {
    expect(useAlarmStore.getState().alarms).toHaveLength(0);
  });

  it("setAlarms replaces the entire list", () => {
    const a1 = makeAlarm({ id: 1 });
    const a2 = makeAlarm({ id: 2 });
    useAlarmStore.getState().setAlarms([a1, a2]);
    expect(useAlarmStore.getState().alarms).toEqual([a1, a2]);

    // Replace with a different set
    const a3 = makeAlarm({ id: 3 });
    useAlarmStore.getState().setAlarms([a3]);
    expect(useAlarmStore.getState().alarms).toEqual([a3]);
  });

  it("addOrUpdateAlarm prepends a new alarm", () => {
    const a1 = makeAlarm({ id: 1 });
    useAlarmStore.getState().setAlarms([a1]);
    const a2 = makeAlarm({ id: 2, message: "Second" });
    useAlarmStore.getState().addOrUpdateAlarm(a2);

    const { alarms } = useAlarmStore.getState();
    expect(alarms).toHaveLength(2);
    expect(alarms[0]).toEqual(a2); // prepended
    expect(alarms[1]).toEqual(a1);
  });

  it("addOrUpdateAlarm replaces an existing alarm in place", () => {
    const a1 = makeAlarm({ id: 1, message: "Original" });
    useAlarmStore.getState().setAlarms([a1]);

    const updated = makeAlarm({ id: 1, message: "Updated" });
    useAlarmStore.getState().addOrUpdateAlarm(updated);

    const { alarms } = useAlarmStore.getState();
    expect(alarms).toHaveLength(1);
    expect(alarms[0]?.message).toBe("Updated");
  });

  it("ackAlarm calls the API and stamps acknowledged_at on the local record", async () => {
    const { apiClient } = await import("./api-client");
    const a1 = makeAlarm({ id: 42 });
    useAlarmStore.getState().setAlarms([a1]);

    await useAlarmStore.getState().ackAlarm(42);

    expect(apiClient.events.ack).toHaveBeenCalledWith(42);
    const { alarms } = useAlarmStore.getState();
    expect(alarms[0]?.acknowledged_at).not.toBeNull();
    expect(alarms[0]?.acknowledged_by).toBe("current_user");
  });

  it("ackAlarm does not touch unrelated alarms", async () => {
    const a1 = makeAlarm({ id: 1 });
    const a2 = makeAlarm({ id: 2 });
    useAlarmStore.getState().setAlarms([a1, a2]);

    await useAlarmStore.getState().ackAlarm(1);

    const { alarms } = useAlarmStore.getState();
    expect(alarms[0]?.acknowledged_at).not.toBeNull();
    expect(alarms[1]?.acknowledged_at).toBeNull();
  });

  it("setConnected and setReconnecting update their flags", () => {
    useAlarmStore.getState().setConnected(true);
    expect(useAlarmStore.getState().isConnected).toBe(true);

    useAlarmStore.getState().setReconnecting(true);
    expect(useAlarmStore.getState().isReconnecting).toBe(true);
  });
});
