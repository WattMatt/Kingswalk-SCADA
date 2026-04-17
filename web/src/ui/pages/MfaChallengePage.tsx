// web/src/ui/pages/MfaChallengePage.tsx
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";
import type { User } from "@/core/types";

export function MfaChallengePage() {
  const navigate = useNavigate();
  const { mfaPending, setMfaPending, setUser } = useAuthStore();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);

  if (!mfaPending) return <Navigate to="/login" replace />;

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
      const user: User = await apiClient.me();
      setUser(user);
      setMfaPending(false);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div aria-hidden style={amberBarStyle} />

        <div style={{ marginBottom: "1.75rem" }}>
          <h1 style={headingStyle}>Two-Factor Verification</h1>
          <p style={subStyle}>
            {useRecovery
              ? "Enter a recovery code"
              : "Enter the 6-digit code from your authenticator app"}
          </p>
        </div>

        <div style={{ height: "1px", background: "var(--border-dim)", marginBottom: "1.5rem" }} />

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label htmlFor="code" style={labelStyle}>
              {useRecovery ? "Recovery code" : "Authentication code"}
            </label>
            <input
              id="code"
              type="text"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={useRecovery ? "XXXX-XXXX-XXXX-XXXX" : "000000"}
              maxLength={useRecovery ? 39 : 6}
              style={{ ...inputStyle, textAlign: "center", fontSize: "1.05rem", letterSpacing: "0.22em" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </div>

          {error && <div style={errorStyle}>{error}</div>}

          <button
            type="submit"
            disabled={loading}
            style={{ ...submitStyle, background: loading ? "var(--amber-dim)" : "var(--amber)", cursor: loading ? "not-allowed" : "pointer" }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#ffbc1f"; }}
            onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "var(--amber)"; }}
          >
            {loading ? "Verifying…" : "Verify"}
          </button>
        </form>

        <button
          onClick={() => { setUseRecovery((v) => !v); setCode(""); setError(null); }}
          style={ghostBtnStyle}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
        >
          {useRecovery ? "Use authenticator app instead" : "Use a recovery code instead"}
        </button>

        <button
          onClick={() => { setMfaPending(false); navigate("/login"); }}
          style={{ ...ghostBtnStyle, marginTop: "0.35rem" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
        >
          ← Back to login
        </button>
      </div>
    </div>
  );
}

// ── Shared styles ─────────────────────────────────────────────────────────────

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
  maxWidth: "360px",
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
  marginTop: "0.25rem",
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

const ghostBtnStyle: React.CSSProperties = {
  marginTop: "1rem",
  width: "100%",
  background: "transparent",
  border: "none",
  padding: 0,
  fontFamily: "var(--font-mono)",
  fontSize: "0.65rem",
  letterSpacing: "0.06em",
  color: "var(--text-dim)",
  cursor: "pointer",
  textAlign: "center",
  transition: "color 0.15s",
};
