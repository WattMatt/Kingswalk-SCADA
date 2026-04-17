// web/src/core/api-client.ts
import type {
  Breaker,
  MainBoard,
  MetricName,
  MfaConfirmResponse,
  MfaEnrollResponse,
  ScadaEvent,
  TelemetryResponse,
  User,
  UserRole,
} from "./types";

const BASE_URL = "/api";

// ---------------------------------------------------------------------------
// MOCK MODE — active when VITE_MOCK_WS=true (no real backend required)
// ---------------------------------------------------------------------------
const MOCK = import.meta.env.VITE_MOCK_WS === "true";

const MOCK_USER: User = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "demo@kingswalk.local",
  full_name: "Demo Operator",
  role: "admin",
};

const MOCK_BOARDS: MainBoard[] = [
  { id: "b1", code: "MB01", drawing: "SLD-MB01", vlan_id: 10, subnet: "10.10.1.0/24", location: "Sub A" },
  { id: "b2", code: "MB02", drawing: "SLD-MB02", vlan_id: 20, subnet: "10.10.2.0/24", location: "Sub B" },
];

const MOCK_BREAKERS: Breaker[] = Array.from({ length: 12 }, (_, i) => ({
  id: `brk-${i + 1}`,
  main_board_id: "b1",
  label: `MB01-B${String(i + 1).padStart(2, "0")}`,
  breaker_code: `B${String(i + 1).padStart(2, "0")}`,
  abb_family: "Tmax XT",
  rating_amp: 63,
  poles: "3P",
  mp_code: null,
  essential_supply: false,
  device_ip: null,
  feeds_db: null,
}));

const MOCK_TELEMETRY: TelemetryResponse = {
  board_id: "b1",
  board_code: "MB01",
  metric: "voltage_ln",
  unit: "V",
  labels: ["L1", "L2", "L3"],
  series: ["L1", "L2", "L3"].map((label, idx) => ({
    label,
    register_addr: 0x0000 + idx * 2,
    data: Array.from({ length: 48 }, (_, i) => ({
      ts: new Date(Date.now() - (47 - i) * 15 * 60 * 1000).toISOString(),
      value: 228 + Math.sin(i * 0.3 + idx) * 5,
    })),
  })),
};

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

// Tiny helper so mock functions feel like real async calls
function mockResolve<T>(value: T): Promise<T> {
  return Promise.resolve(value);
}

export const apiClient = {
  login: (_email: string, _password: string) =>
    MOCK
      ? mockResolve<{ message?: string; mfa_required?: boolean }>({ mfa_required: false })
      : request<{ message?: string; mfa_required?: boolean }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: _email, password: _password }),
        }),

  logout: () =>
    MOCK
      ? mockResolve<{ message: string }>({ message: "OK" })
      : request<{ message: string }>("/auth/logout", { method: "POST" }),

  me: () =>
    MOCK ? mockResolve<User>(MOCK_USER) : request<User>("/auth/me"),

  onboard: (token: string, full_name: string, password: string) =>
    MOCK
      ? mockResolve<{ message: string; mfa_required: boolean }>({ message: "OK", mfa_required: false })
      : request<{ message: string; mfa_required: boolean }>("/auth/onboard", {
          method: "POST",
          body: JSON.stringify({ token, full_name, password }),
        }),

  forgotPassword: (email: string) =>
    MOCK
      ? mockResolve<{ message: string }>({ message: "Reset email sent (mock)" })
      : request<{ message: string }>("/auth/password-reset/request", {
          method: "POST",
          body: JSON.stringify({ email }),
        }),

  resetPassword: (token: string, password: string) =>
    MOCK
      ? mockResolve<{ message: string }>({ message: "Password reset (mock)" })
      : request<{ message: string }>("/auth/password-reset/confirm", {
          method: "POST",
          body: JSON.stringify({ token, password }),
        }),

  mfa: {
    enroll: () =>
      MOCK
        ? mockResolve<MfaEnrollResponse>({ provisioning_uri: "otpauth://totp/Kingswalk:demo@kingswalk.local?secret=JBSWY3DPEHPK3PXP&issuer=Kingswalk" })
        : request<MfaEnrollResponse>("/auth/mfa/enroll", { method: "POST" }),
    confirmEnrollment: (code: string) =>
      MOCK
        ? mockResolve<MfaConfirmResponse>({ message: "MFA enrolled (mock)", recovery_codes: ["AAAA-BBBB", "CCCC-DDDD", "EEEE-FFFF", "GGGG-HHHH", "IIII-JJJJ", "KKKK-LLLL", "MMMM-NNNN", "OOOO-PPPP"] })
        : request<MfaConfirmResponse>("/auth/mfa/confirm-enrollment", {
            method: "POST",
            body: JSON.stringify({ code }),
          }),
    verifyTotp: (code: string) =>
      MOCK
        ? mockResolve<{ message: string }>({ message: "Verified (mock)" })
        : request<{ message: string }>("/auth/mfa/verify", {
            method: "POST",
            body: JSON.stringify({ code }),
          }),
    useRecoveryCode: (code: string) =>
      MOCK
        ? mockResolve<{ message: string }>({ message: "Recovery code accepted (mock)" })
        : request<{ message: string }>("/auth/mfa/recovery", {
            method: "POST",
            body: JSON.stringify({ code }),
          }),
  },

  admin: {
    invite: (email: string, role: UserRole) =>
      MOCK
        ? mockResolve<{ message: string }>({ message: `Invite sent to ${email} as ${role} (mock)` })
        : request<{ message: string }>("/admin/invite", {
            method: "POST",
            body: JSON.stringify({ email, role }),
          }),
  },

  assets: {
    boards: () =>
      MOCK ? mockResolve<MainBoard[]>(MOCK_BOARDS) : request<MainBoard[]>("/assets/boards"),
    boardBreakers: (_boardId: string) =>
      MOCK
        ? mockResolve<Breaker[]>(MOCK_BREAKERS)
        : request<Breaker[]>(`/assets/boards/${_boardId}/breakers`),
    breakers: (board?: string) =>
      MOCK
        ? mockResolve<Breaker[]>(MOCK_BREAKERS)
        : request<Breaker[]>(
            `/assets/breakers${board ? `?board=${encodeURIComponent(board)}` : ""}`,
          ),
  },

  events: {
    list: (severity?: string) =>
      MOCK
        ? mockResolve<ScadaEvent[]>([])
        : request<ScadaEvent[]>(`/events${severity ? `?severity=${severity}` : ""}`),
    ack: (eventId: number) =>
      MOCK
        ? mockResolve<{ message: string }>({ message: "Acknowledged (mock)" })
        : request<{ message: string }>(`/events/${eventId}/ack`, { method: "POST" }),
  },

  telemetry: {
    query: (params: {
      boardId: string;
      metric?: MetricName;
      start?: string;    // ISO 8601
      end?: string;      // ISO 8601
      bucketMinutes?: number;
    }): Promise<TelemetryResponse> => {
      if (MOCK) return mockResolve<TelemetryResponse>({ ...MOCK_TELEMETRY, board_id: params.boardId, metric: params.metric ?? "voltage_ln" });
      const qs = new URLSearchParams({
        board_id: params.boardId,
        ...(params.metric          && { metric: params.metric }),
        ...(params.start           && { start: params.start }),
        ...(params.end             && { end: params.end }),
        ...(params.bucketMinutes != null && {
          bucket_minutes: String(params.bucketMinutes),
        }),
      });
      return request<TelemetryResponse>(`/telemetry?${qs.toString()}`);
    },
  },
};
