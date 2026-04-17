// web/src/ui/pages/ResetPasswordPage.tsx
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "@/core/api-client";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setError(null);
    setLoading(true);
    try {
      await apiClient.resetPassword(token, password);
      navigate("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div style={pageStyle}>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--red-fault)" }}>
          Invalid reset link.
        </p>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div aria-hidden style={amberBarStyle} />

        <div style={{ marginBottom: "1.75rem" }}>
          <h1 style={headingStyle}>Set New Password</h1>
          <p style={subStyle}>Choose a strong password for your account.</p>
        </div>

        <div style={{ height: "1px", background: "var(--border-dim)", marginBottom: "1.5rem" }} />

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label htmlFor="password" style={labelStyle}>New password</label>
            <input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label htmlFor="confirm" style={labelStyle}>Confirm password</label>
            <input
              id="confirm"
              type="password"
              required
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              style={inputStyle}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </div>

          {error && (
            <div style={errorStyle}>{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ ...submitStyle, background: loading ? "var(--amber-dim)" : "var(--amber)", cursor: loading ? "not-allowed" : "pointer" }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#ffbc1f"; }}
            onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "var(--amber)"; }}
          >
            {loading ? "Updating…" : "Update password"}
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
