# api/app/ws/manager.py
"""WebSocket connection manager — fan-out with per-client rate limiting."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()

# Minimum gap between sends to a single client (100ms = 10 msg/sec max)
_MIN_INTERVAL_SECONDS: float = 0.1


@dataclass
class _ConnState:
    """Per-connection tracking state."""

    user_id: uuid.UUID
    last_sent: float = field(default_factory=lambda: 0.0)
    pending: dict[str, Any] | None = None


class ConnectionManager:
    """Manages active WebSocket connections with rate limiting and Redis fan-out.

    Enforces a maximum of 10 messages per second per client. If a message arrives
    before the 100ms window has elapsed, it is buffered and sent on the next tick.
    """

    def __init__(self) -> None:
        self._connections: dict[WebSocket, _ConnState] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        """Accept the WebSocket handshake and register the connection.

        Args:
            websocket: The incoming WebSocket connection.
            user_id: Authenticated user UUID for audit logging.
        """
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = _ConnState(user_id=user_id)
        log.info("ws.connected", user_id=str(user_id), active=len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove the connection from the registry.

        Args:
            websocket: The WebSocket connection to remove.
        """
        async with self._lock:
            state = self._connections.pop(websocket, None)
        if state:
            log.info("ws.disconnected", user_id=str(state.user_id))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients, respecting per-client rate limits.

        If a client was sent a message less than 100ms ago, the new message is
        buffered (overwriting any previous buffer) and dispatched after a short yield.

        Args:
            message: JSON-serialisable dict to broadcast.
        """
        async with self._lock:
            snapshot = dict(self._connections)

        now = time.monotonic()
        for ws, state in snapshot.items():
            elapsed = now - state.last_sent
            if elapsed < _MIN_INTERVAL_SECONDS:
                # Buffer and defer — overwrite any older buffered message
                state.pending = message
                asyncio.ensure_future(self._deferred_send(ws, state, elapsed))
            else:
                await self._send(ws, state, message)

    async def _deferred_send(
        self, websocket: WebSocket, state: _ConnState, elapsed: float
    ) -> None:
        """Wait out the remaining rate-limit window, then send the buffered message.

        Args:
            websocket: Target connection.
            state: Per-connection state object.
            elapsed: Seconds already elapsed since last send.
        """
        wait = _MIN_INTERVAL_SECONDS - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        msg = state.pending
        if msg is not None:
            state.pending = None
            await self._send(websocket, state, msg)

    async def _send(
        self, websocket: WebSocket, state: _ConnState, message: dict[str, Any]
    ) -> None:
        """Serialise and transmit a message, handling stale connections gracefully.

        Args:
            websocket: Target connection.
            state: Per-connection state (last_sent is updated on success).
            message: JSON-serialisable payload.
        """
        try:
            await websocket.send_text(json.dumps(message))
            state.last_sent = time.monotonic()
        except Exception:
            log.warning("ws.send_failed", user_id=str(state.user_id))

    async def send_sync(self, websocket: WebSocket, db: AsyncSession) -> None:
        """Send a full state snapshot to a newly connected (or reconnected) client.

        Imports state lazily to avoid circular imports between ws modules.

        Args:
            websocket: Target connection.
            db: Active database session for the snapshot query.
        """
        from app.ws.state import get_state_snapshot  # noqa: PLC0415

        snapshot = await get_state_snapshot(db)
        async with self._lock:
            state = self._connections.get(websocket)
        if state is not None:
            await self._send(websocket, state, snapshot)


# Module-level singleton shared by the router
manager = ConnectionManager()
