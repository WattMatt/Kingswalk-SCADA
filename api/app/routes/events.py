# api/app/routes/events.py
"""Event and alarm endpoints — list recent events, acknowledge alarms."""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.core.rbac import get_current_user
from app.db.engine import get_db
from app.db.models import AuditLog, Event, User
from app.services.notification_service import cancel_escalation

log = structlog.get_logger()

events_router = APIRouter(prefix="/api/events", tags=["events"])


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class EventOut(BaseModel):
    """Serialised alarm/event record."""

    id: int
    ts: datetime
    asset_id: uuid.UUID | None
    severity: str
    kind: str
    message: str
    payload: dict  # type: ignore[type-arg]
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@events_router.get("", response_model=list[EventOut])
async def list_events(
    severity: str | None = Query(
        default=None, description="Filter by severity: info|warning|error|critical"
    ),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[EventOut]:
    """Return the 100 most recent events, optionally filtered by severity.

    Requires: any authenticated role (admin, operator, viewer).

    Args:
        severity: Optional severity filter — one of info, warning, error, critical.
    """
    stmt = select(Event).order_by(Event.ts.desc()).limit(100)
    if severity is not None:
        stmt = stmt.where(Event.severity == severity)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [EventOut.model_validate(row) for row in rows]


@events_router.post("/{event_id}/ack", response_model=EventOut)
async def acknowledge_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventOut:
    """Acknowledge an alarm event.

    Sets acknowledged_by and acknowledged_at on the event record.
    Writes an entry to the audit log.

    Requires: admin or operator role. Viewers receive 403.

    Args:
        event_id: Integer primary key of the event to acknowledge.

    Raises:
        AuthError: If the calling user is a viewer.
        NotFoundError: If the event does not exist or is already acknowledged.
    """
    if current_user.role not in ("admin", "operator"):
        raise AppError("Insufficient permissions — operator or admin required", status_code=403)

    result = await db.execute(
        select(Event).where(
            Event.id == event_id,
            Event.acknowledged_at.is_(None),
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError(f"Event {event_id} not found or already acknowledged")

    now = datetime.now(UTC)
    event.acknowledged_by = current_user.id
    event.acknowledged_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="event.ack",
        asset_id=event.asset_id,
        payload={"event_id": event_id, "severity": event.severity, "kind": event.kind},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(event)

    # Cancel any pending tier-2 escalation for this alarm
    asyncio.create_task(
        cancel_escalation(event_id),
        name=f"cancel-escalation-{event_id}",
    )

    log.info(
        "event.acknowledged",
        event_id=event_id,
        user_id=str(current_user.id),
        severity=event.severity,
    )

    return EventOut.model_validate(event)
