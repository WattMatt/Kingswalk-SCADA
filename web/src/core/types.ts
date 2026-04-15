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

// ---------------------------------------------------------------------------
// SCADA / Breaker types — shared contract with backend WebSocket API
// ---------------------------------------------------------------------------

export type BreakerStateValue = "closed" | "open" | "tripped" | "unknown";

export interface BreakerState {
  asset_id: string;
  label: string;           // e.g. "MB01-B01"
  main_board_ref: string;  // e.g. "MB01"
  state: BreakerStateValue;
  comms_loss: boolean;
  last_seen: string | null;
}

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
