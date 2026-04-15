// web/src/ui/pages/DashboardPage.tsx
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";
import { useBreakerStore } from "@/core/breaker-store";
import { useScadaWebSocket } from "@/core/useScadaWebSocket";
import { BreakerGrid } from "@/ui/components/BreakerGrid";

type StatusBannerProps = {
  status: string;
};

function StatusBanner({ status }: StatusBannerProps) {
  if (status === "connected") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-green-800 bg-green-950 px-4 py-2 text-sm text-green-300">
        <span className="h-2 w-2 rounded-full bg-green-400" />
        LIVE
      </div>
    );
  }

  if (status === "connecting") {
    return (
      <div className="flex animate-pulse items-center gap-2 rounded-lg border border-amber-800 bg-amber-950 px-4 py-2 text-sm text-amber-300">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        RECONNECTING…
      </div>
    );
  }

  // disconnected | error
  return (
    <div className="flex items-center gap-2 rounded-lg border border-red-800 bg-red-950 px-4 py-2 text-sm text-red-300">
      <span className="h-2 w-2 rounded-full bg-red-400" />
      DISCONNECTED
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, clearUser } = useAuthStore();
  const getAlarmCount = useBreakerStore((s) => s.getAlarmCount);
  const { connectionStatus } = useScadaWebSocket();

  const alarmCount = getAlarmCount();

  async function handleLogout() {
    try {
      await apiClient.logout();
    } catch {
      // Always clear local auth even if the server call fails
    }
    clearUser();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Kingswalk SCADA</h1>
            <p className="text-sm text-slate-400">Monitoring Dashboard — R1 PoC</p>
          </div>
          <div className="flex items-center gap-4">
            <StatusBanner status={connectionStatus} />
            <span className="text-sm text-slate-300">
              {user?.full_name}{" "}
              <span className="rounded bg-blue-900 px-2 py-0.5 text-xs font-medium uppercase text-blue-300">
                {user?.role}
              </span>
            </span>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Stat cards */}
        <div className="mb-8 grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="mb-1 text-sm text-slate-400">Main Boards</p>
            <p className="text-3xl font-bold text-white">9</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="mb-1 text-sm text-slate-400">Total Breakers</p>
            <p className="text-3xl font-bold text-white">104</p>
          </div>
          <div className="rounded-xl border border-red-900 bg-slate-900 p-6">
            <p className="mb-1 text-sm text-slate-400">Active Alarms</p>
            <p
              className={`text-3xl font-bold ${
                alarmCount > 0 ? "text-red-400" : "text-white"
              }`}
            >
              {alarmCount}
            </p>
          </div>
        </div>

        {/* Breaker grid */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <BreakerGrid />
        </div>
      </div>
    </div>
  );
}
