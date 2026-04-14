# api/app/services/ingest_service.py
"""Ingest orchestration: store → evaluate → publish."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import telemetry_repo
from app.repos.telemetry_repo import RawSampleRow


async def handle_batch(db: AsyncSession, samples: list[Any]) -> int:
    """Store raw samples. Returns count of newly inserted rows.

    Threshold evaluation and Redis publish are wired in Task 4.
    """
    rows = [
        RawSampleRow(
            ts=s.sampled_at,
            device_id=s.device_id,
            register_address=s.register_address,
            raw_value=s.raw_value,
        )
        for s in samples
    ]
    return await telemetry_repo.insert_raw_batch(db, rows)
