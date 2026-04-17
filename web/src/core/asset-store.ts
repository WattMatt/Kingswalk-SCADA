// web/src/core/asset-store.ts
import { create } from "zustand";
import { apiClient } from "./api-client";
import type { Breaker, MainBoard } from "./types";

interface AssetStore {
  boards: MainBoard[];
  breakers: Breaker[];
  isLoading: boolean;
  error: string | null;
  /** Fetch all main boards from the API. */
  fetchBoards: () => Promise<void>;
  /**
   * Fetch breakers — all breakers when called with no argument,
   * or only those for a specific board when `boardId` is provided.
   */
  fetchBreakers: (boardId?: string) => Promise<void>;
}

export const useAssetStore = create<AssetStore>((set) => ({
  boards: [],
  breakers: [],
  isLoading: false,
  error: null,

  fetchBoards: async () => {
    set({ isLoading: true, error: null });
    try {
      const boards = await apiClient.assets.boards();
      set({ boards, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },

  fetchBreakers: async (boardId?: string) => {
    set({ isLoading: true, error: null });
    try {
      const breakers = boardId
        ? await apiClient.assets.boardBreakers(boardId)
        : await apiClient.assets.breakers();
      set({ breakers, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },
}));
