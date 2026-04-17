// web/src/ui/components/BreakerCard.tsx
import type { Breaker, BreakerLiveState } from "@/core/types";

interface BreakerCardProps {
  breaker: Breaker;
  state: BreakerLiveState;
}

const STATE_LABELS: Record<BreakerLiveState, string> = {
  closed:     "CLOSED",
  open:       "OPEN",
  tripped:    "TRIPPED",
  comms_loss: "NO COMMS",
  unknown:    "—",
};

const STATE_TEXT: Record<BreakerLiveState, string> = {
  closed:     "#16c784",
  open:       "#ff9400",
  tripped:    "#f23645",
  comms_loss: "#4e6070",
  unknown:    "#3d5166",
};

const CARD_BORDER: Record<BreakerLiveState, string> = {
  closed:     "1px solid #16332a",
  open:       "1px solid #33270a",
  tripped:    "1px solid #3d1018",
  comms_loss: "1px solid #1c2a38",
  unknown:    "1px solid #1c2a38",
};

const CARD_GLOW: Record<BreakerLiveState, string> = {
  closed:     "",
  open:       "",
  tripped:    "0 0 0 1px rgba(242,54,69,0.25)",
  comms_loss: "",
  unknown:    "",
};

/** Single breaker tile — industrial LED indicator style. */
export function BreakerCard({ breaker, state }: BreakerCardProps) {
  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: CARD_BORDER[state],
        boxShadow: CARD_GLOW[state] || undefined,
        padding: "0.6rem 0.7rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.3rem",
        transition: "box-shadow 0.3s",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Tripped: pulsing red top edge */}
      {state === "tripped" && (
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: 0, left: 0, right: 0,
            height: "2px",
            background: "var(--red-fault)",
            animation: "pulse-red 1.4s ease-in-out infinite",
          }}
        />
      )}

      {/* Header row: label + LED */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.4rem" }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            fontWeight: 700,
            color: "var(--text-hi)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {breaker.label}
        </span>
        <span className={`led led-${state}`} aria-label={STATE_LABELS[state]} />
      </div>

      {/* Tenant name */}
      {breaker.feeds_db?.name && (
        <p
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "0.78rem",
            fontWeight: 500,
            color: "var(--text-mid)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            lineHeight: 1.2,
          }}
        >
          {breaker.feeds_db.name}
        </p>
      )}

      {/* Bottom row: rating + state badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.3rem", marginTop: "0.15rem" }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.65rem",
            color: "var(--text-dim)",
          }}
        >
          {breaker.rating_amp}A {breaker.poles}
          {breaker.essential_supply && (
            <span
              style={{
                marginLeft: "0.35rem",
                background: "rgba(246,166,0,0.15)",
                color: "var(--amber-text)",
                padding: "0 0.3rem",
                fontSize: "0.6rem",
                letterSpacing: "0.08em",
              }}
            >
              ESS
            </span>
          )}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.58rem",
            fontWeight: 700,
            letterSpacing: "0.1em",
            color: STATE_TEXT[state],
          }}
        >
          {STATE_LABELS[state]}
        </span>
      </div>
    </div>
  );
}
