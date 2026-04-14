import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "./auth-store";
import type { User } from "./types";

const testUser: User = {
  id: "u-1",
  email: "operator@kingswalk.co.za",
  full_name: "Test Operator",
  role: "operator",
};

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      mfaPending: false,
    });
  });

  it("starts with no authenticated user", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(true);
  });

  it("setUser authenticates the user", () => {
    useAuthStore.getState().setUser(testUser);
    const state = useAuthStore.getState();
    expect(state.user).toEqual(testUser);
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
  });

  it("clearUser removes authentication", () => {
    useAuthStore.getState().setUser(testUser);
    useAuthStore.getState().clearUser();
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it("setLoading updates the loading flag", () => {
    useAuthStore.getState().setLoading(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("setMfaPending updates the MFA pending flag", () => {
    useAuthStore.getState().setMfaPending(true);
    expect(useAuthStore.getState().mfaPending).toBe(true);
  });
});
