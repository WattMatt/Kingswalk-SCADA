// web/src/ui/components/BreakerCell.tsx
import type { BreakerState, BreakerStateValue } from "@/core/types";

interface BreakerCellProps {
  breaker: BreakerState;
}

type StyleSet = {
  card: string;
  dot: string;
  label: string;
  badge: string;
};

// Keyed by the exhaustive BreakerStateValue union — noUncheckedIndexedAccess safe
const STATE_STYLES: Record<BreakerStateValue, StyleSet> = {
  closed: {
    card: "border-green-800 bg-green-950",
    dot: "bg-green-400",
    label: "text-green-400",
    badge: "text-green-400",
  },
  open: {
    card: "border-slate-700 bg-slate-900",
    dot: "bg-slate-400",
    label: "text-slate-400",
    badge: "text-slate-400",
  },
  tripped: {
    card: "border-red-800 bg-red-950 animate-pulse",
    dot: "bg-red-400",
    label: "text-red-400",
    badge: "text-red-400",
  },
  unknown: {
    card: "border-amber-800 bg-amber-950",
    dot: "bg-amber-400",
    label: "text-amber-400",
    badge: "text-amber-400",
  },
};

function getStyles(state: BreakerStateValue, commsLoss: boolean): StyleSet {
  if (commsLoss) return STATE_STYLES.unknown;
  return STATE_STYLES[state];
}

/** Strip the board prefix from the label, e.g. "MB01-B03" → "B03" */
function shortLabel(label: string): string {
  const parts = label.split("-");
  return parts.length > 1 ? parts.slice(1).join("-") : label;
}

function formatLastSeen(ts: string | null): string {
  if (!ts) return "Never";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

export function BreakerCell({ breaker }: BreakerCellProps) {
  const styles = getStyles(breaker.state, breaker.comms_loss);

  const stateLabel = breaker.comms_loss ? "comms loss" : breaker.state;

  const title = [
    `Label: ${breaker.label}`,
    `State: ${stateLabel}`,
    `Board: ${breaker.main_board_ref}`,
    `Last seen: ${formatLastSeen(breaker.last_seen)}`,
  ].join("\n");

  return (
    <div
      title={title}
      className={[
        "flex min-h-[60px] min-w-[80px] cursor-default flex-col items-center",
        "justify-between rounded-lg border px-2 py-1.5 transition-colors",
        styles.card,
      ].join(" ")}
    >
      {/* Short label at top */}
      <span className={`text-[11px] font-semibold leading-tight ${styles.label}`}>
        {shortLabel(breaker.label)}
      </span>

      {/* State indicator dot */}
      <span
        className={`mt-1 h-2 w-2 rounded-full ${styles.dot}`}
        aria-hidden="true"
      />

      {/* State badge at bottom */}
      <span className={`mt-1 text-[9px] uppercase tracking-wide ${styles.badge}`}>
        {stateLabel}
      </span>
    </div>
  );
}
