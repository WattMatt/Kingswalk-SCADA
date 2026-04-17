// web/src/core/breaker-store.ts
import { create } from "zustand";
import type { BreakerState, BreakerUpdate } from "./types";

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface BreakerStore {
  breakers: Record<string, BreakerState>; // keyed by asset_id
  connectionStatus: ConnectionStatus;
  lastSnapshotAt: string | null;

  setSnapshot: (breakers: BreakerState[]) => void;
  applyUpdate: (update: BreakerUpdate) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;

  // Derived helpers
  getBreakersByBoard: () => Record<string, BreakerState[]>; // keyed by main_board_ref
  getAlarmCount: () => number; // count of tripped breakers
}

export const useBreakerStore = create<BreakerStore>((set, get) => ({
  breakers: {},
  connectionStatus: "connecting",
  lastSnapshotAt: null,

  setSnapshot: (breakers) => {
    const mapped: Record<string, BreakerState> = {};
    for (const b of breakers) {
      mapped[b.asset_id] = b;
    }
    set({ breakers: mapped, lastSnapshotAt: new Date().toISOString() });
  },

  applyUpdate: (update) => {
    set((state) => ({
      breakers: {
        ...state.breakers,
        [update.asset_id]: {
          asset_id: update.asset_id,
          label: update.label,
          main_board_ref: update.main_board_ref,
          state: update.state,
          comms_loss: update.comms_loss,
          last_seen: update.timestamp,
        },
      },
    }));
  },

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  getBreakersByBoard: () => {
    const { breakers } = get();
    const groups: Record<string, BreakerState[]> = {};
    for (const breaker of Object.values(breakers)) {
      const board = breaker.main_board_ref;
      if (!groups[board]) {
        groups[board] = [];
      }
      groups[board].push(breaker);
    }
    // Sort breakers within each board by label
    for (const board of Object.keys(groups)) {
      groups[board]?.sort((a, b) => a.label.localeCompare(b.label));
    }
    return groups;
  },

  getAlarmCount: () => {
    const { breakers } = get();
    return Object.values(breakers).filter((b) => b.state === "tripped").length;
  },
}));
