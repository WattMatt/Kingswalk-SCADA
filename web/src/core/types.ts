// web/src/core/types.ts

export type UserRole = "admin" | "operator" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface ApiError {
  error: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mfaPending: boolean;
}

export interface MfaEnrollResponse {
  provisioning_uri: string;
}

export interface MfaConfirmResponse {
  recovery_codes: string[];
  message: string;
}

// ── Asset types ──────────────────────────────────────────────────────────────

export interface MainBoard {
  id: string;
  code: string;
  drawing: string;
  vlan_id: number;
  subnet: string;
  location: string | null;
}

export interface DistributionBoard {
  id: string;
  code: string;
  name: string | null;
  area_m2: number | null;
}

export interface Breaker {
  id: string;
  main_board_id: string;
  label: string;
  breaker_code: string;
  abb_family: string;
  rating_amp: number;
  poles: string;
  mp_code: string | null;
  essential_supply: boolean;
  device_ip: string | null;
  feeds_db: DistributionBoard | null;
}

export interface ScadaEvent {
  id: number;
  ts: string;
  asset_id: string | null;
  severity: "info" | "warning" | "error" | "critical";
  kind: string;
  message: string;
  payload: Record<string, unknown>;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export type BreakerLiveState =
  | "closed"
  | "open"
  | "tripped"
  | "comms_loss"
  | "unknown";

export interface BreakerState {
  breakerId: string;
  state: BreakerLiveState;
  lastUpdated: string; // ISO timestamp
}

// ── WebSocket message types ───────────────────────────────────────────────────

export interface StateSyncMessage {
  type: "state_sync";
  boards: MainBoard[];
  active_alarms: ScadaEvent[];
  ts: string;
}

export interface TelemetryUpdateMessage {
  type: "telemetry_update";
  samples: Array<{
    device_id: string;
    register_address: number;
    raw_value: number;
    ts: string;
  }>;
  ts: string;
}

export type WsMessage = StateSyncMessage | TelemetryUpdateMessage;
