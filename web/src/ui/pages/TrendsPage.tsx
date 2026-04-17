// web/src/ui/pages/TrendsPage.tsx
/**
 * PQ Trends — time-series power quality charts for a selected main board.
 *
 * Features
 * --------
 * - Board selector: dropdown populated from assetStore
 * - Metric tabs: voltage_ln, voltage_ll, current, frequency, power_factor, thd
 * - Time range presets: 1H · 6H · 24H · 7D  (with auto bucket sizing)
 * - Recharts ResponsiveLineChart with industrial dark styling
 * - Loading / empty / error states
 * - Navigation back to Dashboard via topbar
 *
 * No Tailwind — inline styles only, CSS custom properties from index.css.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiClient } from "@/core/api-client";
import { useAssetStore } from "@/core/asset-store";
import { useAuthStore } from "@/core/auth-store";
import type { MetricName, TelemetryResponse, TelemetrySeries } from "@/core/types";
import { METRIC_LABELS } from "@/core/types";

// ── Constants ─────────────────────────────────────────────────────────────────

const METRICS: MetricName[] = [
  "voltage_ln",
  "voltage_ll",
  "current",
  "frequency",
  "power_factor",
  "thd",
];

type RangeKey = "1H" | "6H" | "24H" | "7D";

const RANGE_CONFIG: Record<RangeKey, { label: string; hours: number; bucketMinutes: number }> = {
  "1H":  { label: "1H",  hours: 1,    bucketMinutes: 1  },
  "6H":  { label: "6H",  hours: 6,    bucketMinutes: 5  },
  "24H": { label: "24H", hours: 24,   bucketMinutes: 15 },
  "7D":  { label: "7D",  hours: 168,  bucketMinutes: 60 },
};

/** One colour per series line — amber → cyan → green → purple (SCADA industrial) */
const LINE_COLORS = [
  "var(--amber)",        // L1 / L1-N / L1-L2
  "#38bdf8",             // L2 / L2-N / L2-L3  (sky blue)
  "var(--green-live)",   // L3 / L3-N / L3-L1
  "#c084fc",             // Neutral / extra (purple)
];

/** Reference bands for quick sanity checks — shown as dashed lines. */
const REFERENCE_LINES: Partial<Record<MetricName, { value: number; label: string }[]>> = {
  voltage_ln:   [{ value: 210, label: "Min" }, { value: 253, label: "Max" }],
  frequency:    [{ value: 49.5, label: "Min" }, { value: 50.5, label: "Max" }],
  thd:          [{ value: 8, label: "8% limit" }],
};

const ROLE_COLOR: Record<string, string> = {
  admin:    "var(--amber-text)",
  operator: "var(--green-live)",
  viewer:   "var(--text-mid)",
};

// ── Recharts data reshaping ───────────────────────────────────────────────────

/**
 * Convert the API's series-per-register format into Recharts "wide" format:
 * [{ ts: "…", "L1-N": 231.4, "L2-N": 230.8, … }, …]
 */
function toChartData(series: TelemetrySeries[]): Record<string, string | number>[] {
  if (series.length === 0) return [];

  // Build a map: ts → { [label]: value }
  const byTs = new Map<string, Record<string, number>>();
  for (const s of series) {
    for (const pt of s.data) {
      if (!byTs.has(pt.ts)) byTs.set(pt.ts, {});
      const row = byTs.get(pt.ts)!;
      row[s.label] = pt.value;
    }
  }

  return Array.from(byTs.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([ts, vals]) => ({ ts, ...vals }));
}

