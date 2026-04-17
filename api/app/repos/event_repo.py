# api/app/repos/event_repo.py
"""Repository for alarm events."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event

log = structlog.get_logger()


async def insert_event(
    db: AsyncSession,
    *,
    severity: str,
    kind: str,
    message: str,
    payload: dict[str, object] | None = None,
    notify: bool = True,
) -> Event:
    """Insert a new alarm event. Returns the persisted Event row.

    Args:
        db: Async database session.
        severity: One of info, warning, error, critical.
        kind: Machine-readable event type key.
        message: Human-readable description.
        payload: Optional structured metadata dict.
        notify: If True (default), fire tier-1 email notification and register
                tier-2 escalation for warning/error/critical events.
    """
    event = Event(
        severity=severity,
        kind=kind,
        message=message,
        payload=payload or {},
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    if notify:
        # Lazy imports avoid circular dependencies at module load time.
        # Import order: stdlib-shaped third-party first, then app modules.
        from app.db.engine import AsyncSessionLocal  # noqa: PLC0415
        from app.services.notification_service import notify_new_event  # noqa: PLC0415

        # Capture only the PK so the task is fully decoupled from the caller's
        # session.  The caller may close or reuse `db` before the task runs.
        event_id = event.id

        async def _notify() -> None:
            from sqlalchemy import select as sa_select  # noqa: PLC0415

            from app.db.models import Event as EventModel  # noqa: PLC0415

            async with AsyncSessionLocal() as notify_db:
                result = await notify_db.execute(
                    sa_select(EventModel).where(EventModel.id == event_id)
                )
                fresh_event = result.scalar_one_or_none()
                if fresh_event is None:
                    # Row gone before task ran (e.g. test teardown) — skip.
                    return
                await notify_new_event(notify_db, fresh_event)

        asyncio.create_task(_notify(), name=f"notify-{event.id}")

    return event


async def recent_event_exists(
    db: AsyncSession,
    kind: str,
    within_minutes: int = 5,
) -> bool:
    """Return True if an unacknowledged event of this kind exists within the last N minutes.

    Used as a dedup guard to prevent event storms during rapid oscillation.
    Full hysteresis (Phase 3) replaces this.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=within_minutes)
    result = await db.execute(
        select(Event.id).where(
            Event.kind == kind,
            Event.ts >= cutoff,
            Event.acknowledged_at.is_(None),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
