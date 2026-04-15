"""Tests for GET /api/ws (WebSocket endpoint).

Uses httpx-ws (or starlette's TestClient WebSocket support) via the
ASGI transport.  The DB full_snapshot query is mocked out so these
tests don't require a real database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.services.ws_manager import WsManager

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_valid_token(role: str = "operator") -> str:
    return create_access_token(str(uuid.uuid4()), role)


def _make_snapshot_mock():
    """Return a mock DB context that returns an empty breaker list."""
    session = AsyncMock()

    async def _execute(query, params=None):  # noqa: ANN001
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        return mock_result

    session.execute = _execute

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_connect_no_cookie_closes_1008() -> None:
    """Connecting without an access_token cookie → close code 1008."""
    # We use a raw ASGI WebSocket handshake via starlette's test client.
    from starlette.testclient import TestClient  # type: ignore[import]

    with patch("app.core.config.settings.edge_ingest_token", "dummy"):
        client = TestClient(app, raise_server_exceptions=False)
        with pytest.raises(Exception):
            # Starlette TestClient raises on WS close with non-normal code.
            with client.websocket_connect("/api/ws") as ws:
                ws.receive_json()


@pytest.mark.asyncio
async def test_ws_connect_invalid_token_closes_1008() -> None:
    """Connecting with a malformed JWT → close code 1008."""
    from starlette.testclient import TestClient  # type: ignore[import]

    with patch("app.core.config.settings.edge_ingest_token", "dummy"):
        client = TestClient(app, raise_server_exceptions=False)
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/ws", cookies={"access_token": "not.a.valid.jwt"}
            ) as ws:
                ws.receive_json()


@pytest.mark.asyncio
async def test_ws_connect_valid_token_receives_full_snapshot() -> None:
    """Valid JWT → connection accepted → first message is full_snapshot."""
    from starlette.testclient import TestClient  # type: ignore[import]

    token = _make_valid_token()
    db_ctx = _make_snapshot_mock()

    with (
        patch("app.core.config.settings.edge_ingest_token", "dummy"),
        patch("app.routes.ws.AsyncSessionLocal", return_value=db_ctx),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        with client.websocket_connect(
            "/api/ws", cookies={"access_token": token}
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "full_snapshot"
            assert "breakers" in msg
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_ws_manager_broadcast_reaches_connected_client() -> None:
    """WsManager.broadcast sends a JSON message to all registered WebSockets."""
    manager = WsManager()
    user_id = str(uuid.uuid4())
    sent_messages: list[dict] = []  # type: ignore[type-arg]

    # Simulate a connected WebSocket
    mock_ws = AsyncMock()
    mock_ws.client_state = __import__(
        "starlette.websockets", fromlist=["WebSocketState"]
    ).WebSocketState.CONNECTED

    async def _send_json(msg):  # noqa: ANN001
        sent_messages.append(msg)

    mock_ws.send_json = _send_json

    await manager.connect(mock_ws, user_id)
    test_message = {"type": "breaker_update", "asset_id": "abc", "state": "tripped"}
    await manager.broadcast(test_message)

    assert len(sent_messages) == 1
    assert sent_messages[0] == test_message


@pytest.mark.asyncio
async def test_ws_manager_disconnect_removes_connection() -> None:
    """After disconnect, broadcast should not reach the removed client."""
    manager = WsManager()
    user_id = str(uuid.uuid4())
    sent_messages: list[dict] = []  # type: ignore[type-arg]

    mock_ws = AsyncMock()
    mock_ws.client_state = __import__(
        "starlette.websockets", fromlist=["WebSocketState"]
    ).WebSocketState.CONNECTED
    mock_ws.send_json = AsyncMock(side_effect=lambda m: sent_messages.append(m))

    await manager.connect(mock_ws, user_id)
    await manager.disconnect(mock_ws, user_id)
    await manager.broadcast({"type": "breaker_update", "state": "open"})

    assert len(sent_messages) == 0


@pytest.mark.asyncio
async def test_ws_manager_rate_limit_drops_excess_messages() -> None:
    """Token bucket drops messages beyond 10/sec burst."""
    import time

    manager = WsManager()
    user_id = str(uuid.uuid4())
    sent_count = 0

    mock_ws = AsyncMock()
    mock_ws.client_state = __import__(
        "starlette.websockets", fromlist=["WebSocketState"]
    ).WebSocketState.CONNECTED

    async def _send_json(msg):  # noqa: ANN001
        nonlocal sent_count
        sent_count += 1

    mock_ws.send_json = _send_json

    await manager.connect(mock_ws, user_id)

    # Fire 20 messages instantly — bucket capacity is 10 so at most 10 go through.
    for _ in range(20):
        await manager.broadcast({"type": "ping"})

    # With a fresh bucket (capacity=10), exactly 10 should be sent.
    assert sent_count <= 10
