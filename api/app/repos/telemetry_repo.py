# api/app/repos/telemetry_repo.py
"""Repository for raw telemetry samples."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RawSample

log = structlog.get_logger()


@dataclass
class RawSampleRow:
    ts: datetime
    device_id: str
    register_address: int
    raw_value: int


async def insert_raw_batch(db: AsyncSession, samples: list[RawSampleRow]) -> int:
    """Bulk-insert raw samples. Silently ignores duplicate (device_id, register_address, ts).

    Returns the number of rows actually inserted (0 if all were duplicates).
    """
    if not samples:
        return 0
    stmt = insert(RawSample).values(
        [
            {
                "ts": s.ts,
                "device_id": s.device_id,
                "register_address": s.register_address,
                "raw_value": s.raw_value,
            }
            for s in samples
        ]
    )
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["device_id", "register_address", "ts"]
    )
    result = await db.execute(stmt)
    await db.commit()
    inserted = result.rowcount if result.rowcount is not None else 0
    log.info("raw_batch_inserted", count=inserted, total=len(samples))
    return inserted


async def latest_per_device(db: AsyncSession) -> list[dict[str, object]]:
    """Return the most recent sample for each device_id.

    Used by the WebSocket handler to build the initial state snapshot on reconnect.
    """
    result = await db.execute(
        text(
            "SELECT DISTINCT ON (device_id) "
            "device_id, register_address, raw_value, ts "
            "FROM telemetry.raw_sample "
            "ORDER BY device_id, ts DESC"
        )
    )
    rows = result.fetchall()
    return [
        {
            "device_id": row.device_id,
            "register_address": row.register_address,
            "raw_value": row.raw_value,
            "ts": row.ts.isoformat(),
        }
        for row in rows
    ]
