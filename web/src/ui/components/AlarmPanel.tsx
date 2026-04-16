// web/src/ui/components/AlarmPanel.tsx
import clsx from "clsx";
import type { ScadaEvent, UserRole } from "@/core/types";
import { useAlarmStore } from "@/core/alarm-store";

interface AlarmPanelProps {
  userRole: UserRole;
}

const SEVERITY_CLASSES: Record<ScadaEvent["severity"], string> = {
  info: "text-blue-400",
  warning: "text-amber-400",
  error: "text-orange-400",
  critical: "text-red-400",
};

const SEVERITY_ICONS: Record<ScadaEvent["severity"], string> = {
  info: "ℹ",
  warning: "⚠",
  error: "✖",
  critical: "🔴",
};

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-ZA", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Shows last 20 active (unacknowledged) alarms with acknowledge action for operator/admin. */
export function AlarmPanel({ userRole }: AlarmPanelProps) {
  const { alarms, ackAlarm } = useAlarmStore();
  const canAck = userRole === "operator" || userRole === "admin";

  const active = alarms.filter((a) => a.acknowledged_at === null).slice(0, 20);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-white">Active Alarms</h2>
        <span className="rounded-full bg-red-900 px-2 py-0.5 text-xs font-bold text-red-300">
          {active.length}
        </span>
      </div>

      {active.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">No active alarms</p>
      ) : (
        <ul className="divide-y divide-slate-800 overflow-y-auto max-h-96">
          {active.map((alarm) => (
            <li key={alarm.id} className="flex items-start gap-3 px-4 py-3">
              <span
                className={clsx("mt-0.5 shrink-0 text-base", SEVERITY_CLASSES[alarm.severity])}
                aria-label={alarm.severity}
              >
                {SEVERITY_ICONS[alarm.severity]}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-200 truncate">{alarm.kind}</p>
                <p className="text-xs text-slate-400 truncate">{alarm.message}</p>
                <p className="mt-0.5 text-xs text-slate-600">{formatTs(alarm.ts)}</p>
              </div>
              {canAck && (
                <button
                  onClick={() => void ackAlarm(alarm.id)}
                  className="shrink-0 rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
                >
                  Ack
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
