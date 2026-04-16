# api/app/repos/asset_repo.py
"""Repository for asset entities (main boards, breakers, distribution boards)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Breaker, DistributionBoard, MainBoard


async def list_main_boards(db: AsyncSession) -> list[MainBoard]:
    """Return all active main boards ordered by code.

    Args:
        db: Async database session.

    Returns:
        List of MainBoard ORM instances, sorted by code ascending.
    """
    result = await db.execute(
        select(MainBoard)
        .where(MainBoard.deleted_at.is_(None))
        .order_by(MainBoard.code)
    )
    return list(result.scalars().all())


async def get_main_board(db: AsyncSession, board_id: uuid.UUID) -> MainBoard | None:
    """Return one main board by id, or None if not found or soft-deleted.

    Args:
        db: Async database session.
        board_id: UUID primary key of the main board.

    Returns:
        MainBoard ORM instance or None.
    """
    result = await db.execute(
        select(MainBoard).where(
            MainBoard.id == board_id,
            MainBoard.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_breakers(
    db: AsyncSession,
    main_board_id: uuid.UUID | None = None,
) -> list[Breaker]:
    """Return all active breakers, optionally filtered by main_board_id.

    Eager-loads the related DistributionBoard (feeds_db) via selectinload
    to avoid N+1 queries when serialising the response.

    Args:
        db: Async database session.
        main_board_id: If provided, restrict results to this main board.

    Returns:
        List of Breaker ORM instances ordered by label.
    """
    stmt = (
        select(Breaker)
        .where(Breaker.deleted_at.is_(None))
        .options(selectinload(Breaker.distribution_board))
        .order_by(Breaker.label)
    )
    if main_board_id is not None:
        stmt = stmt.where(Breaker.main_board_id == main_board_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_distribution_board(
    db: AsyncSession,
    board_id: uuid.UUID,
) -> DistributionBoard | None:
    """Return one distribution board by id, or None.

    Args:
        db: Async database session.
        board_id: UUID primary key of the distribution board.

    Returns:
        DistributionBoard ORM instance or None.
    """
    result = await db.execute(
        select(DistributionBoard).where(
            DistributionBoard.id == board_id,
            DistributionBoard.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()
