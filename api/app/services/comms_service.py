# api/app/services/comms_service.py
"""COMMS LOSS detection — identify stale breaker data.

A breaker is STALE if its last raw_sample is older than 2× its poll interval.
Default poll interval for breaker state: 250ms → STALE if >500ms.
For MVP we use a practical threshold of 60s (one polling cycle miss).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_FRESH_THRESHOLD_SEC = 60
_STALE_THRESHOLD_SEC = 300


async def get_freshness_status(db: AsyncSession) -> dict[str, str]:
    """Return freshness classification for all known devices.

    Args:
        db: An active async database session.

    Returns:
        Mapping of ``{device_id: status}`` where status is one of:

        - ``"fresh"`` — last sample < 60 s ago
        - ``"stale"`` — last sample 60 s–300 s ago
        - ``"comms_loss"`` — last sample > 300 s ago or no data ever recorded
    """
    result = await db.execute(
        text(
            "SELECT device_id, MAX(ts) AS last_ts "
            "FROM telemetry.raw_sample "
            "GROUP BY device_id"
        )
    )
    rows = result.fetchall()

    now = datetime.now(UTC)
    freshness: dict[str, str] = {}

    for row in rows:
        last_ts: datetime = row.last_ts
        # Ensure tz-aware for comparison
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        age = (now - last_ts).total_seconds()

        if age < _FRESH_THRESHOLD_SEC:
            freshness[row.device_id] = "fresh"
        elif age < _STALE_THRESHOLD_SEC:
            freshness[row.device_id] = "stale"
        else:
            freshness[row.device_id] = "comms_loss"

    return freshness
