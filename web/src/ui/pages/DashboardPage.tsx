// web/src/ui/pages/DashboardPage.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAlarmStore } from "@/core/alarm-store";
import { useAssetStore } from "@/core/asset-store";
import { useAuthStore } from "@/core/auth-store";
import type { BreakerLiveState, StateSyncMessage } from "@/core/types";
import { useBreakerStore } from "@/core/breaker-store";
import { useScadaWebSocket } from "@/core/useScadaWebSocket";
import { wsClient } from "@/core/ws-client";
import { AlarmPanel } from "../components/AlarmPanel";
import { BreakerCard } from "../components/BreakerCard";
import { BreakerGrid } from "@/ui/components/BreakerGrid";

const WS_BASE =
  (import.meta.env["VITE_WS_URL"] as string | undefined) ?? "ws://localhost:8000";

type StateMap = Record<string, BreakerLiveState>;

const ROLE_COLOR: Record<string, string> = {
  admin:    "var(--amber-text)",
  operator: "var(--green-live)",
  viewer:   "var(--text-mid)",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, clearUser } = useAuthStore();
  const { boards, breakers, fetchBoards, fetchBreakers } = useAssetStore();
  const { alarms, setAlarms, isReconnecting, setConnected, setReconnecting } =
    useAlarmStore();
  const getAlarmCount = useBreakerStore((s) => s.getAlarmCount);
  const { connectionStatus } = useScadaWebSocket();

  const [selectedBoardId, setSelectedBoardId] = useState<string | null>(null);
  const [stateMap] = useState<StateMap>({});
  const [wsConnected, setWsConnected] = useState(false);

  const alarmCount = getAlarmCount();

  // ── Data fetch ──────────────────────────────────────────────────────────────

  useEffect(() => {
    void fetchBoards();
    void apiClient.events.list().then(setAlarms).catch(() => undefined);
  }, [fetchBoards, setAlarms]);

  useEffect(() => {
    if (boards.length > 0 && selectedBoardId === null) {
      setSelectedBoardId(boards[0]?.id ?? null);
    }
  }, [boards, selectedBoardId]);

  useEffect(() => {
    if (selectedBoardId) void fetchBreakers(selectedBoardId);
  }, [selectedBoardId, fetchBreakers]);

  // ── WebSocket ───────────────────────────────────────────────────────────────

  useEffect(() => {
    wsClient.connect(WS_BASE);
    setConnected(true);
    setWsConnected(true);

    const unsub = wsClient.onMessage((msg) => {
      if (msg.type === "state_sync") {
        const sync = msg as StateSyncMessage;
        setAlarms(sync.active_alarms);
        setConnected(true);
        setReconnecting(false);
        setWsConnected(true);
      } else if (msg.type === "telemetry_update") {
        console.debug("[ws] telemetry_update", msg.samples.length, "samples");
      }
    });

    return () => {
      unsub();
      wsClient.disconnect();
      setConnected(false);
      setWsConnected(false);
    };
  }, [setAlarms, setConnected, setReconnecting]);

  // ── Helpers ─────────────────────────────────────────────────────────────────

  async function handleLogout() {
    try { await apiClient.logout(); } catch { /* always clear */ }
    clearUser();
    navigate("/login");
  }

  const activeAlarmCount = alarms.filter((a) => a.acknowledged_at === null).length;
  const boardBreakers    = breakers.filter((b) => b.main_board_id === selectedBoardId);
  const selectedBoard    = boards.find((b) => b.id === selectedBoardId);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg-void)" }}>

      {/* ── Reconnecting banner ─────────────────────────────────────────────── */}
      {isReconnecting && (
        <div
          style={{
            background: "rgba(246,166,0,0.12)",
            borderBottom: "1px solid rgba(246,166,0,0.30)",
            padding: "0.4rem 1.2rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.68rem",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--amber-text)",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            flexShrink: 0,
          }}
        >
          <span style={{ animation: "pulse-red 1.4s ease-in-out infinite", display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "var(--amber)", flexShrink: 0 }} />
          Reconnecting to live data…
        </div>
      )}

      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <header
        style={{
          height: "52px",
          background: "var(--bg-deep)",
          borderBottom: "1px solid var(--border-dim)",
          display: "flex",
          alignItems: "center",
          gap: "1.25rem",
          padding: "0 1.25rem",
          flexShrink: 0,
          position: "relative",
        }}
      >
        {/* Amber left accent */}
        <div aria-hidden style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "3px", background: "linear-gradient(180deg, var(--amber) 0%, transparent 100%)" }} />

        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.55rem", paddingLeft: "0.35rem" }}>
          <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden>
            <circle cx="9" cy="9" r="8" stroke="var(--amber)" strokeWidth="1.5"/>
            <path d="M9 4v5l3 2" stroke="var(--amber)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "1.05rem",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--amber-text)",
            }}
          >
            Kingswalk
          </span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.6rem",
              letterSpacing: "0.12em",
              color: "var(--text-dim)",
              textTransform: "uppercase",
              paddingLeft: "0.25rem",
            }}
          >
            SCADA
          </span>
        </div>

        {/* Divider */}
        <div style={{ width: "1px", height: "20px", background: "var(--border-mid)" }} />

        {/* Live indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <span
            className={wsConnected ? "led led-closed" : "led led-comms_loss"}
            aria-hidden
          />
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.62rem",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: wsConnected ? "var(--green-live)" : "var(--grey-dead)",
            }}
          >
            {wsConnected ? "Live" : "Offline"}
          </span>
        </div>

        {/* Nav links */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.1rem" }}>
          <button
            style={{
              background: "transparent",
              border: "none",
              borderBottom: "2px solid var(--amber)",
              padding: "0.2rem 0",
              cursor: "default",
              fontFamily: "var(--font-mono)",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--amber-text)",
            }}
          >
            Dashboard
          </button>
          <div style={{ width: "1px", height: "12px", background: "var(--border-dim)", margin: "0 0.5rem" }} />
          <button
            onClick={() => navigate("/trends")}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: "2px solid transparent",
              padding: "0.2rem 0",
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-mid)",
              transition: "color 0.15s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-hi)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-mid)"; }}
          >
            PQ Trends
          </button>
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Stat chips */}
        <StatChip label="Boards"  value={boards.length > 0 ? String(boards.length) : "—"} />
        <StatChip label="Alarms"  value={String(activeAlarmCount)} highlight={activeAlarmCount > 0} />

        {/* Divider */}
        <div style={{ width: "1px", height: "20px", background: "var(--border-mid)" }} />

        {/* User info */}
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "var(--text-mid)" }}>
          {user?.full_name ?? user?.email}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.58rem",
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: ROLE_COLOR[user?.role ?? "viewer"] ?? "var(--text-mid)",
            background: "rgba(255,255,255,0.04)",
            padding: "0.15rem 0.4rem",
            border: "1px solid var(--border-mid)",
          }}
        >
          {user?.role ?? "viewer"}
        </span>

        <button
          onClick={() => void handleLogout()}
          style={{
            background: "transparent",
            border: "1px solid var(--border-mid)",
            color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.65rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            padding: "0.25rem 0.65rem",
            cursor: "pointer",
            transition: "border-color 0.15s, color 0.15s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--border-hi)"; e.currentTarget.style.color = "var(--text-mid)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-mid)"; e.currentTarget.style.color = "var(--text-dim)"; }}
        >
          Sign out
        </button>
      </header>

      {/* ── Board selector tab strip ─────────────────────────────────────────── */}
      <div
        style={{
          background: "var(--bg-panel)",
          borderBottom: "1px solid var(--border-dim)",
          display: "flex",
          alignItems: "stretch",
          overflowX: "auto",
          flexShrink: 0,
          gap: 0,
        }}
      >
        {boards.length === 0 ? (
          <div style={{ padding: "0.65rem 1.25rem", fontFamily: "var(--font-mono)", fontSize: "0.65rem", color: "var(--text-dim)", letterSpacing: "0.1em" }}>
            Loading boards…
          </div>
        ) : (
          boards.map((board) => {
            const active = board.id === selectedBoardId;
            return (
              <button
                key={board.id}
                onClick={() => setSelectedBoardId(board.id)}
                style={{
                  background: active ? "var(--bg-surface)" : "transparent",
                  border: "none",
                  borderBottom: active ? "2px solid var(--amber)" : "2px solid transparent",
                  borderRight: "1px solid var(--border-dim)",
                  padding: "0.55rem 1.1rem",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  gap: "0.1rem",
                  minWidth: "7.5rem",
                  transition: "background 0.15s, border-color 0.15s",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    color: active ? "var(--amber-text)" : "var(--text-mid)",
                  }}
                >
                  {board.code}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.57rem",
                    letterSpacing: "0.06em",
                    color: "var(--text-dim)",
                  }}
                >
                  VLAN {board.vlan_id ?? "—"}
                </span>
              </button>
            );
          })
        )}
      </div>

      {/* ── Main content area ────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>

        {/* Breaker grid column */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>

          {/* Board detail header */}
          {selectedBoard && (
            <div
              style={{
                padding: "0.65rem 1.1rem",
                borderBottom: "1px solid var(--border-dim)",
                display: "flex",
                alignItems: "center",
                gap: "1rem",
                flexShrink: 0,
              }}
            >
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "0.9rem", color: "var(--text-hi)", letterSpacing: "0.05em" }}>
                {selectedBoard.location ?? selectedBoard.code}
              </span>
              {selectedBoard.drawing && (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.62rem", color: "var(--text-dim)", letterSpacing: "0.06em" }}>
                  {selectedBoard.drawing}
                </span>
              )}
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.62rem", color: "var(--text-dim)" }}>
                {boardBreakers.length} breaker{boardBreakers.length !== 1 ? "s" : ""}
              </span>
            </div>
          )}

          {/* Grid */}
          <div style={{ flex: 1, overflowY: "auto", padding: "1rem" }}>
            {boardBreakers.length === 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  gap: "0.75rem",
                  minHeight: "200px",
                }}
              >
                <span style={{ fontSize: "1.6rem", opacity: 0.3 }}>◫</span>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.65rem", letterSpacing: "0.12em", color: "var(--text-dim)", textTransform: "uppercase" }}>
                  {selectedBoardId ? "Loading breakers…" : "Select a main board"}
                </p>
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
                  gap: "0.6rem",
                }}
              >
                {boardBreakers.map((breaker) => (
                  <BreakerCard
                    key={breaker.id}
                    breaker={breaker}
                    state={stateMap[breaker.id] ?? "unknown"}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Alarm panel column */}
        <div
          style={{
            width: "280px",
            flexShrink: 0,
            borderLeft: "1px solid var(--border-dim)",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <AlarmPanel userRole={user?.role ?? "viewer"} />
        </div>
      </div>
    </div>
  );
}

/** Compact stat chip for the top bar */
function StatChip({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.05rem" }}>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.78rem",
          fontWeight: 700,
          color: highlight ? "var(--red-fault)" : "var(--text-hi)",
          lineHeight: 1,
        }}
      >
        {value}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.52rem",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "var(--text-dim)",
          lineHeight: 1,
        }}
      >
        {label}
      </span>
    </div>
  );
}
