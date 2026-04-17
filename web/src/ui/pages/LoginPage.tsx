// web/src/ui/pages/LoginPage.tsx
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";

export function LoginPage() {
  const navigate = useNavigate();
  const { setUser, setMfaPending } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await apiClient.login(email, password);
      if (result.mfa_required) {
        setMfaPending(true);
        navigate("/mfa");
        return;
      }
      const user = await apiClient.me();
      setUser(user);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-void)",
        padding: "2rem",
      }}
    >
      {/* Ambient glow behind the card */}
      <div
        aria-hidden
        style={{
          position: "fixed",
          top: "30%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "600px",
          height: "300px",
          background: "radial-gradient(ellipse at center, rgba(246,166,0,0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          width: "100%",
          maxWidth: "380px",
          background: "var(--bg-panel)",
          border: "1px solid var(--border-mid)",
          padding: "2.5rem 2rem",
          position: "relative",
        }}
      >
        {/* Amber top bar */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: 0, left: 0, right: 0,
            height: "2px",
            background: "linear-gradient(90deg, var(--amber) 0%, transparent 80%)",
          }}
        />

        {/* Site identity */}
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.4rem" }}>
            {/* Power/monitoring icon */}
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <circle cx="9" cy="9" r="8" stroke="var(--amber)" strokeWidth="1.5"/>
              <path d="M9 4v5l3 2" stroke="var(--amber)" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: "1.2rem",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--amber-text)",
              }}
            >
              Kingswalk
            </span>
          </div>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
            }}
          >
            SCADA / Electrical Monitoring
          </p>
        </div>

        <div style={{ height: "1px", background: "var(--border-dim)", marginBottom: "1.75rem" }} />

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          <Field label="Email" htmlFor="email">
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@watsonmattheus.co.za"
              style={inputStyle}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.boxShadow = "0 0 0 1px var(--amber)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.boxShadow = "none"; }}
            />
          </Field>

          {error && (
            <div
              style={{
                background: "rgba(242,54,69,0.10)",
                border: "1px solid rgba(242,54,69,0.35)",
                padding: "0.6rem 0.75rem",
                fontFamily: "var(--font-mono)",
                fontSize: "0.72rem",
                color: "#f87171",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: "0.25rem",
              background: loading ? "var(--amber-dim)" : "var(--amber)",
              color: "#000",
              border: "none",
              padding: "0.65rem 1rem",
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "0.85rem",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "#ffbc1f"; }}
            onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = "var(--amber)"; }}
          >
            {loading ? "Authenticating…" : "Sign in"}
          </button>
        </form>

        <Link
          to="/forgot-password"
          style={{
            display: "block",
            marginTop: "1.25rem",
            textAlign: "center",
            fontFamily: "var(--font-mono)",
            fontSize: "0.68rem",
            letterSpacing: "0.06em",
            color: "var(--text-dim)",
            textDecoration: "none",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
        >
          Forgot password?
        </Link>

        {/* Version watermark */}
        <p
          style={{
            position: "absolute",
            bottom: "0.6rem",
            right: "0.8rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.6rem",
            color: "var(--border-hi)",
            letterSpacing: "0.1em",
          }}
        >
          R1 · v0.1.0
        </p>
      </div>
    </div>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <label
        htmlFor={htmlFor}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.68rem",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--text-mid)",
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

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
