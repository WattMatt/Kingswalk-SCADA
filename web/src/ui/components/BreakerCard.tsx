// web/src/ui/components/BreakerCard.tsx
import clsx from "clsx";
import type { Breaker, BreakerLiveState } from "@/core/types";

interface BreakerCardProps {
  breaker: Breaker;
  state: BreakerLiveState;
}

const STATE_LABELS: Record<BreakerLiveState, string> = {
  closed: "CLOSED",
  open: "OPEN",
  tripped: "TRIPPED",
  comms_loss: "COMMS LOSS",
  unknown: "UNKNOWN",
};

const STATE_CLASSES: Record<BreakerLiveState, string> = {
  closed: "bg-green-900 text-green-300 border-green-700",
  open: "bg-amber-900 text-amber-300 border-amber-700",
  tripped: "bg-red-900 text-red-300 border-red-700",
  comms_loss: "bg-slate-700 text-slate-300 border-slate-600",
  unknown: "bg-slate-800 text-slate-400 border-slate-700",
};

const CARD_BORDER: Record<BreakerLiveState, string> = {
  closed: "border-green-800",
  open: "border-amber-800",
  tripped: "border-red-800",
  comms_loss: "border-slate-600",
  unknown: "border-slate-700",
};

/** Displays a single breaker's identity and live state. */
export function BreakerCard({ breaker, state }: BreakerCardProps) {
  const polesLabel = breaker.poles === "TP" ? "TP" : breaker.poles;

  return (
    <div
      className={clsx(
        "rounded-lg border bg-slate-900 p-3 flex flex-col gap-1",
        CARD_BORDER[state],
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-sm font-semibold text-white truncate">
          {breaker.label}
        </span>
        <span
          className={clsx(
            "shrink-0 rounded border px-1.5 py-0.5 text-xs font-bold uppercase tracking-wide",
            STATE_CLASSES[state],
          )}
        >
          {STATE_LABELS[state]}
        </span>
      </div>

      {breaker.feeds_db?.name && (
        <p className="text-xs text-slate-300 truncate">{breaker.feeds_db.name}</p>
      )}

      <p className="text-xs text-slate-500">
        {breaker.rating_amp}A {polesLabel}
        {breaker.essential_supply && (
          <span className="ml-1 rounded bg-yellow-900 px-1 text-yellow-400">ESS</span>
        )}
      </p>
    </div>
  );
}
