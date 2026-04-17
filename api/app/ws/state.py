# api/app/ws/state.py
"""State snapshot builder — full board + breaker + alarm payload for new WS clients."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.repos import asset_repo


def _board_dict(board: object) -> dict[str, object]:
    """Serialise a MainBoard ORM object to a plain dict.

    Args:
        board: MainBoard ORM instance.

    Returns:
        Dictionary representation safe for JSON serialisation.
    """
    from app.db.models import MainBoard  # noqa: PLC0415

    assert isinstance(board, MainBoard)
    return {
        "id": str(board.id),
        "code": board.code,
        "drawing": board.drawing,
        "vlan_id": board.vlan_id,
        "subnet": str(board.subnet),
        "location": board.location,
    }


def _breaker_dict(breaker: object) -> dict[str, object]:
    """Serialise a Breaker ORM object to a plain dict.

    Args:
        breaker: Breaker ORM instance (with distribution_board eager-loaded).

    Returns:
        Dictionary representation safe for JSON serialisation.
    """
    from app.db.models import Breaker  # noqa: PLC0415

    assert isinstance(breaker, Breaker)
    feeds_db: dict[str, object] | None = None
    if breaker.distribution_board is not None:
        db_obj = breaker.distribution_board
        area: float | None = (
            float(db_obj.area_m2) if isinstance(db_obj.area_m2, Decimal) else db_obj.area_m2
        )
        feeds_db = {
            "id": str(db_obj.id),
            "code": db_obj.code,
            "name": db_obj.name,
            "area_m2": area,
        }
    return {
        "id": str(breaker.id),
        "main_board_id": str(breaker.main_board_id),
        "label": breaker.label,
        "breaker_code": breaker.breaker_code,
        "abb_family": breaker.abb_family,
        "rating_amp": breaker.rating_amp,
        "poles": str(breaker.poles),
        "mp_code": breaker.mp_code,
        "essential_supply": breaker.essential_supply,
        "device_ip": str(breaker.device_ip) if breaker.device_ip else None,
        "feeds_db": feeds_db,
    }


def _event_dict(event: Event) -> dict[str, object]:
    """Serialise an Event ORM object to a plain dict.

    Args:
        event: Event ORM instance.

    Returns:
        Dictionary representation safe for JSON serialisation.
    """
    return {
        "id": event.id,
        "ts": event.ts.isoformat(),
        "asset_id": str(event.asset_id) if event.asset_id else None,
        "severity": event.severity,
        "kind": event.kind,
        "message": event.message,
        "payload": event.payload,
        "acknowledged_by": str(event.acknowledged_by) if event.acknowledged_by else None,
        "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
    }


async def get_state_snapshot(db: AsyncSession) -> dict[str, object]:
    """Return a full state payload: all main boards, their breakers, and active alarms.

    Queries all active main boards and breakers, groups breakers under their
    respective board, and fetches the 50 most recent unacknowledged events.

    Args:
        db: Active async database session.

    Returns:
        Dict with keys ``type``, ``boards``, ``active_alarms``, and ``ts``.

        Example::

            {
                "type": "state_sync",
                "boards": [
                    {
                        "id": "...",
                        "code": "MB1",
                        ...
                        "breakers": [...]
                    },
                    ...
                ],
                "active_alarms": [...],
                "ts": "2026-04-16T10:00:00+00:00"
            }
    """
    boards = await asset_repo.list_main_boards(db)
    all_breakers = await asset_repo.list_breakers(db)

    # Group breakers by main_board_id for O(n) assembly
    breakers_by_board: dict[uuid.UUID, list[dict[str, object]]] = {}
    for breaker in all_breakers:
        from app.db.models import Breaker  # noqa: PLC0415

        assert isinstance(breaker, Breaker)
        bid = breaker.main_board_id
        if bid not in breakers_by_board:
            breakers_by_board[bid] = []
        breakers_by_board[bid].append(_breaker_dict(breaker))

    boards_payload: list[dict[str, object]] = []
    for board in boards:
        from app.db.models import MainBoard  # noqa: PLC0415

        assert isinstance(board, MainBoard)
        board_d = _board_dict(board)
        board_d["breakers"] = breakers_by_board.get(board.id, [])
        boards_payload.append(board_d)

    # Active alarms: unacknowledged events, newest first, capped at 50
    result = await db.execute(
        select(Event)
        .where(Event.acknowledged_at.is_(None))
        .order_by(Event.ts.desc())
        .limit(50)
    )
    active_alarms = [_event_dict(row) for row in result.scalars().all()]

    return {
        "type": "state_sync",
        "boards": boards_payload,
        "active_alarms": active_alarms,
        "ts": datetime.now(UTC).isoformat(),
    }
