# api/app/services/threshold_service.py
"""Threshold evaluation: compare a raw sample value against all matching threshold rules.

Metric key format: "{device_id}:{register_address}" — e.g. "MB_1_1_breaker_0:0".
Threshold rows with `asset_class = 'raw'` and `metric = '{device_id}:{register_address}'`
match Phase 2b raw samples. Asset-specific thresholds (by UUID) are used in Phase 3.

Band-based evaluation (migration 0001a schema):
  Each threshold row carries optional low/high boundaries per severity band
  (warning_low/warning_high, error_low/error_high, critical_low/critical_high).
  A value is "in violation" of a band when it falls OUTSIDE [low, high]:
    - below low  → fires if low is set and value < low
    - above high → fires if high is set and value > high
  Highest severity that fires wins. One event per (metric, severity) per 5 minutes (dedup guard).

Dedup: only one event of the same `kind` is created per 5-minute window
to prevent storms during rapid oscillation. Full hysteresis is Phase 3.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Threshold
from app.repos import event_repo

log = structlog.get_logger()

# Severity bands in descending priority order.
# Each tuple: (severity_label, low_attr, high_attr)
_BANDS: list[tuple[str, str, str]] = [
    ("critical", "critical_low", "critical_high"),
    ("error",    "error_low",    "error_high"),
    ("warning",  "warning_low",  "warning_high"),
]


def _triggered_severity(threshold: Threshold, value: float) -> str | None:
    """Return the highest severity band fired by *value*, or None if within all bands."""
    for severity, low_attr, high_attr in _BANDS:
        low: float | None = getattr(threshold, low_attr, None)
        high: float | None = getattr(threshold, high_attr, None)
        if low is not None and value < low:
            return severity
        if high is not None and value > high:
            return severity
    return None


async def evaluate_sample(
    db: AsyncSession,
    device_id: str,
    register_address: int,
    raw_value: int,
) -> int:
    """Evaluate all matching threshold rules for one sample.

    Returns the number of new events created (0 or more).
    """
    metric_key = f"{device_id}:{register_address}"
    # Load enabled threshold rules that match this metric.
    # 'raw' asset_class is the Phase 2b catch-all; Phase 3 adds per-asset rules.
    result = await db.execute(
        select(Threshold).where(
            Threshold.enabled.is_(True),
            Threshold.metric == metric_key,
            Threshold.asset_class == "raw",
        )
    )
    thresholds = result.scalars().all()

    created = 0
    for threshold in thresholds:
        severity = _triggered_severity(threshold, float(raw_value))
        if severity is None:
            continue  # Value within all bands — no event

        # Condition met — check dedup window before inserting.
        kind = f"threshold:{metric_key}:{severity}"
        if await event_repo.recent_event_exists(db, kind=kind, within_minutes=5):
            log.debug("threshold_event_deduped", kind=kind)
            continue

        await event_repo.insert_event(
            db,
            severity=severity,
            kind=kind,
            message=(
                f"Threshold crossed: {device_id} register {register_address} "
                f"value={raw_value} severity={severity}"
            ),
            payload={
                "device_id": device_id,
                "register_address": register_address,
                "raw_value": raw_value,
                "threshold_id": str(threshold.id) if threshold.id else None,
            },
        )
        created += 1
        log.info("threshold_event_created", kind=kind, severity=severity)

    return created
