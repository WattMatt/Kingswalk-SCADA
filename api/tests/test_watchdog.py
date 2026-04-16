"""Tests for watchdog_service and comms_service."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.services.watchdog_service as ws
from app.services import comms_service
from tests.conftest import _make_test_engine

# ---------------------------------------------------------------------------
# record_telemetry_received
# ---------------------------------------------------------------------------


def test_record_telemetry_received_updates_timestamp() -> None:
    """record_telemetry_received sets _last_telemetry_ts to roughly now."""
    ws._last_telemetry_ts = None
    before = datetime.now(UTC)
    ws.record_telemetry_received()
    after = datetime.now(UTC)

    assert ws._last_telemetry_ts is not None
    assert before <= ws._last_telemetry_ts <= after


def test_record_telemetry_received_called_twice_updates() -> None:
    """Calling record_telemetry_received twice keeps the latest timestamp."""
    ws._last_telemetry_ts = None
    ws.record_telemetry_received()
    first = ws._last_telemetry_ts
    ws.record_telemetry_received()
    second = ws._last_telemetry_ts

    assert second is not None
    assert second >= first  # type: ignore[operator]


# ---------------------------------------------------------------------------
# watchdog_loop — does NOT fire when telemetry is recent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_no_alarm_when_recent() -> None:
    """Watchdog does not raise an alarm when telemetry arrived <30s ago."""
    ws._last_telemetry_ts = datetime.now(UTC)  # just now

    inserted_events: list = []

    async def fake_insert(*args: object, **kwargs: object) -> object:
        inserted_events.append(kwargs)
        return object()

    _no_alarm = AsyncMock(return_value=False)
    _no_insert = AsyncMock(side_effect=fake_insert)
    with (
        patch("app.services.watchdog_service.event_repo.recent_event_exists", new=_no_alarm),
        patch("app.services.watchdog_service.event_repo.insert_event", new=_no_insert),
        patch("app.services.watchdog_service.AsyncSessionLocal") as mock_session_cls,
    ):
        # Run loop for one tick (sleep=0 so it completes quickly in test).
        async def _one_tick() -> None:
            with patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
                try:
                    await ws.watchdog_loop()
                except asyncio.CancelledError:
                    pass

        await _one_tick()

    # No DB interactions expected because silence condition is false.
    mock_session_cls.assert_not_called()
    assert inserted_events == []


# ---------------------------------------------------------------------------
# watchdog_loop — DOES fire when telemetry is silent >30s
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_fires_alarm_when_silent() -> None:
    """Watchdog raises CRITICAL alarm when no telemetry for >30s."""
    ws._last_telemetry_ts = datetime.now(UTC) - timedelta(seconds=60)  # 60s ago

    inserted_events: list = []

    async def fake_insert(*args: object, **kwargs: object) -> object:
        inserted_events.append(kwargs)
        return object()

    # Build a context manager mock: AsyncSessionLocal() is a sync callable that
    # returns an async context manager (like async_sessionmaker does).
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_db)

    with (
        patch(
            "app.services.watchdog_service.event_repo.recent_event_exists",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.services.watchdog_service.event_repo.insert_event",
            new=AsyncMock(side_effect=fake_insert),
        ),
        patch(
            "app.services.watchdog_service.AsyncSessionLocal",
            mock_session_factory,
        ),
        patch("asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])),
    ):
        try:
            await ws.watchdog_loop()
        except asyncio.CancelledError:
            pass

    assert len(inserted_events) == 1
    ev = inserted_events[0]
    assert ev["severity"] == "critical"
    assert ev["kind"] == "edge_watchdog"
    assert "30s" in ev["message"]


# ---------------------------------------------------------------------------
# watchdog_loop — dedup: does NOT fire twice within 5 minutes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_dedup_no_second_alarm() -> None:
    """Watchdog does not insert a second alarm within the dedup window."""
    ws._last_telemetry_ts = datetime.now(UTC) - timedelta(seconds=60)

    inserted_events: list = []

    async def fake_insert(*args: object, **kwargs: object) -> object:
        inserted_events.append(kwargs)
        return object()

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_db)

    with (
        patch(
            "app.services.watchdog_service.event_repo.recent_event_exists",
            new=AsyncMock(return_value=True),  # already alarmed
        ),
        patch(
            "app.services.watchdog_service.event_repo.insert_event",
            new=AsyncMock(side_effect=fake_insert),
        ),
        patch(
            "app.services.watchdog_service.AsyncSessionLocal",
            mock_session_factory,
        ),
        patch("asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])),
    ):
        try:
            await ws.watchdog_loop()
        except asyncio.CancelledError:
            pass

    assert inserted_events == []


# ---------------------------------------------------------------------------
# get_freshness_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_freshness_status_classifies_correctly(clean_tables: None) -> None:
    """get_freshness_status returns fresh/stale/comms_loss based on age."""
    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        # fresh: 30s ago
        await db.execute(text(
            "INSERT INTO telemetry.raw_sample (ts, device_id, register_address, raw_value) "
            "VALUES (NOW() - INTERVAL '30 seconds', 'device_fresh', 0, 100)"
        ))
        # stale: 120s ago
        await db.execute(text(
            "INSERT INTO telemetry.raw_sample (ts, device_id, register_address, raw_value) "
            "VALUES (NOW() - INTERVAL '120 seconds', 'device_stale', 0, 200)"
        ))
        # comms_loss: 400s ago
        await db.execute(text(
            "INSERT INTO telemetry.raw_sample (ts, device_id, register_address, raw_value) "
            "VALUES (NOW() - INTERVAL '400 seconds', 'device_comms_loss', 0, 300)"
        ))
        await db.commit()

        result = await comms_service.get_freshness_status(db)

    await engine.dispose()

    assert result["device_fresh"] == "fresh"
    assert result["device_stale"] == "stale"
    assert result["device_comms_loss"] == "comms_loss"


@pytest.mark.asyncio
async def test_get_freshness_status_empty_returns_empty(clean_tables: None) -> None:
    """get_freshness_status returns empty dict when no devices exist."""
    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as db:
        result = await comms_service.get_freshness_status(db)

    await engine.dispose()
    assert result == {}


# ---------------------------------------------------------------------------
# GET /api/health/telemetry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telemetry_health_returns_200(client: AsyncClient) -> None:
    """GET /api/health/telemetry returns 200."""
    ws._last_telemetry_ts = None
    with patch(
        "app.routes.health.comms_service.get_freshness_status",
        new=AsyncMock(return_value={}),
    ):
        response = await client.get("/api/health/telemetry")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_telemetry_health_unknown_when_no_telemetry(client: AsyncClient) -> None:
    """Status is 'unknown' when no telemetry has ever been received."""
    ws._last_telemetry_ts = None
    with patch(
        "app.routes.health.comms_service.get_freshness_status",
        new=AsyncMock(return_value={}),
    ):
        response = await client.get("/api/health/telemetry")
    body = response.json()
    assert body["status"] == "unknown"
    assert body["last_telemetry_at"] is None
    assert body["silence_seconds"] is None
    assert isinstance(body["device_freshness"], dict)


@pytest.mark.asyncio
async def test_telemetry_health_ok_when_recent(client: AsyncClient) -> None:
    """Status is 'ok' when telemetry arrived within silence threshold."""
    ws._last_telemetry_ts = datetime.now(UTC)
    with patch(
        "app.routes.health.comms_service.get_freshness_status",
        new=AsyncMock(return_value={"dev1": "fresh"}),
    ):
        response = await client.get("/api/health/telemetry")
    body = response.json()
    assert body["status"] == "ok"
    assert body["last_telemetry_at"] is not None
    assert body["silence_seconds"] is not None
    assert body["silence_seconds"] < ws.SILENCE_THRESHOLD_SEC


@pytest.mark.asyncio
async def test_telemetry_health_silent_when_old(client: AsyncClient) -> None:
    """Status is 'silent' when last telemetry is older than silence threshold."""
    ws._last_telemetry_ts = datetime.now(UTC) - timedelta(seconds=120)
    with patch(
        "app.routes.health.comms_service.get_freshness_status",
        new=AsyncMock(return_value={"dev1": "comms_loss"}),
    ):
        response = await client.get("/api/health/telemetry")
    body = response.json()
    assert body["status"] == "silent"
    assert body["silence_seconds"] >= ws.SILENCE_THRESHOLD_SEC
