// web/src/core/alarm-store.ts
import { create } from "zustand";
import { apiClient } from "./api-client";
import type { ScadaEvent } from "./types";

interface AlarmStore {
  alarms: ScadaEvent[];
  isConnected: boolean;
  isReconnecting: boolean;
  /** Replace the entire alarm list (used on state_sync). */
  setAlarms: (alarms: ScadaEvent[]) => void;
  /** Upsert a single alarm into the list. */
  addOrUpdateAlarm: (alarm: ScadaEvent) => void;
  /** Call the ack API then stamp the local record. */
  ackAlarm: (eventId: number) => Promise<void>;
  setConnected: (v: boolean) => void;
  setReconnecting: (v: boolean) => void;
}

export const useAlarmStore = create<AlarmStore>((set, get) => ({
  alarms: [],
  isConnected: false,
  isReconnecting: false,

  setAlarms: (alarms) => set({ alarms }),

  addOrUpdateAlarm: (alarm) => {
    const existing = get().alarms;
    const idx = existing.findIndex((a) => a.id === alarm.id);
    if (idx === -1) {
      set({ alarms: [alarm, ...existing] });
    } else {
      const updated = [...existing];
      updated[idx] = alarm;
      set({ alarms: updated });
    }
  },

  ackAlarm: async (eventId) => {
    await apiClient.events.ack(eventId);
    const now = new Date().toISOString();
    set((state) => ({
      alarms: state.alarms.map((a) =>
        a.id === eventId
          ? { ...a, acknowledged_at: now, acknowledged_by: "current_user" }
          : a,
      ),
    }));
  },

  setConnected: (isConnected) => set({ isConnected }),
  setReconnecting: (isReconnecting) => set({ isReconnecting }),
}));
