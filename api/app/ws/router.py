# api/app/ws/router.py
"""WebSocket endpoint — JWT auth, Redis pub/sub fan-out, 10 msg/sec throttle."""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.core.security import decode_token
from app.db.engine import get_db
from app.db.models import User
from app.repos import user_repo
from app.ws.manager import manager

log = structlog.get_logger()

ws_router = APIRouter(tags=["websocket"])

_REDIS_CHANNEL = "telemetry:live"


def _extract_cookie(websocket: WebSocket, name: str) -> str | None:
    """Parse a named cookie from the WebSocket handshake Cookie header.

    WebSocket connections cannot use FastAPI's ``Cookie`` dependency because
    the dependency injection pipeline runs before the connection is accepted.
    We read the raw ``cookie`` header from the scope instead.

    Args:
        websocket: Incoming WebSocket connection (not yet accepted).
        name: Cookie name to extract.

    Returns:
        The cookie value, or None if not present.
    """
    cookie_header: str | None = None
    for key, value in websocket.headers.items():
        if key.lower() == "cookie":
            cookie_header = value
            break
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == name:
            return v.strip()
    return None


async def _authenticate_ws(
    websocket: WebSocket, db: AsyncSession
) -> User | None:
    """Extract and validate the access_token cookie from a WebSocket handshake.

    Closes the connection with code 1008 (policy violation) if auth fails.

    Args:
        websocket: Incoming WebSocket (not yet accepted).
        db: Database session for user lookup.

    Returns:
        Authenticated User on success, None on failure (connection already closed).
    """
    token = _extract_cookie(websocket, "access_token")
    if not token:
        await websocket.close(code=1008, reason="Missing access_token cookie")
        log.warning("ws.auth_rejected", reason="no_token")
        return None

    try:
        payload = decode_token(token, expected_aud="access")
        sub = payload.get("sub")
        if not isinstance(sub, str):
            raise ValueError("Missing sub claim")
        user = await user_repo.get_user_by_id(db, uuid.UUID(sub))
    except Exception as exc:
        await websocket.close(code=1008, reason="Invalid access_token")
        log.warning("ws.auth_rejected", reason=str(exc))
        return None

    if user is None or not user.is_active:
        await websocket.close(code=1008, reason="User not found or inactive")
        log.warning("ws.auth_rejected", reason="inactive_user")
        return None

    return user


async def _redis_subscriber(websocket: WebSocket) -> None:
    """Subscribe to the Redis telemetry:live channel and forward messages.

    Runs as a background task for the lifetime of a WebSocket connection.
    Messages arriving on the pub/sub channel are broadcast to all connected clients.

    Each message published by the ingest pipeline has the shape::

        {"samples": [{"device_id": ..., "register_address": ..., ...}]}

    The subscriber wraps this in the standard outbound envelope.

    Args:
        websocket: The owning connection — used only for context in logging.
    """
    redis = await get_redis()
    # Use a dedicated connection for pub/sub; the main singleton stays available
    # for regular commands. We duplicate the client config via from_url.
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(_REDIS_CHANNEL)
        log.debug("ws.subscribed", channel=_REDIS_CHANNEL)
        async for raw_msg in pubsub.listen():
            if raw_msg["type"] != "message":
                continue
            try:
                data = json.loads(raw_msg["data"])
            except (json.JSONDecodeError, TypeError):
                log.warning("ws.invalid_redis_msg")
                continue
            outbound = {
                "type": "telemetry_update",
                "samples": data.get("samples", []),
                "ts": data.get("ts", ""),
            }
            await manager.broadcast(outbound)
    except asyncio.CancelledError:
        log.debug("ws.subscriber_cancelled")
        raise
    finally:
        try:
            await pubsub.unsubscribe(_REDIS_CHANNEL)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
        except Exception:
            pass


@ws_router.websocket("/ws/live")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Real-time telemetry WebSocket endpoint.

    Protocol
    --------
    * Auth: ``access_token`` HttpOnly cookie, validated before handshake accept.
      Invalid/missing cookie → close with code 1008.
    * On connect: full state sync (all boards + breakers + active alarms).
    * Inbound: ``{"type": "sync_request"}`` → triggers another full state sync.
    * Outbound: ``{"type": "telemetry_update", "samples": [...], "ts": "..."}``
      and ``{"type": "state_sync", "boards": [...], "active_alarms": [...], "ts": "..."}``.
    * Rate limit: 100ms minimum between sends per client (max 10 msg/sec).
    * Disconnect: background Redis subscriber is cancelled, connection removed.

    Args:
        websocket: Incoming WebSocket connection.
        db: Async database session (injected by FastAPI).
    """
    user = await _authenticate_ws(websocket, db)
    if user is None:
        return  # Connection already closed with 1008

    await manager.connect(websocket, user.id)
    subscriber_task: asyncio.Task[None] | None = None

    try:
        # Send full state snapshot immediately on connect
        await manager.send_sync(websocket, db)

        # Start background Redis listener
        subscriber_task = asyncio.create_task(
            _redis_subscriber(websocket),
            name=f"ws-sub-{user.id}",
        )

        # Receive loop — only sync_request is handled
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if isinstance(msg, dict) and msg.get("type") == "sync_request":
                log.debug("ws.sync_request", user_id=str(user.id))
                await manager.send_sync(websocket, db)

    except WebSocketDisconnect:
        pass
    finally:
        if subscriber_task is not None and not subscriber_task.done():
            subscriber_task.cancel()
            try:
                await subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
        await manager.disconnect(websocket)
