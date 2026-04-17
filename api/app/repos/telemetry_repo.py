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
    # asyncpg returns -1 for rowcount when ON CONFLICT DO NOTHING skips all rows;
    # guard against that to ensure we always return a non-negative count.
    inserted = max(0, result.rowcount) if result.rowcount is not None else 0  # type: ignore[attr-defined]
    log.info("raw_batch_inserted", count=inserted, total=len(samples))
    return inserted


async def query_telemetry(
    db: AsyncSession,
    device_id: str,
    register_addresses: list[int],
    start: datetime,
    end: datetime,
    bucket_minutes: int = 1,
) -> list[dict[str, object]]:
    """Return time-bucketed average register values within [start, end).

    Rows are grouped into equal-width buckets of *bucket_minutes* minutes using
    epoch arithmetic (works on any PostgreSQL version, no TimescaleDB required).

    Returns a list of dicts with keys:
      bucket            – datetime (UTC, timezone-aware)
      register_address  – int
      avg_value         – float (raw register integer, caller applies scale)
    """
    if not register_addresses:
        return []

    from sqlalchemy import bindparam  # noqa: PLC0415

    stmt = text(
        "SELECT "
        "  to_timestamp("
        "    floor(extract(epoch from ts) / :bucket_sec) * :bucket_sec"
        "  ) AS bucket, "
        "  register_address, "
        "  AVG(raw_value)::float AS avg_value "
        "FROM telemetry.raw_sample "
        "WHERE device_id = :device_id "
        "  AND register_address IN :registers "
        "  AND ts >= :start AND ts < :end "
        "GROUP BY 1, register_address "
        "ORDER BY 1, register_address"
    ).bindparams(bindparam("registers", expanding=True))

    result = await db.execute(
        stmt,
        {
            "device_id": device_id,
            "registers": register_addresses,
            "start": start,
            "end": end,
            "bucket_sec": bucket_minutes * 60,
        },
    )
    rows = result.fetchall()
    return [
        {
            "bucket": row.bucket,
            "register_address": row.register_address,
            "avg_value": row.avg_value,
        }
        for row in rows
    ]


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
