// web/src/ui/components/AlarmPanel.tsx
import type { ScadaEvent, UserRole } from "@/core/types";
import { useAlarmStore } from "@/core/alarm-store";

interface AlarmPanelProps {
  userRole: UserRole;
}

const SEV_COLOR: Record<ScadaEvent["severity"], string> = {
  info:     "#60a5fa",
  warning:  "var(--amber-text)",
  error:    "var(--orange-warn)",
  critical: "var(--red-fault)",
};

const SEV_BG: Record<ScadaEvent["severity"], string> = {
  info:     "rgba(96,165,250,0.08)",
  warning:  "rgba(246,166,0,0.08)",
  error:    "rgba(255,148,0,0.10)",
  critical: "rgba(242,54,69,0.12)",
};

const SEV_LABEL: Record<ScadaEvent["severity"], string> = {
  info:     "INFO",
  warning:  "WARN",
  error:    "ERR",
  critical: "CRIT",
};

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-ZA", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
  } catch {
    return iso;
  }
}

/** Active alarm list with severity-coloured rows and per-row ACK. */
export function AlarmPanel({ userRole }: AlarmPanelProps) {
  const { alarms, ackAlarm } = useAlarmStore();
  const canAck = userRole === "operator" || userRole === "admin";
  const active = alarms.filter((a) => a.acknowledged_at === null).slice(0, 20);

  return (
    <div
      style={{
        background: "var(--bg-panel)",
        border: "1px solid var(--border-dim)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.65rem 0.85rem",
          borderBottom: "1px solid var(--border-dim)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.68rem",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            color: "var(--text-mid)",
          }}
        >
          Active Alarms
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.7rem",
            fontWeight: 700,
            color: active.length > 0 ? "var(--red-fault)" : "var(--text-dim)",
            background: active.length > 0 ? "rgba(242,54,69,0.12)" : "transparent",
            padding: "0.1rem 0.45rem",
            minWidth: "1.6rem",
            textAlign: "center",
          }}
        >
          {active.length}
        </span>
      </div>

      {/* Alarm list */}
      {active.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            padding: "2rem",
          }}
        >
          <span style={{ fontSize: "1.4rem" }}>◉</span>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              color: "var(--text-dim)",
              textAlign: "center",
            }}
          >
            SYSTEM NORMAL
          </p>
        </div>
      ) : (
        <ul
          style={{
            flex: 1,
            overflowY: "auto",
            margin: 0,
            padding: 0,
            listStyle: "none",
          }}
        >
          {active.map((alarm) => (
            <li
              key={alarm.id}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "0.65rem",
                padding: "0.6rem 0.85rem",
                borderBottom: "1px solid var(--border-dim)",
                background: SEV_BG[alarm.severity],
              }}
            >
              {/* Severity badge */}
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.58rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: SEV_COLOR[alarm.severity],
                  background: `${SEV_COLOR[alarm.severity]}1a`,
                  padding: "0.15rem 0.35rem",
                  flexShrink: 0,
                  marginTop: "0.1rem",
                  minWidth: "2.4rem",
                  textAlign: "center",
                }}
              >
                {SEV_LABEL[alarm.severity]}
              </span>

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "var(--text-hi)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    marginBottom: "0.1rem",
                  }}
                >
                  {alarm.kind.replace(/_/g, " ").toUpperCase()}
                </p>
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "0.75rem",
                    color: "var(--text-mid)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {alarm.message}
                </p>
                <p
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.6rem",
                    color: "var(--text-dim)",
                    marginTop: "0.2rem",
                  }}
                >
                  {formatTs(alarm.ts)}
                </p>
              </div>

              {/* ACK button */}
              {canAck && (
                <button
                  onClick={() => void ackAlarm(alarm.id)}
                  style={{
                    flexShrink: 0,
                    background: "transparent",
                    border: "1px solid var(--border-hi)",
                    color: "var(--text-mid)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.62rem",
                    letterSpacing: "0.08em",
                    padding: "0.2rem 0.45rem",
                    cursor: "pointer",
                    transition: "border-color 0.15s, color 0.15s",
                    marginTop: "0.1rem",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--amber)";
                    e.currentTarget.style.color = "var(--amber-text)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border-hi)";
                    e.currentTarget.style.color = "var(--text-mid)";
                  }}
                >
                  ACK
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
