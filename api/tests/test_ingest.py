"""Tests for POST /api/ingest/telemetry.

These tests use the ASGI transport (no real DB required for most cases)
and a patched AsyncSessionLocal / ws_manager.  Tests that need DB
state are skipped if TEST_DB_URL is unreachable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

VALID_TOKEN = "test-edge-token-abc123"
ASSET_ID = str(uuid.uuid4())
TS = datetime.now(UTC).isoformat()

VALID_BATCH = {
    "gateway_id": "gw-01",
    "samples": [
        {
            "asset_id": ASSET_ID,
            "timestamp": TS,
            "register": "breaker_state",
            "raw_value": 1,
            "comms_loss": False,
        }
    ],
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _auth_header(token: str = VALID_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_db_mock(valid_ids: list[str], prev_states: dict[str, str] | None = None):
    """Build a minimal AsyncSession mock that returns the given breaker rows."""
    if prev_states is None:
        prev_states = {}

    async def _execute(query, params=None):  # noqa: ANN001
        sql = str(query)
        mock_result = MagicMock()

        if "assets.breaker" in sql and "deleted_at IS NULL" in sql:
            rows = [
                {"id": aid, "label": f"LBL-{aid[:4]}", "main_board_ref": "MB01"}
                for aid in valid_ids
            ]
            mock_result.mappings.return_value.all.return_value = rows
        elif "DISTINCT ON (breaker_id)" in sql:
            rows = [
                {"breaker_id": bid, "state": state}
                for bid, state in prev_states.items()
            ]
            mock_result.mappings.return_value.all.return_value = rows
        else:
            mock_result.mappings.return_value.all.return_value = []

        return mock_result

    session = AsyncMock()
    session.execute = _execute
    session.commit = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_valid_batch_returns_202(client: AsyncClient) -> None:
    """Valid token + valid batch → 202 with accepted count."""
    db_ctx = _make_db_mock(valid_ids=[ASSET_ID])
    with (
        patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN),
        patch("app.routes.ingest.AsyncSessionLocal", return_value=db_ctx),
        patch("app.routes.ingest.ws_manager.broadcast", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=VALID_BATCH,
            headers=_auth_header(),
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_invalid_token_returns_401(client: AsyncClient) -> None:
    """Wrong bearer token → 401."""
    with patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=VALID_BATCH,
            headers=_auth_header("wrong-token"),
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_missing_token_returns_401(client: AsyncClient) -> None:
    """No Authorization header → 401."""
    with patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN):
        resp = await client.post("/api/ingest/telemetry", json=VALID_BATCH)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_malformed_payload_returns_422(client: AsyncClient) -> None:
    """Payload missing required fields → 422."""
    with patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN):
        resp = await client.post(
            "/api/ingest/telemetry",
            json={"gateway_id": "gw-01"},  # missing 'samples'
            headers=_auth_header(),
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_empty_samples_returns_422(client: AsyncClient) -> None:
    """Empty samples list → 422 (custom validator)."""
    with patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN):
        resp = await client.post(
            "/api/ingest/telemetry",
            json={"gateway_id": "gw-01", "samples": []},
            headers=_auth_header(),
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_unknown_asset_id_is_rejected(client: AsyncClient) -> None:
    """asset_id not found in DB → rejected count incremented."""
    db_ctx = _make_db_mock(valid_ids=[])  # no valid breakers
    with (
        patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN),
        patch("app.routes.ingest.AsyncSessionLocal", return_value=db_ctx),
        patch("app.routes.ingest.ws_manager.broadcast", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=VALID_BATCH,
            headers=_auth_header(),
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 1


@pytest.mark.asyncio
async def test_ingest_state_change_triggers_broadcast(client: AsyncClient) -> None:
    """State change (open → closed) triggers ws_manager.broadcast call."""
    db_ctx = _make_db_mock(
        valid_ids=[ASSET_ID],
        prev_states={ASSET_ID: "open"},  # was open, now raw_value=1 → closed
    )
    mock_broadcast = AsyncMock()
    with (
        patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN),
        patch("app.routes.ingest.AsyncSessionLocal", return_value=db_ctx),
        patch("app.routes.ingest.ws_manager.broadcast", mock_broadcast),
    ):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=VALID_BATCH,
            headers=_auth_header(),
        )
    assert resp.status_code == 202
    mock_broadcast.assert_awaited_once()
    call_arg = mock_broadcast.call_args[0][0]
    assert call_arg["type"] == "breaker_update"
    assert call_arg["state"] == "closed"
    assert call_arg["asset_id"] == ASSET_ID


@pytest.mark.asyncio
async def test_ingest_no_change_no_broadcast(client: AsyncClient) -> None:
    """Same state as previous reading → no broadcast."""
    db_ctx = _make_db_mock(
        valid_ids=[ASSET_ID],
        prev_states={ASSET_ID: "closed"},  # already closed
    )
    mock_broadcast = AsyncMock()
    with (
        patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN),
        patch("app.routes.ingest.AsyncSessionLocal", return_value=db_ctx),
        patch("app.routes.ingest.ws_manager.broadcast", mock_broadcast),
    ):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=VALID_BATCH,  # raw_value=1 → closed, same as prev
            headers=_auth_header(),
        )
    assert resp.status_code == 202
    mock_broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_comms_loss_broadcasts_comms_loss_message(client: AsyncClient) -> None:
    """comms_loss=true sample triggers a comms_loss broadcast."""
    batch = {
        "gateway_id": "gw-01",
        "samples": [
            {
                "asset_id": ASSET_ID,
                "timestamp": TS,
                "register": "breaker_state",
                "raw_value": 0,
                "comms_loss": True,
            }
        ],
    }
    db_ctx = _make_db_mock(valid_ids=[ASSET_ID])
    mock_broadcast = AsyncMock()
    with (
        patch("app.core.config.settings.edge_ingest_token", VALID_TOKEN),
        patch("app.routes.ingest.AsyncSessionLocal", return_value=db_ctx),
        patch("app.routes.ingest.ws_manager.broadcast", mock_broadcast),
    ):
        resp = await client.post(
            "/api/ingest/telemetry",
            json=batch,
            headers=_auth_header(),
        )
    assert resp.status_code == 202
    # Should have broadcast a comms_loss message
    call_types = [c[0][0]["type"] for c in mock_broadcast.call_args_list]
    assert "comms_loss" in call_types
