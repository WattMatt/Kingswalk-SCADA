# api/app/routes/telemetry.py
"""GET /api/telemetry — time-bucketed PQ readings for one main board.

Query parameters
----------------
board_id       UUID      Required. UUID of the main board.
metric         str       One of: voltage_ln, voltage_ll, current, frequency,
                         power_factor, thd.  Default: voltage_ln.
start          datetime  ISO 8601 range start.  Default: 1 hour before *end*.
end            datetime  ISO 8601 range end.    Default: now (UTC).
bucket_minutes int       Bucket width in minutes [1–60].  Default: 1.

Response — TelemetryResponse
-----------------------------
{
  "board_id":   "...",
  "board_code": "MB-1.1",
  "metric":     "voltage_ln",
  "unit":       "V",
  "labels":     ["L1-N", "L2-N", "L3-N"],
  "series": [
    { "label": "L1-N", "register": 256,
      "data": [{"ts": "2026-04-17T00:00:00+00:00", "value": 231.4}, ...] },
    ...
  ]
}

The caller reshapes series into Recharts-compatible wide rows in the frontend.
All register addresses follow SPEC §3.2 (ABB M4M 30 assumed); see poller.py for
the authoritative constants.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rbac import get_current_user
from app.db.engine import get_db
from app.db.models import MainBoard, User
from app.repos import telemetry_repo

telemetry_router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# ── Metric → register map ─────────────────────────────────────────────────────
# Register addresses match edge/poller.py constants (SPEC §3.2 / ABB M4M 30).
# Scale factor converts raw integer → engineering unit.
# TODO: VERIFY_REGISTER — addresses assumed from ABB M4M 30 datasheet until
#       Profection confirms the actual register map.

_METRICS: dict[str, dict[str, Any]] = {
    "voltage_ln": {
        "registers": [0x0100, 0x0101, 0x0102],
        "scale": 0.1,
        "unit": "V",
        "labels": ["L1-N", "L2-N", "L3-N"],
    },
    "voltage_ll": {
        "registers": [0x0103, 0x0104, 0x0105],
        "scale": 0.1,
        "unit": "V",
        "labels": ["L1-L2", "L2-L3", "L3-L1"],
    },
    "current": {
        "registers": [0x0110, 0x0111, 0x0112],
        "scale": 0.01,
        "unit": "A",
        "labels": ["L1", "L2", "L3"],
    },
    "frequency": {
        "registers": [0x0114],
        "scale": 0.1,
        "unit": "Hz",
        "labels": ["Freq"],
    },
    "power_factor": {
        "registers": [0x0115, 0x0116, 0x0117],
        "scale": 0.001,
        "unit": "",
        "labels": ["L1", "L2", "L3"],
    },
    "thd": {
        "registers": [0x0200, 0x0201, 0x0202],
        "scale": 0.1,
        "unit": "%",
        "labels": ["L1", "L2", "L3"],
    },
}

VALID_METRICS = sorted(_METRICS)


# ── Response schema ────────────────────────────────────────────────────────────


class TelemetryPoint(BaseModel):
    ts: str     # ISO 8601, always UTC+00:00
    value: float


class TelemetrySeries(BaseModel):
    label: str
    register_addr: int
    data: list[TelemetryPoint]


class TelemetryResponse(BaseModel):
    board_id: str
    board_code: str
    metric: str
    unit: str
    labels: list[str]
    series: list[TelemetrySeries]


# ── Endpoint ───────────────────────────────────────────────────────────────────


@telemetry_router.get("", response_model=TelemetryResponse)
async def get_telemetry(
    board_id: uuid.UUID,
    metric: str = Query(default="voltage_ln", description=f"One of: {', '.join(VALID_METRICS)}"),
    start: datetime | None = Query(default=None, description="Range start (ISO 8601). Default: 1 h before end."),
    end: datetime | None = Query(default=None, description="Range end (ISO 8601). Default: now (UTC)."),
    bucket_minutes: int = Query(default=1, ge=1, le=60, description="Bucket width in minutes [1–60]."),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> TelemetryResponse:
    """Return time-bucketed PQ telemetry for one main board.

    All values are averaged within each bucket and scaled to engineering units.

    Raises:
        HTTPException 422: Unknown metric name.
        NotFoundError  404: Board not found or soft-deleted.
    """
    if metric not in _METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown metric '{metric}'. Valid metrics: {VALID_METRICS}",
        )

    # Resolve board UUID → board code (used as device_id in raw_sample)
    result = await db.execute(
        select(MainBoard.id, MainBoard.code).where(
            MainBoard.id == board_id,
            MainBoard.deleted_at.is_(None),
        )
    )
    board_row = result.one_or_none()
    if board_row is None:
        raise NotFoundError(f"Main board {board_id} not found")

    board_code: str = board_row.code

    # Time range defaults (UTC)
    now = datetime.now(timezone.utc)
    resolved_end = end if end is not None else now
    resolved_start = start if start is not None else resolved_end - timedelta(hours=1)

    m = _METRICS[metric]
    rows = await telemetry_repo.query_telemetry(
        db=db,
        device_id=board_code,
        register_addresses=m["registers"],
        start=resolved_start,
        end=resolved_end,
        bucket_minutes=bucket_minutes,
    )

    # Pivot long rows → per-register data lists
    series_data: dict[int, list[TelemetryPoint]] = {r: [] for r in m["registers"]}
    for row in rows:
        addr = cast(int, row["register_address"])
        raw_avg_obj = row["avg_value"]
        raw_avg = cast(float, raw_avg_obj) if raw_avg_obj is not None else 0.0
        scaled = round(raw_avg * cast(float, m["scale"]), 3)
        bucket = cast(datetime, row["bucket"])
        ts_str = bucket.isoformat()
        if addr in series_data:
            series_data[addr].append(TelemetryPoint(ts=ts_str, value=scaled))

    series = [
        TelemetrySeries(
            label=m["labels"][i],
            register_addr=m["registers"][i],
            data=series_data[m["registers"][i]],
        )
        for i in range(len(m["registers"]))
    ]

    return TelemetryResponse(
        board_id=str(board_id),
        board_code=board_code,
        metric=metric,
        unit=m["unit"],
        labels=m["labels"],
        series=series,
    )
