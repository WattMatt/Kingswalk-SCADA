// web/src/ui/pages/ForgotPasswordPage.tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/core/api-client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.forgotPassword(email);
    } finally {
      setSubmitted(true);
      setLoading(false);
    }
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div aria-hidden style={amberBarStyle} />

        <div style={{ marginBottom: "1.75rem" }}>
          <h1 style={headingStyle}>Reset Password</h1>
          {!submitted && (
            <p style={subStyle}>Enter your email and we'll send a reset link.</p>
          )}
        </div>

        <div style={{ height: "1px", background: "var(--border-dim)", marginBottom: "1.5rem" }} />

        {submitted ? (
          <div>
            <div
              style={{
                background: "rgba(22,199,132,0.08)",
                border: "1px solid rgba(22,199,132,0.25)",
                padding: "0.75rem",
                fontFamily: "var(--font-mono)",
                fontSize: "0.72rem",
                color: "var(--green-live)",
                lineHeight: 1.6,
                marginBottom: "1.25rem",
              }}
            >
              If that email is registered, a reset link has been sent. Check your inbox.
            </div>
            <Link to="/login" style={linkStyle}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
            >
              ← Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
              <label htmlFor="email" style={labelStyle}>Email address</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@watsonmattheus.co.za"
                style={inputStyle}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{ ...submitStyle, background: loading ? "var(--amber-dim)" : "var(--amber)", cursor: loading ? "not-allowed" : "pointer" }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#ffbc1f"; }}
              onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "var(--amber)"; }}
            >
              {loading ? "Sending…" : "Send reset link"}
            </button>

            <Link to="/login" style={{ ...linkStyle, textAlign: "center", display: "block", marginTop: "0.25rem" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
            >
              ← Back to login
            </Link>
          </form>
        )}
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

const linkStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.68rem",
  letterSpacing: "0.06em",
  color: "var(--text-dim)",
  textDecoration: "none",
  transition: "color 0.15s",
};