/** Format a UTC ISO timestamp for the X-axis tick label. */
function formatTick(ts: string): string {
  try {
    const d = new Date(ts);
    const h = d.getUTCHours().toString().padStart(2, "0");
    const m = d.getUTCMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  } catch {
    return ts;
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TopBar({
  onLogout,
  userName,
  userRole,
}: {
  onLogout: () => void;
  userName: string;
  userRole: string;
}) {
  const navigate = useNavigate();
  return (
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
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: "3px",
          background: "linear-gradient(180deg, var(--amber) 0%, transparent 100%)",
        }}
      />

      {/* Logo */}
      <div
        style={{ display: "flex", alignItems: "center", gap: "0.55rem", paddingLeft: "0.35rem" }}
      >
        <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden>
          <circle cx="9" cy="9" r="8" stroke="var(--amber)" strokeWidth="1.5" />
          <path d="M9 4v5l3 2" stroke="var(--amber)" strokeWidth="1.5" strokeLinecap="round" />
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

      {/* Nav links */}
      <NavLink label="Dashboard" onClick={() => navigate("/dashboard")} active={false} />
      <NavLink label="PQ Trends" onClick={() => undefined} active />

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* User badge */}
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.7rem",
          color: "var(--text-mid)",
        }}
      >
        {userName}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.58rem",
          fontWeight: 700,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: ROLE_COLOR[userRole] ?? "var(--text-mid)",
          background: "rgba(255,255,255,0.04)",
          padding: "0.15rem 0.4rem",
          border: "1px solid var(--border-mid)",
        }}
      >
        {userRole}
      </span>

      <button
        onClick={onLogout}
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
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--border-hi)";
          e.currentTarget.style.color = "var(--text-mid)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--border-mid)";
          e.currentTarget.style.color = "var(--text-dim)";
        }}
      >
        Sign out
      </button>
    </header>
  );
}

function NavLink({
  label,
  onClick,
  active,
}: {
  label: string;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "transparent",
        border: "none",
        borderBottom: active ? "2px solid var(--amber)" : "2px solid transparent",
        padding: "0.2rem 0",
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: "0.68rem",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: active ? "var(--amber-text)" : "var(--text-mid)",
        transition: "color 0.15s, border-color 0.15s",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.color = "var(--text-hi)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.color = "var(--text-mid)";
      }}
    >
      {label}
    </button>
  );
}

