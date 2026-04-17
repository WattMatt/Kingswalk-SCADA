from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.engine import get_db
from app.services import comms_service, watchdog_service

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok", "version": settings.version}


@router.get("/api/health/telemetry", tags=["system"])
async def telemetry_health(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """Return edge gateway telemetry freshness — public endpoint for monitoring tools.

    Returns:
        JSON object with fields:

        - ``last_telemetry_at``: ISO-8601 timestamp of last received batch, or null.
        - ``silence_seconds``: seconds since last batch (null if never received).
        - ``status``: ``"ok"`` | ``"silent"`` | ``"unknown"``
        - ``device_freshness``: mapping of device_id to freshness status.
    """
    last = watchdog_service.get_last_telemetry_ts()
    now = datetime.now(UTC)

    if last is None:
        silence_seconds = None
        status = "unknown"
    else:
        silence_seconds = (now - last).total_seconds()
        status = "ok" if silence_seconds < watchdog_service.SILENCE_THRESHOLD_SEC else "silent"

    device_freshness = await comms_service.get_freshness_status(db)

    return {
        "last_telemetry_at": last.isoformat() if last else None,
        "silence_seconds": silence_seconds,
        "status": status,
        "device_freshness": device_freshness,
    }
