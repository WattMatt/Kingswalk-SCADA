# api/tests/test_assets.py
"""Tests for /api/assets/* and /api/events/* endpoints.

Uses async mock overrides for the repo layer so no live database is required.
Auth is exercised by overriding get_current_user for authenticated tests
and restoring the real dependency for the 401 cases.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.rbac import get_current_user
from app.db.engine import get_db
from app.db.models import Breaker, DistributionBoard, MainBoard, User
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BOARD_ID = uuid.uuid4()
_BREAKER_ID = uuid.uuid4()
_DB_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_EVENT_ID = 1


def _make_board(board_id: uuid.UUID = _BOARD_ID) -> MainBoard:
    """Build a minimal MainBoard ORM stub."""
    board = MagicMock(spec=MainBoard)
    board.id = board_id
    board.code = "MB1"
    board.drawing = "DWG-001"
    board.vlan_id = 10
    board.subnet = "192.168.10.0/24"
    board.gateway_ip = "192.168.10.1"
    board.location = "Basement"
    board.deleted_at = None
    return board


def _make_db() -> DistributionBoard:
    """Build a minimal DistributionBoard ORM stub."""
    db = MagicMock(spec=DistributionBoard)
    db.id = _DB_ID
    db.code = "DB-A1"
    db.name = "Tenant A"
    db.area_m2 = 120.5
    db.deleted_at = None
    return db


def _make_breaker(main_board_id: uuid.UUID = _BOARD_ID) -> Breaker:
    """Build a minimal Breaker ORM stub."""
    br = MagicMock(spec=Breaker)
    br.id = _BREAKER_ID
    br.main_board_id = main_board_id
    br.label = "BKR-001"
    br.breaker_code = "BC001"
    br.abb_family = "Tmax XT"
    br.rating_amp = 100
    br.poles = "TP"
    br.mp_code = "MP2"
    br.essential_supply = False
    br.device_ip = None
    br.distribution_board = _make_db()
    br.deleted_at = None
    return br


def _make_user(role: str = "operator") -> User:
    """Build a minimal User ORM stub."""
    user = MagicMock(spec=User)
    user.id = _USER_ID
    user.role = role
    user.is_active = True
    return user


def _make_event(acknowledged: bool = False) -> Any:
    """Build a minimal Event-like stub."""
    ev = MagicMock()
    ev.id = _EVENT_ID
    ev.ts = datetime.now(UTC)
    ev.asset_id = None
    ev.severity = "warning"
    ev.kind = "threshold.breach"
    ev.message = "Voltage out of range"
    ev.payload = {}
    ev.acknowledged_by = _USER_ID if acknowledged else None
    ev.acknowledged_at = datetime.now(UTC) if acknowledged else None
    return ev


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def authed_client(client: AsyncClient) -> AsyncClient:
    """Override get_current_user to return a mock operator."""
    user = _make_user("operator")
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def viewer_client(client: AsyncClient) -> AsyncClient:
    """Override get_current_user to return a mock viewer."""
    user = _make_user("viewer")
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(client: AsyncClient) -> AsyncClient:
    """Override get_current_user to return a mock admin."""
    user = _make_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /api/assets/boards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_boards_returns_200(authed_client: AsyncClient) -> None:
    """Authenticated user receives a list of boards."""
    boards = [_make_board()]
    with patch("app.routes.assets.asset_repo.list_main_boards", new=AsyncMock(return_value=boards)):
        response = await authed_client.get("/api/assets/boards")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["code"] == "MB1"
    assert body[0]["vlan_id"] == 10


@pytest.mark.asyncio
async def test_list_boards_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Request without a token returns 401."""
    response = await client.get("/api/assets/boards")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_boards_viewer_allowed(viewer_client: AsyncClient) -> None:
    """Viewer role can read boards."""
    boards = [_make_board()]
    with patch("app.routes.assets.asset_repo.list_main_boards", new=AsyncMock(return_value=boards)):
        response = await viewer_client.get("/api/assets/boards")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/assets/boards/{board_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_board_returns_board_and_breakers(authed_client: AsyncClient) -> None:
    """Single board endpoint returns board data plus its breakers."""
    board = _make_board()
    breakers = [_make_breaker()]
    with (
        patch("app.routes.assets.asset_repo.get_main_board", new=AsyncMock(return_value=board)),
        patch("app.routes.assets.asset_repo.list_breakers", new=AsyncMock(return_value=breakers)),
    ):
        response = await authed_client.get(f"/api/assets/boards/{_BOARD_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "MB1"
    assert "breakers" in body
    assert len(body["breakers"]) == 1
    assert body["breakers"][0]["label"] == "BKR-001"


@pytest.mark.asyncio
async def test_get_board_not_found_returns_404(authed_client: AsyncClient) -> None:
    """Missing board returns 404."""
    with patch("app.routes.assets.asset_repo.get_main_board", new=AsyncMock(return_value=None)):
        response = await authed_client.get(f"/api/assets/boards/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/assets/boards/{board_id}/breakers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_board_breakers_returns_200(authed_client: AsyncClient) -> None:
    """Breakers-for-board endpoint returns list of breakers."""
    board = _make_board()
    breakers = [_make_breaker()]
    with (
        patch("app.routes.assets.asset_repo.get_main_board", new=AsyncMock(return_value=board)),
        patch("app.routes.assets.asset_repo.list_breakers", new=AsyncMock(return_value=breakers)),
    ):
        response = await authed_client.get(f"/api/assets/boards/{_BOARD_ID}/breakers")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["breaker_code"] == "BC001"


@pytest.mark.asyncio
async def test_list_board_breakers_not_found_returns_404(authed_client: AsyncClient) -> None:
    """Missing board returns 404 on breakers sub-endpoint."""
    with patch("app.routes.assets.asset_repo.get_main_board", new=AsyncMock(return_value=None)):
        response = await authed_client.get(f"/api/assets/boards/{uuid.uuid4()}/breakers")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/assets/breakers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_breakers_returns_200(authed_client: AsyncClient) -> None:
    """All-breakers endpoint returns a flat list."""
    breakers = [_make_breaker()]
    with patch("app.routes.assets.asset_repo.list_breakers", new=AsyncMock(return_value=breakers)):
        response = await authed_client.get("/api/assets/breakers")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["label"] == "BKR-001"


@pytest.mark.asyncio
async def test_list_all_breakers_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Unauthenticated request to breakers endpoint returns 401."""
    response = await client.get("/api/assets/breakers")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_returns_200(authed_client: AsyncClient) -> None:
    """Authenticated user can list events."""
    ev = _make_event()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ev]

    async def mock_execute(*args: Any, **kwargs: Any) -> Any:
        return mock_result

    with patch("app.routes.events.AsyncSession.execute", new=mock_execute):
        # Use dependency override for get_db to return a mock session
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        original_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            response = await authed_client.get("/api/events")
        finally:
            if original_override is not None:
                app.dependency_overrides[get_db] = original_override
            else:
                app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_list_events_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Unauthenticated request to events list returns 401."""
    response = await client.get("/api/events")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/events/{event_id}/ack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ack_event_viewer_returns_403(viewer_client: AsyncClient) -> None:
    """Viewer role cannot acknowledge events — must return 403."""
    response = await viewer_client.post(f"/api/events/{_EVENT_ID}/ack")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ack_event_operator_returns_200(authed_client: AsyncClient) -> None:
    """Operator can acknowledge an unacknowledged event."""
    ev = _make_event(acknowledged=False)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = ev
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        response = await authed_client.post(f"/api/events/{_EVENT_ID}/ack")
    finally:
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _EVENT_ID


@pytest.mark.asyncio
async def test_ack_event_not_found_returns_404(authed_client: AsyncClient) -> None:
    """Acknowledge on a missing or already-acked event returns 404."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        response = await authed_client.post(f"/api/events/{_EVENT_ID}/ack")
    finally:
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ack_event_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Unauthenticated ack attempt returns 401."""
    response = await client.post(f"/api/events/{_EVENT_ID}/ack")
    assert response.status_code == 401