/** Dark-styled Recharts tooltip */
function ChartTooltip({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
  unit: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--bg-panel)",
        border: "1px solid var(--border-mid)",
        padding: "0.5rem 0.75rem",
        fontFamily: "var(--font-mono)",
        fontSize: "0.68rem",
        minWidth: "120px",
      }}
    >
      <p style={{ color: "var(--text-dim)", marginBottom: "0.35rem", letterSpacing: "0.08em" }}>
        {label ? formatTick(label) : ""}
      </p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color, margin: "0.15rem 0" }}>
          {entry.name}:{" "}
          <span style={{ color: "var(--text-hi)", fontWeight: 700 }}>
            {typeof entry.value === "number" ? entry.value.toFixed(2) : entry.value}
            {unit ? ` ${unit}` : ""}
          </span>
        </p>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function TrendsPage() {
  const navigate = useNavigate();
  const { user, clearUser } = useAuthStore();
  const { boards, fetchBoards } = useAssetStore();

  const [selectedBoardId, setSelectedBoardId] = useState<string>("");
  const [metric, setMetric] = useState<MetricName>("voltage_ln");
  const [range, setRange] = useState<RangeKey>("1H");
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-refresh interval ref
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Seed board list ─────────────────────────────────────────────────────────

  useEffect(() => {
    void fetchBoards();
  }, [fetchBoards]);

  useEffect(() => {
    if (boards.length > 0 && selectedBoardId === "") {
      setSelectedBoardId(boards[0]?.id ?? "");
    }
  }, [boards, selectedBoardId]);

  // ── Fetch helper ────────────────────────────────────────────────────────────

  const fetchTelemetry = useCallback(async () => {
    if (!selectedBoardId) return;
    setLoading(true);
    setError(null);
    try {
      const cfg = RANGE_CONFIG[range];
      const end = new Date();
      const start = new Date(end.getTime() - cfg.hours * 3600 * 1000);
      const data = await apiClient.telemetry.query({
        boardId: selectedBoardId,
        metric,
        start: start.toISOString(),
        end: end.toISOString(),
        bucketMinutes: cfg.bucketMinutes,
      });
      setTelemetry(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load telemetry");
      setTelemetry(null);
    } finally {
      setLoading(false);
    }
  }, [selectedBoardId, metric, range]);

  // Fetch on control changes
  useEffect(() => {
    void fetchTelemetry();
  }, [fetchTelemetry]);

  // Auto-refresh every 30 s for the 1H range
  useEffect(() => {
    if (refreshRef.current) clearInterval(refreshRef.current);
    if (range === "1H") {
      refreshRef.current = setInterval(() => {
        void fetchTelemetry();
      }, 30_000);
    }
    return () => {
      if (refreshRef.current) clearInterval(refreshRef.current);
    };
  }, [range, fetchTelemetry]);

  // ── Derived ─────────────────────────────────────────────────────────────────

  const chartData = useMemo(
    () => (telemetry ? toChartData(telemetry.series) : []),
    [telemetry],
  );

  const hasData = chartData.length > 0;
  const seriesLabels = telemetry?.series.map((s) => s.label) ?? [];
  const unit = telemetry?.unit ?? "";
  const refLines = REFERENCE_LINES[metric] ?? [];

  // ── Auth ────────────────────────────────────────────────────────────────────

  async function handleLogout() {
    try {
      await apiClient.logout();
    } catch {
      /* always clear */
    }
    clearUser();
    navigate("/login");
  }

  // ── Layout ──────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg-void)",
      }}
    >
      {/* Top bar */}
      <TopBar
        onLogout={() => void handleLogout()}
        userName={user?.full_name ?? user?.email ?? ""}
        userRole={user?.role ?? "viewer"}
      />

      {/* Controls strip */}
      <div
        style={{
          background: "var(--bg-panel)",
          borderBottom: "1px solid var(--border-dim)",
          display: "flex",
          alignItems: "center",
          gap: "0",
          padding: "0 1.1rem",
          flexShrink: 0,
          flexWrap: "wrap",
        }}
      >
        {/* Board selector */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.55rem 1.1rem 0.55rem 0",
            borderRight: "1px solid var(--border-dim)",
            marginRight: "1.1rem",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.6rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
            }}
          >
            Board
          </span>
          <select
            value={selectedBoardId}
            onChange={(e) => setSelectedBoardId(e.target.value)}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-mid)",
              color: "var(--text-hi)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.72rem",
              padding: "0.2rem 0.5rem",
              cursor: "pointer",
              outline: "none",
              letterSpacing: "0.04em",
            }}
          >
            {boards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.code}
              </option>
            ))}
          </select>
        </div>

        {/* Metric tabs */}
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            gap: 0,
            borderRight: "1px solid var(--border-dim)",
            marginRight: "1.1rem",
          }}
        >
          {METRICS.map((m) => {
            const active = m === metric;
            return (
              <button
                key={m}
                onClick={() => setMetric(m)}
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: active ? "2px solid var(--amber)" : "2px solid transparent",
                  padding: "0.55rem 0.85rem",
                  cursor: "pointer",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.62rem",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: active ? "var(--amber-text)" : "var(--text-dim)",
                  transition: "color 0.15s",
                  whiteSpace: "nowrap",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.color = "var(--text-mid)";
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.color = "var(--text-dim)";
                }}
              >
                {METRIC_LABELS[m]}
              </button>
            );
          })}
        </div>

        {/* Time range buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.6rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
              marginRight: "0.35rem",
            }}
          >
            Range
          </span>
          {(Object.keys(RANGE_CONFIG) as RangeKey[]).map((r) => {
            const active = r === range;
            return (
              <button
                key={r}
                onClick={() => setRange(r)}
                style={{
                  background: active ? "rgba(246,166,0,0.12)" : "transparent",
                  border: active ? "1px solid rgba(246,166,0,0.5)" : "1px solid var(--border-mid)",
                  color: active ? "var(--amber-text)" : "var(--text-dim)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.65rem",
                  letterSpacing: "0.1em",
                  padding: "0.2rem 0.55rem",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {RANGE_CONFIG[r].label}
              </button>
            );
          })}
        </div>

        {/* Loading indicator */}
        {loading && (
          <div
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.6rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--amber)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--amber)",
                animation: "pulse-red 1.2s ease-in-out infinite",
              }}
            />
            Loading…
          </div>
        )}
      </div>

      {/* Chart area */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>

        {/* Page title row */}
        <div
          style={{
            padding: "0.65rem 1.4rem",
            borderBottom: "1px solid var(--border-dim)",
            display: "flex",
            alignItems: "baseline",
            gap: "0.75rem",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: "0.9rem",
              color: "var(--text-hi)",
              letterSpacing: "0.05em",
            }}
          >
            {METRIC_LABELS[metric]}
          </span>
          {telemetry && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.62rem",
                color: "var(--text-dim)",
                letterSpacing: "0.06em",
              }}
            >
              {telemetry.board_code} · {RANGE_CONFIG[range].label} · {RANGE_CONFIG[range].bucketMinutes}m buckets
            </span>
          )}
          {unit && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.62rem",
                color: "var(--amber)",
                letterSpacing: "0.08em",
                marginLeft: "auto",
              }}
            >
              {unit}
            </span>
          )}
        </div>

        {/* Chart or empty state */}
        <div style={{ flex: 1, minHeight: 0, padding: "1rem 0.5rem 0.5rem 0" }}>
          {error ? (
            <EmptyState icon="⚠" message={error} tint="var(--red-fault)" />
          ) : !hasData && !loading ? (
            <EmptyState
              icon="◫"
              message={selectedBoardId ? "No data for selected range" : "Select a main board"}
            />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border-dim)"
                  vertical={false}
                />
                <XAxis
                  dataKey="ts"
                  tickFormatter={formatTick}
                  tick={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    fill: "var(--text-dim)",
                  }}
                  axisLine={{ stroke: "var(--border-mid)" }}
                  tickLine={false}
                  minTickGap={40}
                />
                <YAxis
                  tick={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    fill: "var(--text-dim)",
                  }}
                  axisLine={false}
                  tickLine={false}
                  width={50}
                />
                <Tooltip
                  content={<ChartTooltip unit={unit} />}
                  cursor={{ stroke: "var(--border-mid)", strokeDasharray: "3 3" }}
                />
                <Legend
                  wrapperStyle={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.62rem",
                    color: "var(--text-mid)",
                    paddingTop: "0.5rem",
                  }}
                />

                {/* Reference lines (spec limits) */}
                {refLines.map((rl) => (
                  <ReferenceLine
                    key={rl.label}
                    y={rl.value}
                    stroke="rgba(242,54,69,0.45)"
                    strokeDasharray="4 3"
                    label={{
                      value: `${rl.label} (${rl.value})`,
                      fill: "var(--red-fault)",
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                    }}
                  />
                ))}

                {/* Data lines */}
                {seriesLabels.map((label, idx) => (
                  <Line
                    key={label}
                    type="monotone"
                    dataKey={label}
                    stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3, fill: LINE_COLORS[idx % LINE_COLORS.length] }}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ icon, message, tint = "var(--text-dim)" }: {
  icon: string;
  message: string;
  tint?: string;
}) {
  return (
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
      <span style={{ fontSize: "1.8rem", opacity: 0.3, color: tint }}>{icon}</span>
      <p
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.65rem",
          letterSpacing: "0.12em",
          color: tint,
          textTransform: "uppercase",
          opacity: 0.7,
        }}
      >
        {message}
      </p>
    </div>
  );
}
