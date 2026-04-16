# api/app/services/watchdog_service.py
"""Edge gateway watchdog — raises CRITICAL alarm if no telemetry for >30s.

Runs as a background asyncio task, started in the app lifespan.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.db.engine import AsyncSessionLocal
from app.repos import event_repo

SILENCE_THRESHOLD_SEC = 30
_DEDUP_MINUTES = 5
_WATCHDOG_KIND = "edge_watchdog"

_last_telemetry_ts: datetime | None = None

log = structlog.get_logger()


def record_telemetry_received() -> None:
    """Record that a telemetry batch was received right now.

    Call this every time the ingest endpoint accepts a batch.
    Thread-safe for asyncio single-threaded event loops.
    """
    global _last_telemetry_ts
    _last_telemetry_ts = datetime.now(UTC)


def get_last_telemetry_ts() -> datetime | None:
    """Return the timestamp of the most recently received telemetry batch, or None."""
    return _last_telemetry_ts


async def watchdog_loop() -> None:
    """Background task: every 10s check if telemetry has been silent >30s.

    Raises a CRITICAL event via event_repo when silence is detected.
    Uses a 5-minute dedup guard to avoid flooding the events table.

    Designed to run for the lifetime of the process — cancelled on shutdown.
    """
    log.info("watchdog_started", silence_threshold_sec=SILENCE_THRESHOLD_SEC)

    while True:
        await asyncio.sleep(10)
        now = datetime.now(UTC)
        last = _last_telemetry_ts

        silence = (
            last is None
            or (now - last) > timedelta(seconds=SILENCE_THRESHOLD_SEC)
        )

        if not silence:
            continue

        silence_secs = None if last is None else (now - last).total_seconds()
        log.warning(
            "watchdog_silence_detected",
            last_telemetry_at=last.isoformat() if last else None,
            silence_seconds=silence_secs,
        )

        try:
            async with AsyncSessionLocal() as db:
                already_alarmed = await event_repo.recent_event_exists(
                    db, kind=_WATCHDOG_KIND, within_minutes=_DEDUP_MINUTES
                )
                if already_alarmed:
                    log.debug("watchdog_deduped", kind=_WATCHDOG_KIND)
                    continue

                await event_repo.insert_event(
                    db,
                    severity="critical",
                    kind=_WATCHDOG_KIND,
                    message="Edge gateway unresponsive — no telemetry for >30s",
                    payload={
                        "last_telemetry_at": last.isoformat() if last else None,
                        "silence_seconds": silence_secs,
                    },
                )
                log.error(
                    "watchdog_alarm_raised",
                    last_telemetry_at=last.isoformat() if last else None,
                )
        except Exception:
            log.exception("watchdog_db_error")
