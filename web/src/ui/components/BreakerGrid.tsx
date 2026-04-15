// web/src/ui/components/BreakerGrid.tsx
import type { BreakerState } from "@/core/types";
import { useBreakerStore } from "@/core/breaker-store";
import { BreakerCell } from "./BreakerCell";

export function BreakerGrid() {
  const getBreakersByBoard = useBreakerStore((s) => s.getBreakersByBoard);
  const byBoard = getBreakersByBoard();
  const boards = Object.keys(byBoard).sort(); // MB01 → MB09

  if (boards.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-500">
        Waiting for snapshot…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {boards.map((board, idx) => {
        // noUncheckedIndexedAccess: board is a key we just extracted via Object.keys,
        // so the value is guaranteed to exist — fallback to [] is just a type guard.
        const breakers: BreakerState[] = byBoard[board] ?? [];
        const trippedCount = breakers.filter((b) => b.state === "tripped").length;
        const commsLossCount = breakers.filter((b) => b.comms_loss).length;

        return (
          <div key={board}>
            {/* Board section header */}
            <div className="mb-3 flex items-center gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-200">
                {board}
              </h2>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                {breakers.length} breakers
              </span>
              {trippedCount > 0 && (
                <span className="animate-pulse rounded bg-red-900 px-2 py-0.5 text-xs font-semibold text-red-400">
                  {trippedCount} tripped
                </span>
              )}
              {commsLossCount > 0 && (
                <span className="rounded bg-amber-900 px-2 py-0.5 text-xs font-semibold text-amber-400">
                  {commsLossCount} comms loss
                </span>
              )}
            </div>

            {/* Breaker grid */}
            <div className="grid grid-cols-6 gap-2 lg:grid-cols-8 xl:grid-cols-10">
              {breakers.map((breaker) => (
                <BreakerCell key={breaker.asset_id} breaker={breaker} />
              ))}
            </div>

            {/* Divider between boards (not after last) */}
            {idx < boards.length - 1 && (
              <div className="mt-6 border-t border-slate-800" />
            )}
          </div>
        );
      })}
    </div>
  );
}
