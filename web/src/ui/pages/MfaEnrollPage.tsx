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

  // ── Recovery codes step ────────────────────────────────────────────────────

  if (step === "recovery") {
    return (
      <div style={pageStyle}>
        <div style={{ ...cardStyle, maxWidth: "480px" }}>
          <div aria-hidden style={amberBarStyle} />

          <h1 style={headingStyle}>Save Your Recovery Codes</h1>
          <p style={{ ...subStyle, color: "var(--red-fault)", marginBottom: "1.25rem" }}>
            These codes will NOT be shown again. Store them somewhere safe.
          </p>

          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-mid)",
              padding: "1rem",
              marginBottom: "1.5rem",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              letterSpacing: "0.05em",
              color: "var(--text-mid)",
              lineHeight: 1.9,
            }}
          >
            {recoveryCodes.map((c) => <div key={c}>{c}</div>)}
          </div>

          <button
            onClick={() => navigate("/dashboard")}
            style={{ ...submitStyle, background: "var(--amber)", cursor: "pointer" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#ffbc1f"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--amber)"; }}
          >
            I've saved my recovery codes — continue
          </button>
        </div>
      </div>
    );
  }

  // ── QR / confirm step ──────────────────────────────────────────────────────

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div aria-hidden style={amberBarStyle} />

        <div style={{ marginBottom: "1.75rem" }}>
          <h1 style={headingStyle}>Set Up Two-Factor Authentication</h1>
          <p style={subStyle}>
            Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
          </p>
        </div>

        <div style={{ height: "1px", background: "var(--border-dim)", marginBottom: "1.5rem" }} />

        {/* QR code panel */}
        {provisioningUri ? (
          <div
            style={{
              background: "#fff",
              padding: "1rem",
              display: "flex",
              justifyContent: "center",
              marginBottom: "1.5rem",
            }}
          >
            <QRCodeSVG value={provisioningUri} size={180} />
          </div>
        ) : (
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-dim)",
              height: "120px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "1.5rem",
              fontFamily: "var(--font-mono)",
              fontSize: "0.65rem",
              letterSpacing: "0.1em",
              color: "var(--text-dim)",
              textTransform: "uppercase",
            }}
          >
            {error ?? "Loading…"}
          </div>
        )}

        <form onSubmit={handleConfirm} style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label htmlFor="code" style={labelStyle}>Enter the 6-digit code to confirm</label>
            <input
              id="code"
              type="text"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="000000"
              maxLength={6}
              style={{ ...inputStyle, textAlign: "center", fontSize: "1.2rem", letterSpacing: "0.3em" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </div>

          {error && <div style={errorStyle}>{error}</div>}

          <button
            type="submit"
            disabled={loading || !provisioningUri}
            style={{
              ...submitStyle,
              background: loading || !provisioningUri ? "var(--amber-dim)" : "var(--amber)",
              cursor: loading || !provisioningUri ? "not-allowed" : "pointer",
            }}
            onMouseEnter={(e) => { if (!loading && provisioningUri) e.currentTarget.style.background = "#ffbc1f"; }}
            onMouseLeave={(e) => { if (!loading && provisioningUri) e.currentTarget.style.background = "var(--amber)"; }}
          >
            {loading ? "Confirming…" : "Confirm & Enable MFA"}
          </button>
        </form>
      </div>
    </div>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--bg-void)",
  padding: "2rem",
};

const cardStyle: React.CSSProperties = {
  width: "100%",
  maxWidth: "380px",
  background: "var(--bg-panel)",
  border: "1px solid var(--border-mid)",
  padding: "2.5rem 2rem",
  position: "relative",
};

const amberBarStyle: React.CSSProperties = {
  position: "absolute",
  top: 0, left: 0, right: 0,
  height: "2px",
  background: "linear-gradient(90deg, var(--amber) 0%, transparent 80%)",
};

const headingStyle: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontWeight: 700,
  fontSize: "1.3rem",
  letterSpacing: "0.06em",
  color: "var(--text-hi)",
  marginBottom: "0.3rem",
};

const subStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.68rem",
  letterSpacing: "0.06em",
  color: "var(--text-dim)",
  lineHeight: 1.5,
};

const labelStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.68rem",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "var(--text-mid)",
};

const inputStyle: React.CSSProperties = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border-mid)",
  padding: "0.55rem 0.75rem",
  fontFamily: "var(--font-mono)",
  fontSize: "0.82rem",
  color: "var(--text-hi)",
  outline: "none",
  width: "100%",
  transition: "border-color 0.15s, box-shadow 0.15s",
};

const errorStyle: React.CSSProperties = {
  background: "rgba(242,54,69,0.10)",
  border: "1px solid rgba(242,54,69,0.35)",
  padding: "0.6rem 0.75rem",
  fontFamily: "var(--font-mono)",
  fontSize: "0.72rem",
  color: "#f87171",
};

const submitStyle: React.CSSProperties = {
  color: "#000",
  border: "none",
  padding: "0.65rem 1rem",
  fontFamily: "var(--font-display)",
  fontWeight: 700,
  fontSize: "0.85rem",
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  transition: "background 0.15s",
  width: "100%",
};
