// web/src/ui/pages/MfaEnrollPage.tsx
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { apiClient } from "@/core/api-client";

type Step = "qr" | "recovery";

export function MfaEnrollPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("qr");
  const [provisioningUri, setProvisioningUri] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.mfa.enroll().then((r) => setProvisioningUri(r.provisioning_uri)).catch(() => {
      setError("Failed to start MFA enrollment. Please try again.");
    });
  }, []);

  async function handleConfirm(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await apiClient.mfa.confirmEnrollment(code);
      setRecoveryCodes(result.recovery_codes);
      setStep("recovery");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code");
    } finally {
      setLoading(false);
    }
  }

  if (step === "recovery") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
          <h1 className="mb-2 text-xl font-semibold text-white">Save Your Recovery Codes</h1>
          <p className="mb-4 text-sm text-red-400">
            These codes will NOT be shown again. Store them somewhere safe.
          </p>
          <div className="mb-6 rounded-lg bg-slate-800 p-4 font-mono text-sm text-slate-200">
            {recoveryCodes.map((c) => (
              <div key={c} className="py-0.5">{c}</div>
            ))}
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            I've saved my recovery codes — continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <h1 className="mb-2 text-xl font-semibold text-white">Set Up Two-Factor Authentication</h1>
        <p className="mb-4 text-sm text-slate-400">
          Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
        </p>

        {provisioningUri ? (
          <div className="mb-4 flex justify-center rounded-lg bg-white p-4">
            <QRCodeSVG value={provisioningUri} size={180} />
          </div>
        ) : (
          <div className="mb-4 flex h-32 items-center justify-center rounded-lg bg-slate-800">
            <p className="text-sm text-slate-400">{error ?? "Loading…"}</p>
          </div>
        )}

        <form onSubmit={handleConfirm} className="space-y-4">
          <div>
            <label htmlFor="code" className="mb-1 block text-sm text-slate-300">
              Enter the 6-digit code to confirm
            </label>
            <input
              id="code"
              type="text"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-center text-lg font-mono tracking-widest text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
              placeholder="000000"
              maxLength={6}
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-950 px-3 py-2 text-sm text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !provisioningUri}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Confirming…" : "Confirm & Enable MFA"}
          </button>
        </form>
      </div>
    </div>
  );
}
