# edge/buffer.py
"""LocalBuffer — SQLite-backed pending_samples table for VPN-outage resilience."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass
class RawSample:
    device_id: str
    register_address: int
    raw_value: int
    sampled_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "register_address": self.register_address,
            "raw_value": self.raw_value,
            "sampled_at": self.sampled_at.isoformat(),
        }


class LocalBuffer:
    """SQLite-backed telemetry buffer.

    Survives VPN outages — samples accumulate here until CloudSync drains them.
    Use `:memory:` for tests.
    """

    def __init__(self, db_path: str = "edge_buffer.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialise(self) -> None:
        # For :memory: databases, we need to keep the connection open
        if self._db_path == ":memory:":
            self._db = await aiosqlite.connect(self._db_path)

        db = self._db if self._db else None
        if db is None:
            db = await aiosqlite.connect(self._db_path)
            close_after = True
        else:
            close_after = False

        try:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_samples (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT    NOT NULL,
                    register_address INTEGER NOT NULL,
                    raw_value        INTEGER NOT NULL,
                    sampled_at       TEXT    NOT NULL,
                    synced           INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_unsynced "
                "ON pending_samples (synced) WHERE synced = 0"
            )
            await db.commit()
        finally:
            if close_after:
                await db.close()

    async def add(self, sample: RawSample) -> None:
        db = self._db if self._db else None
        if db is None:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO pending_samples "
                    "(device_id, register_address, raw_value, sampled_at) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        sample.device_id,
                        sample.register_address,
                        sample.raw_value,
                        sample.sampled_at.isoformat(),
                    ),
                )
                await db.commit()
        else:
            await db.execute(
                "INSERT INTO pending_samples "
                "(device_id, register_address, raw_value, sampled_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    sample.device_id,
                    sample.register_address,
                    sample.raw_value,
                    sample.sampled_at.isoformat(),
                ),
            )
            await db.commit()

    async def take_batch(self, max_rows: int = 500) -> list[tuple[int, RawSample]]:
        """Return up to `max_rows` unsynced samples as (row_id, RawSample) pairs."""
        db = self._db if self._db else None
        if db is None:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    "SELECT id, device_id, register_address, raw_value, sampled_at "
                    "FROM pending_samples WHERE synced = 0 "
                    "ORDER BY id ASC LIMIT ?",
                    (max_rows,),
                ) as cursor:
                    rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT id, device_id, register_address, raw_value, sampled_at "
                "FROM pending_samples WHERE synced = 0 "
                "ORDER BY id ASC LIMIT ?",
                (max_rows,),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            (
                row[0],
                RawSample(
                    device_id=row[1],
                    register_address=row[2],
                    raw_value=row[3],
                    sampled_at=datetime.fromisoformat(row[4]),
                ),
            )
            for row in rows
        ]

    async def mark_synced(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        db = self._db if self._db else None
        if db is None:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    f"UPDATE pending_samples SET synced = 1 WHERE id IN ({placeholders})",
                    ids,
                )
                await db.commit()
        else:
            await db.execute(
                f"UPDATE pending_samples SET synced = 1 WHERE id IN ({placeholders})",
                ids,
            )
            await db.commit()

    async def pending_count(self) -> int:
        db = self._db if self._db else None
        if db is None:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM pending_samples WHERE synced = 0"
                ) as cursor:
                    row = await cursor.fetchone()
                    return int(row[0]) if row else 0
        else:
            async with db.execute(
                "SELECT COUNT(*) FROM pending_samples WHERE synced = 0"
            ) as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else 0

    async def close(self) -> None:
        """Close the persistent `:memory:` connection, if any."""
        if self._db is not None:
            await self._db.close()
            self._db = None
