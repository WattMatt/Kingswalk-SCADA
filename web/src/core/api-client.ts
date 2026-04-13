// web/src/core/api-client.ts
import type { User } from "./types";

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
    request<{ message: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    request<{ message: string }>("/auth/logout", { method: "POST" }),

  me: () => request<User>("/auth/me"),
};
