# api/app/routes/assets.py
"""Read-only asset endpoints — main boards and breakers.

All endpoints require an authenticated user (any role: admin, operator, viewer).
No write operations are exposed — this system is monitoring-only.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rbac import get_current_user
from app.db.engine import get_db
from app.db.models import User
from app.repos import asset_repo

assets_router = APIRouter(prefix="/api/assets", tags=["assets"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DistributionBoardOut(BaseModel):
    """Serialised distribution board for embedding inside BreakerOut."""

    id: uuid.UUID
    code: str
    name: str | None
    area_m2: float | None

    model_config = ConfigDict(from_attributes=True)


class BreakerOut(BaseModel):
    """Serialised circuit breaker."""

    id: uuid.UUID
    main_board_id: uuid.UUID
    label: str
    breaker_code: str
    abb_family: str
    rating_amp: int
    poles: str
    mp_code: str | None
    essential_supply: bool
    device_ip: str | None
    feeds_db: DistributionBoardOut | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_breaker(cls, breaker: object) -> "BreakerOut":
        """Build BreakerOut from an ORM Breaker, coercing INET/CIDR to str."""
        from app.db.models import Breaker  # noqa: PLC0415

        assert isinstance(breaker, Breaker)
        feeds_db = None
        if breaker.distribution_board is not None:
            db_obj = breaker.distribution_board
            area: float | None = (
                float(db_obj.area_m2) if isinstance(db_obj.area_m2, Decimal) else db_obj.area_m2
            )
            feeds_db = DistributionBoardOut(
                id=db_obj.id,
                code=db_obj.code,
                name=db_obj.name,
                area_m2=area,
            )
        return cls(
            id=breaker.id,
            main_board_id=breaker.main_board_id,
            label=breaker.label,
            breaker_code=breaker.breaker_code,
            abb_family=breaker.abb_family,
            rating_amp=breaker.rating_amp,
            poles=str(breaker.poles),
            mp_code=breaker.mp_code,
            essential_supply=breaker.essential_supply,
            device_ip=str(breaker.device_ip) if breaker.device_ip else None,
            feeds_db=feeds_db,
        )


class MainBoardOut(BaseModel):
    """Serialised main distribution board."""

    id: uuid.UUID
    code: str
    drawing: str
    vlan_id: int
    subnet: str
    location: str | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_board(cls, board: object) -> "MainBoardOut":
        """Build MainBoardOut from an ORM MainBoard, coercing CIDR to str."""
        from app.db.models import MainBoard  # noqa: PLC0415

        assert isinstance(board, MainBoard)
        return cls(
            id=board.id,
            code=board.code,
            drawing=board.drawing,
            vlan_id=board.vlan_id,
            subnet=str(board.subnet),
            location=board.location,
        )


class MainBoardWithBreakersOut(MainBoardOut):
    """Main board including its child breakers."""

    breakers: list[BreakerOut]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@assets_router.get("/boards", response_model=list[MainBoardOut])
async def list_boards(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[MainBoardOut]:
    """Return all 9 active main boards ordered by code.

    Requires: any authenticated role (admin, operator, viewer).
    """
    boards = await asset_repo.list_main_boards(db)
    return [MainBoardOut.from_orm_board(b) for b in boards]


@assets_router.get("/boards/{board_id}", response_model=MainBoardWithBreakersOut)
async def get_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> MainBoardWithBreakersOut:
    """Return a single main board and all its breakers.

    Requires: any authenticated role.

    Args:
        board_id: UUID of the main board.

    Raises:
        NotFoundError: If the board does not exist or is soft-deleted.
    """
    board = await asset_repo.get_main_board(db, board_id)
    if board is None:
        raise NotFoundError(f"Main board {board_id} not found")
    breakers = await asset_repo.list_breakers(db, main_board_id=board_id)
    board_out = MainBoardOut.from_orm_board(board)
    return MainBoardWithBreakersOut(
        **board_out.model_dump(),
        breakers=[BreakerOut.from_orm_breaker(b) for b in breakers],
    )


@assets_router.get("/boards/{board_id}/breakers", response_model=list[BreakerOut])
async def list_board_breakers(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[BreakerOut]:
    """Return all active breakers for a specific main board.

    Requires: any authenticated role.

    Args:
        board_id: UUID of the main board.

    Raises:
        NotFoundError: If the board does not exist or is soft-deleted.
    """
    board = await asset_repo.get_main_board(db, board_id)
    if board is None:
        raise NotFoundError(f"Main board {board_id} not found")
    breakers = await asset_repo.list_breakers(db, main_board_id=board_id)
    return [BreakerOut.from_orm_breaker(b) for b in breakers]


@assets_router.get("/breakers", response_model=list[BreakerOut])
async def list_all_breakers(
    board: str | None = Query(default=None, description="Filter by main board code (e.g. MB1)"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[BreakerOut]:
    """Return all 104 active breakers, with optional ?board= filter by main board code.

    Requires: any authenticated role.

    Args:
        board: Optional main board code to filter by (e.g. 'MB1').
    """
    main_board_id: uuid.UUID | None = None
    if board is not None:
        from sqlalchemy import select  # noqa: PLC0415

        from app.db.models import MainBoard  # noqa: PLC0415

        result = await db.execute(
            select(MainBoard.id).where(
                MainBoard.code == board,
                MainBoard.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"Main board with code '{board}' not found")
        main_board_id = row
    breakers = await asset_repo.list_breakers(db, main_board_id=main_board_id)
    return [BreakerOut.from_orm_breaker(b) for b in breakers]
