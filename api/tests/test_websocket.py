# api/tests/test_websocket.py
"""WebSocket endpoint tests — auth, state sync, sync_request, disconnect."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app
from app.ws.manager import ConnectionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_access_token(role: str = "operator") -> str:
    """Create a valid access JWT for a random user."""
    return create_access_token(user_id=str(uuid.uuid4()), role=role)


def _cookie_header(token: str) -> dict[str, str]:
    """Return a headers dict containing the access_token cookie."""
    return {"cookie": f"access_token={token}"}


# ---------------------------------------------------------------------------
# Unit tests — ConnectionManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_connect_disconnect() -> None:
    """connect() accepts the socket; disconnect() removes it from the registry."""
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    uid = uuid.uuid4()

    await mgr.connect(ws, uid)
    assert ws in mgr._connections

    await mgr.disconnect(ws)
    assert ws not in mgr._connections


@pytest.mark.asyncio
async def test_manager_broadcast_sends_to_all() -> None:
    """broadcast() calls send_text on every connected socket."""
    mgr = ConnectionManager()

    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_text = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_text = AsyncMock()

    await mgr.connect(ws1, uuid.uuid4())
    await mgr.connect(ws2, uuid.uuid4())

    msg = {"type": "telemetry_update", "samples": [], "ts": "now"}
    await mgr.broadcast(msg)

    ws1.send_text.assert_called_once_with(json.dumps(msg))
    ws2.send_text.assert_called_once_with(json.dumps(msg))


@pytest.mark.asyncio
async def test_manager_broadcast_tolerates_broken_socket() -> None:
    """broadcast() swallows send errors so one bad socket doesn't drop others."""
    mgr = ConnectionManager()

    ws_bad = MagicMock()
    ws_bad.accept = AsyncMock()
    ws_bad.send_text = AsyncMock(side_effect=RuntimeError("broken"))

    ws_good = MagicMock()
    ws_good.accept = AsyncMock()
    ws_good.send_text = AsyncMock()

    await mgr.connect(ws_bad, uuid.uuid4())
    await mgr.connect(ws_good, uuid.uuid4())

    await mgr.broadcast({"type": "x"})
    ws_good.send_text.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests — /ws/live endpoint via Starlette TestClient
# ---------------------------------------------------------------------------
# Note: Starlette's synchronous TestClient is used for WebSocket tests because
# httpx's AsyncClient does not support the WebSocket protocol.
# The fake_redis fixture (autouse=True) from conftest ensures no real Redis.
# The override_get_db override is module-level in conftest, so DB is covered.
# ---------------------------------------------------------------------------


def _patch_get_state_snapshot(boards: list | None = None, alarms: list | None = None):  # type: ignore[no-untyped-def]
    """Return a context manager that patches get_state_snapshot with a canned response."""
    payload = {
        "type": "state_sync",
        "boards": boards or [],
        "active_alarms": alarms or [],
        "ts": datetime.now(UTC).isoformat(),
    }
    return patch(
        "app.ws.manager.get_state_snapshot",
        new=AsyncMock(return_value=payload),
    )


def _patch_user(active: bool = True) -> object:
    """Patch user_repo.get_user_by_id to return a mock User (or None)."""
    if not active:
        return patch("app.ws.router.user_repo.get_user_by_id", new=AsyncMock(return_value=None))
    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_active = True
    return patch(
        "app.ws.router.user_repo.get_user_by_id",
        new=AsyncMock(return_value=user),
    )


def _patch_redis_subscriber() -> object:
    """Patch _redis_subscriber so tests don't hang waiting for Redis pub/sub."""
    import asyncio  # noqa: PLC0415

    async def _noop(ws: object) -> None:  # noqa: ARG001
        # Block forever until cancelled — simulates real subscriber idle behaviour
        await asyncio.sleep(3600)

    return patch("app.ws.router._redis_subscriber", side_effect=_noop)


# ---------------------------------------------------------------------------


def test_ws_rejects_unauthenticated() -> None:
    """Connection without access_token cookie is closed with code 1008."""
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/live"):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008


def test_ws_rejects_invalid_token() -> None:
    """Connection with a malformed JWT is closed with code 1008."""
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws/live", headers={"cookie": "access_token=not.a.valid.jwt"}
            ):
                pass  # pragma: no cover
        assert exc_info.value.code == 1008


def test_ws_accepted_with_valid_token_receives_state_sync() -> None:
    """Valid JWT cookie → connection accepted → state_sync message received."""
    token = _make_access_token()

    with _patch_user(), _patch_redis_subscriber():
        canned = {
            "type": "state_sync",
            "boards": [{"id": str(uuid.uuid4()), "code": "MB1"}],
            "active_alarms": [],
            "ts": datetime.now(UTC).isoformat(),
        }
        with patch(
            "app.ws.state.get_state_snapshot", new=AsyncMock(return_value=canned)
        ):
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/live", headers=_cookie_header(token)
                ) as ws:
                    data = ws.receive_json()
                    assert data["type"] == "state_sync"
                    assert len(data["boards"]) == 1
                    assert data["boards"][0]["code"] == "MB1"


def test_ws_sync_request_triggers_state_sync() -> None:
    """Sending {"type": "sync_request"} causes another state_sync to be sent."""
    token = _make_access_token()

    with _patch_user(), _patch_redis_subscriber():
        canned = {
            "type": "state_sync",
            "boards": [],
            "active_alarms": [],
            "ts": datetime.now(UTC).isoformat(),
        }
        with patch(
            "app.ws.state.get_state_snapshot", new=AsyncMock(return_value=canned)
        ):
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/live", headers=_cookie_header(token)
                ) as ws:
                    # Consume the initial state_sync
                    first = ws.receive_json()
                    assert first["type"] == "state_sync"

                    # Request another sync
                    ws.send_json({"type": "sync_request"})
                    second = ws.receive_json()
                    assert second["type"] == "state_sync"


def test_ws_disconnect_is_handled_cleanly() -> None:
    """Closing the WebSocket does not raise an unhandled exception."""
    token = _make_access_token()

    with _patch_user(), _patch_redis_subscriber():
        canned = {
            "type": "state_sync",
            "boards": [],
            "active_alarms": [],
            "ts": datetime.now(UTC).isoformat(),
        }
        with patch(
            "app.ws.state.get_state_snapshot", new=AsyncMock(return_value=canned)
        ):
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws/live", headers=_cookie_header(token)
                ) as ws:
                    ws.receive_json()  # initial state_sync
                    ws.close()  # explicit clean disconnect
                # No exception raised — test passes
