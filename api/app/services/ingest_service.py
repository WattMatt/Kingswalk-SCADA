# api/app/services/ingest_service.py
"""Ingest orchestration: store raw samples → evaluate thresholds → publish to Redis.

Called by POST /api/ingest/batch. Central pipeline step for Phase 2b.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.repos import telemetry_repo
from app.repos.telemetry_repo import RawSampleRow
from app.services import threshold_service, watchdog_service

log = structlog.get_logger()

_REDIS_CHANNEL = "telemetry:live"


class _SampleLike(Protocol):
    """Structural type for ingest samples — avoids circular import with routes/ingest.py."""

    device_id: str
    register_address: int
    raw_value: int
    sampled_at: datetime


async def handle_batch(db: AsyncSession, samples: Sequence[_SampleLike]) -> int:
    """Full ingest pipeline for one batch from the edge gateway.

    Steps:
    1. Convert to RawSampleRow and bulk-insert (idempotent ON CONFLICT DO NOTHING).
    2. Evaluate threshold rules for each sample — creates events.event rows on breach.
    3. Publish the accepted samples to Redis channel 'telemetry:live' for WS clients.

    Returns the number of newly inserted rows.
    """
    watchdog_service.record_telemetry_received()

    rows = [
        RawSampleRow(
            ts=s.sampled_at,
            device_id=s.device_id,
            register_address=s.register_address,
            raw_value=s.raw_value,
        )
        for s in samples
    ]

    inserted = await telemetry_repo.insert_raw_batch(db, rows)

    # Evaluate thresholds for every sample in the batch, not just newly inserted ones.
    # Duplicate samples won't re-insert (ON CONFLICT DO NOTHING) but we still evaluate
    # them on replay to catch threshold breaches that may have been missed while offline.
    # threshold_service has its own 5-minute dedup guard, so re-evaluation of a
    # recently seen sample will not produce a duplicate alarm event.
    for s in samples:
        try:
            await threshold_service.evaluate_sample(
                db,
                device_id=s.device_id,
                register_address=s.register_address,
                raw_value=s.raw_value,
            )
        except Exception:
            # Threshold evaluation failure must not abort the ingest response.
            log.exception("threshold_evaluation_failed", device_id=s.device_id)

    # Publish live update to Redis — WebSocket broadcaster subscribes to this channel.
    if samples:
        try:
            redis = await get_redis()
            payload = json.dumps({
                "samples": [
                    {
                        "device_id": s.device_id,
                        "register_address": s.register_address,
                        "raw_value": s.raw_value,
                        "ts": s.sampled_at.isoformat(),
                    }
                    for s in samples
                ]
            })
            subscribers = await redis.publish(_REDIS_CHANNEL, payload)
            if subscribers == 0:
                log.warning("redis_no_subscribers", channel=_REDIS_CHANNEL)
        except Exception:
            # Redis publish failure must not abort the ingest response.
            log.exception("redis_publish_failed")

    return inserted
