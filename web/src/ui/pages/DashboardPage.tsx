// web/src/ui/pages/DashboardPage.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { apiClient } from "@/core/api-client";
import { useAlarmStore } from "@/core/alarm-store";
import { useAssetStore } from "@/core/asset-store";
import { useAuthStore } from "@/core/auth-store";
import type { BreakerLiveState, StateSyncMessage } from "@/core/types";
import { wsClient } from "@/core/ws-client";
import { AlarmPanel } from "../components/AlarmPanel";
import { BreakerCard } from "../components/BreakerCard";

const WS_BASE =
  (import.meta.env["VITE_WS_URL"] as string | undefined) ?? "ws://localhost:8000";

/** Map breakerId → live state; "unknown" until WS decodes register data (Phase 3). */
type StateMap = Record<string, BreakerLiveState>;

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, clearUser } = useAuthStore();
  const { boards, breakers, fetchBoards, fetchBreakers } = useAssetStore();
  const { alarms, setAlarms, isReconnecting, setConnected, setReconnecting } =
    useAlarmStore();

  const [selectedBoardId, setSelectedBoardId] = useState<string | null>(null);
  // stateMap will be populated in Phase 3 from telemetry_update decoding
  const [stateMap] = useState<StateMap>({});

  // ── Data fetch ─────────────────────────────────────────────────────────────

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
    if (selectedBoardId) {
      void fetchBreakers(selectedBoardId);
    }
  }, [selectedBoardId, fetchBreakers]);

  // ── WebSocket ──────────────────────────────────────────────────────────────

  useEffect(() => {
    wsClient.connect(WS_BASE);
    setConnected(true);

    const unsub = wsClient.onMessage((msg) => {
      if (msg.type === "state_sync") {
        const sync = msg as StateSyncMessage;
        setAlarms(sync.active_alarms);
        setConnected(true);
        setReconnecting(false);
      } else if (msg.type === "telemetry_update") {
        // Phase 3: decode breaker state from register values
        console.debug("[ws] telemetry_update", msg.samples.length, "samples");
      }
    });

    return () => {
      unsub();
      wsClient.disconnect();
      setConnected(false);
    };
  }, [setAlarms, setConnected, setReconnecting]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  async function handleLogout() {
    try {
      await apiClient.logout();
    } catch {
      // Always clear local auth even if server call fails
    }
    clearUser();
    navigate("/login");
  }

  const activeAlarmCount = alarms.filter((a) => a.acknowledged_at === null).length;
  const boardBreakers = breakers.filter((b) => b.main_board_id === selectedBoardId);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {isReconnecting && (
        <div className="bg-amber-900 px-4 py-2 text-center text-sm text-amber-200">
          Reconnecting to live data…
        </div>
      )}

      <div className="mx-auto max-w-7xl px-4 py-6">
        {/* Header */}
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Kingswalk SCADA</h1>
            <p className="text-sm text-slate-400">Live Monitoring Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-300">
              {user?.full_name}{" "}
              <span className="ml-1 rounded bg-blue-900 px-2 py-0.5 text-xs font-medium uppercase text-blue-300">
                {user?.role}
              </span>
            </span>
            <button
              onClick={() => void handleLogout()}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 hover:text-white"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Summary cards */}
        <div className="mb-6 grid grid-cols-3 gap-4">
          {[
            { label: "Main Boards", value: boards.length > 0 ? String(boards.length) : "9" },
            { label: "Breakers", value: "104" },
            { label: "Active Alarms", value: String(activeAlarmCount) },
          ].map((card) => (
            <div key={card.label} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="mb-1 text-sm text-slate-400">{card.label}</p>
              <p className="text-3xl font-bold">{card.value}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-6">
          {/* Board tabs + breaker grid */}
          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap gap-2">
              {boards.map((board) => (
                <button
                  key={board.id}
                  onClick={() => setSelectedBoardId(board.id)}
                  className={clsx(
                    "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                    board.id === selectedBoardId
                      ? "border-blue-600 bg-blue-900 text-blue-200"
                      : "border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-500 hover:text-white",
                  )}
                >
                  {board.code}
                </button>
              ))}
            </div>

            {boardBreakers.length === 0 ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-500">
                {selectedBoardId ? "Loading breakers…" : "Select a main board"}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
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

          {/* Alarm panel */}
          <div className="w-80 shrink-0">
            <AlarmPanel userRole={user?.role ?? "viewer"} />
          </div>
        </div>
      </div>
    </div>
  );
}
