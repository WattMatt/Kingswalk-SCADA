"""WebSocket endpoint — live breaker state updates.

Route: GET /ws  (registered under /api prefix → full path: /api/ws)

Authentication: JWT from the HttpOnly ``access_token`` cookie.
On invalid / missing token the connection is closed with code 1008
(Policy Violation) before any application data is sent.

On connect the server immediately sends a ``full_snapshot`` message
containing the current state of every breaker, then keeps the
connection open for server-push ``breaker_update`` / ``comms_loss``
messages via :pyobj:`ws_manager`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.engine import AsyncSessionLocal
from app.services.ws_manager import ws_manager

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])


async def _get_full_snapshot(db: AsyncSession) -> dict:  # type: ignore[type-arg]
    """Query the DB for the current state of all breakers.

    Uses a raw SQL query joining ``assets.breaker``,
    ``assets.main_board``, and the latest row from
    ``telemetry.breaker_state`` (DISTINCT ON) so we get one current
    state per breaker without a separate subquery per row.
    """
    result = await db.execute(
        text(
            """
            SELECT
                b.id::text              AS asset_id,
                b.label,
                mb.code                 AS main_board_ref,
                COALESCE(bs.state, 'unknown') AS state,
                false                   AS comms_loss,
                bs.ts                   AS last_seen
            FROM assets.breaker b
            JOIN assets.main_board mb ON mb.id = b.main_board_id
            LEFT JOIN LATERAL (
                SELECT state, ts
                FROM telemetry.breaker_state
                WHERE breaker_id = b.id
                ORDER BY ts DESC
                LIMIT 1
            ) bs ON true
            WHERE b.deleted_at IS NULL
            ORDER BY mb.code, b.label
            """
        )
    )
    rows = result.mappings().all()
    breakers = [
        {
            "asset_id": row["asset_id"],
            "label": row["label"],
            "main_board_ref": row["main_board_ref"],
            "state": row["state"],
            "comms_loss": row["comms_loss"],
            "last_seen": (
                row["last_seen"].isoformat() if row["last_seen"] else None
            ),
        }
        for row in rows
    ]
    return {
        "type": "full_snapshot",
        "timestamp": datetime.now(UTC).isoformat(),
        "breakers": breakers,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept WebSocket connections authenticated via access_token cookie."""
    # ── 1. Auth: extract and validate JWT from cookie ──────────────────
    token: str | None = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=1008)
        logger.warning("ws.auth_failed", reason="no_cookie")
        return

    try:
        payload = decode_token(token, expected_aud="access")
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        await websocket.close(code=1008)
        logger.warning("ws.auth_failed", reason=str(exc))
        return

    # ── 2. Accept connection and register ──────────────────────────────
    await websocket.accept()
    await ws_manager.connect(websocket, user_id)
    logger.info("ws.connected", user_id=str(user_id))

    try:
        # ── 3. Send full snapshot ──────────────────────────────────────
        async with AsyncSessionLocal() as db:
            snapshot = await _get_full_snapshot(db)
        await websocket.send_json(snapshot)

        # ── 4. Keep-alive loop ─────────────────────────────────────────
        # We only push server → client; there's nothing meaningful to
        # receive.  We still need to await incoming frames so that
        # WebSocketDisconnect is raised on close, and to handle pings.
        while True:
            # receive_text() / receive_bytes() / receive_json() all raise
            # WebSocketDisconnect when the client closes the connection.
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("ws.disconnected", user_id=str(user_id))
    except Exception as exc:
        logger.error("ws.error", user_id=str(user_id), error=str(exc))
    finally:
        await ws_manager.disconnect(websocket, user_id)
