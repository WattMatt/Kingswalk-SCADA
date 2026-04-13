// web/src/core/auth-store.ts
import { create } from "zustand";
import type { AuthState, User } from "./types";

interface AuthActions {
  setUser: (user: User) => void;
  clearUser: () => void;
  setLoading: (loading: boolean) => void;
  setMfaPending: (pending: boolean) => void;
}

export const useAuthStore = create<AuthState & AuthActions>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  mfaPending: false,

  setUser: (user) => set({ user, isAuthenticated: true, isLoading: false }),
  clearUser: () => set({ user: null, isAuthenticated: false, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
  setMfaPending: (mfaPending) => set({ mfaPending }),
}));
