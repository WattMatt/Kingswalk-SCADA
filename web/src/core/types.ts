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
}

export interface MfaEnrollResponse {
  provisioning_uri: string;
}

export interface MfaConfirmResponse {
  recovery_codes: string[];
  message: string;
}
