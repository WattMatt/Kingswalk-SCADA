// web/src/ui/App.tsx
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { TrendsPage } from "./pages/TrendsPage";
import { LoginPage } from "./pages/LoginPage";
import { MfaChallengePage } from "./pages/MfaChallengePage";
import { MfaEnrollPage } from "./pages/MfaEnrollPage";
import { OnboardPage } from "./pages/OnboardPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";

export function App() {
  const { setUser, clearUser } = useAuthStore();

  // Restore auth state on page load
  useEffect(() => {
    apiClient
      .me()
      .then(setUser)
      .catch(() => clearUser());
  }, [setUser, clearUser]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/onboard" element={<OnboardPage />} />
        <Route path="/mfa" element={<MfaChallengePage />} />
        <Route
          path="/mfa/enroll"
          element={
            <ProtectedRoute>
              <MfaEnrollPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/trends"
          element={
            <ProtectedRoute>
              <TrendsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
