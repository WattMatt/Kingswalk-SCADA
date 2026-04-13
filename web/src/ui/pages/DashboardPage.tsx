// web/src/ui/pages/DashboardPage.tsx
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/core/api-client";
import { useAuthStore } from "@/core/auth-store";

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, clearUser } = useAuthStore();

  async function handleLogout() {
    await apiClient.logout();
    clearUser();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Kingswalk SCADA</h1>
            <p className="text-sm text-slate-400">Monitoring Dashboard — R1 PoC</p>
          </div>
          <div className="flex items-center gap-4">
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

        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Main Boards", value: "9", color: "blue" },
            { label: "Breakers", value: "104", color: "green" },
            { label: "Active Alarms", value: "—", color: "red" },
          ].map((card) => (
            <div
              key={card.label}
              className="rounded-xl border border-slate-800 bg-slate-900 p-6"
            >
              <p className="mb-1 text-sm text-slate-400">{card.label}</p>
              <p className="text-3xl font-bold text-white">{card.value}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <p className="text-sm text-slate-400">
            Phase 2 — Real-time breaker state grid will appear here.
          </p>
        </div>
      </div>
    </div>
  );
}
