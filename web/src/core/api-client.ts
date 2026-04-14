// web/src/core/api-client.ts
import type { MfaConfirmResponse, MfaEnrollResponse, User } from "./types";

const BASE_URL = "/api";

function getCsrfToken(): string {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrf_token="));
  return match ? match.split("=").slice(1).join("=") : "";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (method !== "GET") {
    headers["X-CSRF-Token"] = getCsrfToken();
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "Unknown error" }));
    throw new Error((body as { error: string }).error ?? "Request failed");
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  login: (email: string, password: string) =>
    request<{ message?: string; mfa_required?: boolean }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    request<{ message: string }>("/auth/logout", { method: "POST" }),

  me: () => request<User>("/auth/me"),

  onboard: (token: string, full_name: string, password: string) =>
    request<{ message: string; mfa_required: boolean }>("/auth/onboard", {
      method: "POST",
      body: JSON.stringify({ token, full_name, password }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  mfa: {
    enroll: () => request<MfaEnrollResponse>("/auth/mfa/enroll", { method: "POST" }),
    confirmEnrollment: (code: string) =>
      request<MfaConfirmResponse>("/auth/mfa/confirm-enrollment", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    verifyTotp: (code: string) =>
      request<{ message: string }>("/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    useRecoveryCode: (code: string) =>
      request<{ message: string }>("/auth/mfa/recovery", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
  },

  admin: {
    invite: (email: string, role: string) =>
      request<{ message: string }>("/admin/invite", {
        method: "POST",
        body: JSON.stringify({ email, role }),
      }),
  },
};
