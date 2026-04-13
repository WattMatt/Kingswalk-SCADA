// web/src/ui/pages/MfaChallengePage.tsx
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";

export function MfaChallengePage() {
  const navigate = useNavigate();
  const { mfaPending, setMfaPending } = useAuthStore();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);

  if (!mfaPending) {
    return <Navigate to="/login" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (useRecovery) {
        await apiClient.mfa.useRecoveryCode(code);
      } else {
        await apiClient.mfa.verifyTotp(code);
      }
      setMfaPending(false);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <h1 className="mb-2 text-xl font-semibold text-white">Two-Factor Verification</h1>
        <p className="mb-6 text-sm text-slate-400">
          {useRecovery ? "Enter a recovery code" : "Enter the 6-digit code from your authenticator app"}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="code" className="mb-1 block text-sm text-slate-300">
              {useRecovery ? "Recovery code" : "Authentication code"}
            </label>
            <input
              id="code"
              type="text"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-center text-lg font-mono tracking-widest text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
              placeholder={useRecovery ? "XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX" : "000000"}
              maxLength={useRecovery ? 39 : 6}
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-950 px-3 py-2 text-sm text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Verifying…" : "Verify"}
          </button>
        </form>

        <button
          onClick={() => { setUseRecovery((v) => !v); setCode(""); setError(null); }}
          className="mt-4 w-full text-center text-sm text-slate-400 hover:text-slate-300"
        >
          {useRecovery ? "Use authenticator app instead" : "Use a recovery code instead"}
        </button>

        <button
          onClick={() => navigate("/login")}
          className="mt-2 w-full text-center text-sm text-slate-500 hover:text-slate-400"
        >
          Back to login
        </button>
      </div>
    </div>
  );
}
