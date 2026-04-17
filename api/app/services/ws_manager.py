"""WebSocket connection manager for live breaker state broadcasts.

Maintains an in-memory registry of connected WebSocket clients, with a
10-message-per-second token-bucket throttle per connection.  No Redis
required for Phase 2 — all state lives in this process.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

import structlog
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = structlog.get_logger()

# Token-bucket constants — 10 msgs/sec, burst of 10.
_RATE_LIMIT = 10  # messages per second
_BUCKET_CAPACITY = 10  # max burst


class _BucketState:
    """Token-bucket state per WebSocket connection."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self) -> None:
        self.tokens: float = float(_BUCKET_CAPACITY)
        self.last_refill: float = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token.  Returns True if the message should be sent."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            float(_BUCKET_CAPACITY),
            self.tokens + elapsed * _RATE_LIMIT,
        )
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class WsManager:
    """In-memory WebSocket connection registry.

    Thread safety: FastAPI/Starlette's async event loop serialises all
    coroutine execution, so plain dicts are safe here without locks.
    """

    def __init__(self) -> None:
        # user_id (str) → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # WebSocket → token-bucket state
        self._buckets: dict[WebSocket, _BucketState] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, user_id: str | uuid.UUID) -> None:
        """Register a new connection.  Caller is responsible for accept()."""
        uid = str(user_id)
        self._connections[uid].add(websocket)
        self._buckets[websocket] = _BucketState()
        logger.info("ws.connect", user_id=uid, total=self._total_connections())

    async def disconnect(self, websocket: WebSocket, user_id: str | uuid.UUID) -> None:
        """Remove a connection from the registry."""
        uid = str(user_id)
        self._connections[uid].discard(websocket)
        if not self._connections[uid]:
            del self._connections[uid]
        self._buckets.pop(websocket, None)
        logger.info("ws.disconnect", user_id=uid, total=self._total_connections())

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def broadcast(self, message: dict) -> None:  # type: ignore[type-arg]
        """Send *message* to every connected client, honouring rate limits."""
        dead: list[tuple[str, WebSocket]] = []
        for uid, connections in list(self._connections.items()):
            for ws in list(connections):
                sent = await self._send(ws, message)
                if sent is False:
                    dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(ws, uid)

    async def send_to_user(
        self, user_id: str | uuid.UUID, message: dict  # type: ignore[type-arg]
    ) -> None:
        """Send *message* to all connections belonging to *user_id*."""
        uid = str(user_id)
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(uid, set())):
            sent = await self._send(ws, message)
            if sent is False:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, uid)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send(self, ws: WebSocket, message: dict) -> bool | None:  # type: ignore[type-arg]
        """Send JSON to a single WebSocket.

        Returns:
            True  — message sent successfully.
            None  — dropped by rate-limiter (not an error).
            False — connection is dead; caller should clean it up.
        """
        bucket = self._buckets.get(ws)
        if bucket is None:
            return False
        if not bucket.consume():
            logger.debug("ws.rate_limited", ws_id=id(ws))
            return None
        try:
            if ws.client_state != WebSocketState.CONNECTED:
                return False
            await ws.send_json(message)
            return True
        except Exception as exc:  # noqa: BLE001 — send errors are expected on abrupt close
            logger.debug("ws.send_failed", error=str(exc))
            return False

    def _total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Singleton — import this everywhere.
ws_manager = WsManager()
