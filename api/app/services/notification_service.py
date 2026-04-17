# api/app/services/notification_service.py
"""Alarm notification and tiered escalation service.

Tier 1 — Notify (immediate):
  New warning/error/critical event → email all active operators + admins.

Tier 2 — Escalate (15 min):
  If the alarm is still unacknowledged after 15 minutes → SMS (stub for R1).

Escalation state is tracked in Redis:
  Key  : kw:escalation:{event_id}
  Value: {"event_id": int, "created_at": ISO-8601 UTC, "severity": str}
  TTL  : 30 min (auto-clears stale keys)

When an event is acknowledged (events.py → ack endpoint) cancel_escalation()
removes the Redis key, preventing the tier-2 fire.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_alarm_email
from app.core.redis_client import get_redis
from app.db.models import Event, User

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ESCALATION_KEY_PREFIX = "kw:escalation:"
_ESCALATION_TIMEOUT_SEC = 15 * 60          # 15 minutes
_ESCALATION_KEY_TTL_SEC = 30 * 60          # Redis TTL — garbage-collect stale keys
_ESCALATION_POLL_INTERVAL_SEC = 60         # check every minute
_EMAIL_SEVERITIES = frozenset({"warning", "error", "critical"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def notify_new_event(db: AsyncSession, event: Event) -> None:
    """Tier-1 notification: email recipients and schedule tier-2 escalation.

    Called immediately after a new event is persisted. Errors are isolated —
    a notification failure must never affect the alarm write path.

    Args:
        db: Async database session (used to fetch recipient list).
        event: The newly created Event row.
    """
    if event.severity not in _EMAIL_SEVERITIES:
        return

    try:
        recipients = await _get_notification_recipients(db)
        if recipients:
            asyncio.create_task(
                _send_notification_email(event, recipients),
                name=f"notify-email-{event.id}",
            )
        else:
            log.debug("notification.no_recipients", event_id=event.id)

        # Register for tier-2 escalation check
        await _register_escalation(event)

    except Exception:
        log.exception("notification.error", event_id=event.id)


async def cancel_escalation(event_id: int) -> None:
    """Cancel a pending tier-2 escalation when an alarm is acknowledged.

    Args:
        event_id: Primary key of the event being acknowledged.
    """
    try:
        redis = await get_redis()
        deleted = await redis.delete(f"{_ESCALATION_KEY_PREFIX}{event_id}")
        if deleted:
            log.debug("escalation.cancelled", event_id=event_id)
    except Exception:
        log.exception("escalation.cancel_error", event_id=event_id)


async def escalation_loop() -> None:
    """Background task: fire tier-2 escalation for overdue unacknowledged alarms.

    Polls Redis every 60 seconds. Any escalation key whose ``created_at``
    timestamp is older than 15 minutes triggers a tier-2 alert (SMS stub
    for R1) and the key is removed to prevent re-firing.

    This coroutine runs for the lifetime of the application and is
    started in the FastAPI lifespan handler.
    """
    log.info("escalation_loop.started", timeout_sec=_ESCALATION_TIMEOUT_SEC)
    while True:
        try:
            await asyncio.sleep(_ESCALATION_POLL_INTERVAL_SEC)
            await _process_escalations()
        except asyncio.CancelledError:
            log.info("escalation_loop.stopped")
            raise
        except Exception:
            log.exception("escalation_loop.error")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _process_escalations() -> None:
    """Scan escalation keys and fire tier-2 for any that have timed out."""
    redis = await get_redis()
    now = datetime.now(UTC)

    cursor = 0
    while True:
        cursor, keys = await redis.scan(
            cursor,
            match=f"{_ESCALATION_KEY_PREFIX}*",
            count=100,
        )
        for key in keys:
            raw = await redis.get(key)
            if raw is None:
                continue
            try:
                data = json.loads(raw)
                created_at = datetime.fromisoformat(data["created_at"])
                event_id = int(data["event_id"])
                severity = str(data.get("severity", "error"))
            except (json.JSONDecodeError, KeyError, ValueError):
                log.warning("escalation.bad_key", key=key)
                await redis.delete(key)
                continue

            elapsed = (now - created_at).total_seconds()
            if elapsed >= _ESCALATION_TIMEOUT_SEC:
                await _fire_tier2(event_id, severity, elapsed)
                await redis.delete(key)

        if cursor == 0:
            break


async def _fire_tier2(event_id: int, severity: str, elapsed_sec: float) -> None:
    """Tier-2 escalation handler.

    R1 implementation: structured log + SMS stub.
    Phase 3 will wire in Africa's Talking (or equivalent) SMS delivery.

    Args:
        event_id: Event primary key.
        severity: Alarm severity string.
        elapsed_sec: Seconds since the alarm was first raised.
    """
    log.warning(
        "escalation.tier2_triggered",
        event_id=event_id,
        severity=severity,
        elapsed_minutes=round(elapsed_sec / 60, 1),
    )
    # TODO Phase 3: SMS delivery
    # on_call = await get_oncall_number(...)
    # await sms_client.send(
    #     to=on_call,
    #     body=f"[ESCALATION] Kingswalk SCADA — event #{event_id} ({severity.upper()}) "
    #          f"unacknowledged for {elapsed_sec//60:.0f} min. Log in to acknowledge.",
    # )


async def _register_escalation(event: Event) -> None:
    """Write escalation tracking record to Redis."""
    redis = await get_redis()
    key = f"{_ESCALATION_KEY_PREFIX}{event.id}"
    value = json.dumps(
        {
            "event_id": event.id,
            "created_at": event.ts.isoformat(),
            "severity": event.severity,
        }
    )
    await redis.setex(key, _ESCALATION_KEY_TTL_SEC, value)
    log.debug("escalation.registered", event_id=event.id, severity=event.severity)


async def _send_notification_email(event: Event, recipients: list[str]) -> None:
    """Send alarm email — wraps send_alarm_email and swallows exceptions."""
    try:
        await send_alarm_email(
            event_id=event.id,
            severity=event.severity,
            kind=event.kind,
            message=event.message,
            ts=event.ts,
            recipients=recipients,
        )
        log.info(
            "notification.email_sent",
            event_id=event.id,
            severity=event.severity,
            recipient_count=len(recipients),
        )
    except Exception:
        log.exception("notification.email_error", event_id=event.id)


async def _get_notification_recipients(db: AsyncSession) -> list[str]:
    """Return email addresses of all active admin and operator users."""
    result = await db.execute(
        select(User.email).where(
            User.is_active.is_(True),
            User.role.in_(["admin", "operator"]),
        )
    )
    return list(result.scalars().all())
