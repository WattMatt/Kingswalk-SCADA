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

// BreakerLiveState includes comms_loss as a display state (superset of BreakerStateValue)
export type BreakerLiveState =
  | "closed"
  | "open"
  | "tripped"
  | "comms_loss"
  | "unknown";

// BreakerStateValue is the wire protocol value (backend WebSocket API)
export type BreakerStateValue = "closed" | "open" | "tripped" | "unknown";

// BreakerState covers both the legacy (breakerId/lastUpdated) shape and the
// live WebSocket shape (asset_id/label/main_board_ref/comms_loss/last_seen).
export interface BreakerState {
  // Legacy dashboard shape
  breakerId?: string;
  lastUpdated?: string; // ISO timestamp
  // WebSocket API shape
  asset_id?: string;
  label?: string;           // e.g. "MB01-B01"
  main_board_ref?: string;  // e.g. "MB01"
  state: BreakerLiveState | BreakerStateValue;
  comms_loss?: boolean;
  last_seen?: string | null;
}

// ── Telemetry / PQ trends types ───────────────────────────────────────────────

export type MetricName =
  | "voltage_ln"
  | "voltage_ll"
  | "current"
  | "frequency"
  | "power_factor"
  | "thd";

export const METRIC_LABELS: Record<MetricName, string> = {
  voltage_ln:   "Voltage L-N",
  voltage_ll:   "Voltage L-L",
  current:      "Current",
  frequency:    "Frequency",
  power_factor: "Power Factor",
  thd:          "THD Voltage",
};

export interface TelemetryPoint {
  ts: string;    // ISO 8601 UTC
  value: number; // Scaled engineering unit
}

export interface TelemetrySeries {
  label: string;
  register_addr: number;
  data: TelemetryPoint[];
}

export interface TelemetryResponse {
  board_id: string;
  board_code: string;
  metric: MetricName;
  unit: string;
  labels: string[];
  series: TelemetrySeries[];
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

// ---------------------------------------------------------------------------
// Real-time breaker WebSocket API — shared contract with backend ingest layer
// ---------------------------------------------------------------------------

export interface FullSnapshot {
  type: "full_snapshot";
  timestamp: string;
  breakers: BreakerState[];
}

export interface BreakerUpdate {
  type: "breaker_update";
  asset_id: string;
  label: string;
  main_board_ref: string;
  state: BreakerStateValue;
  comms_loss: boolean;
  timestamp: string;
}

export interface CommsLoss {
  type: "comms_loss";
  gateway_id: string;
  timestamp: string;
}

export type ServerMessage = FullSnapshot | BreakerUpdate | CommsLoss;
