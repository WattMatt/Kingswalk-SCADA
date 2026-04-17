# api/tests/test_telemetry.py
"""Unit tests for GET /api/telemetry.

These tests mock the repository and DB layers so they run without a real
PostgreSQL connection.  They validate:
  - valid metric names are accepted
  - unknown metric names return 422
  - missing board_id returns 422 (FastAPI validation)
  - 404 when board is not found (mocked)
  - correct shape of TelemetryResponse for a valid call
  - bucket_minutes clamping (1–60 valid, 0 / 61 rejected)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

_BOARD_UUID = uuid.uuid4()
_BOARD_CODE = "MB-1.1"


def _make_auth_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = "operator"
    return user


def _make_board_row(code: str = _BOARD_CODE) -> MagicMock:
    row = MagicMock()
    row.id = _BOARD_UUID
    row.code = code
    return row


# ── Metric validation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetry_unknown_metric_returns_422(client: AsyncClient) -> None:
    """An unknown metric name should return HTTP 422."""
    from app.core.rbac import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()
    try:
        resp = await client.get(
            "/api/telemetry",
            params={"board_id": str(_BOARD_UUID), "metric": "does_not_exist"},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_telemetry_missing_board_id_returns_422(client: AsyncClient) -> None:
    """Omitting board_id should return HTTP 422 (FastAPI schema validation)."""
    from app.core.rbac import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()
    try:
        resp = await client.get("/api/telemetry", params={"metric": "voltage_ln"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_telemetry_bucket_minutes_out_of_range(client: AsyncClient) -> None:
    """bucket_minutes=0 and bucket_minutes=61 should both return 422."""
    from app.core.rbac import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()
    try:
        for bad_bucket in (0, 61):
            resp = await client.get(
                "/api/telemetry",
                params={
                    "board_id": str(_BOARD_UUID),
                    "metric": "voltage_ln",
                    "bucket_minutes": bad_bucket,
                },
            )
            assert resp.status_code == 422, f"Expected 422 for bucket_minutes={bad_bucket}"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── Board not found ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetry_board_not_found_returns_404(client: AsyncClient) -> None:
    """A board_id that does not exist in the DB should return 404."""
    from app.core.rbac import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()
    try:
        with patch("app.routes.telemetry.select") as mock_select:
            # Make db.execute return a result with no rows
            mock_result = MagicMock()
            mock_result.one_or_none.return_value = None

            # We patch the db dependency to return a mock session
            mock_db = AsyncMock()
            mock_db.execute.return_value = mock_result

            from app.db.engine import get_db
            app.dependency_overrides[get_db] = lambda: mock_db

            resp = await client.get(
                "/api/telemetry",
                params={"board_id": str(uuid.uuid4()), "metric": "voltage_ln"},
            )
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)  # type: ignore[arg-type]


# ── Successful response shape ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetry_returns_correct_shape(client: AsyncClient) -> None:
    """A valid request should return TelemetryResponse with the right structure."""
    from app.core.rbac import get_current_user
    from app.db.engine import get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()

    # Mock DB returning a board row
    mock_board_row = _make_board_row()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_board_row

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db

    # Mock telemetry repo returning two bucketed rows (one per register address)
    bucket_ts = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
    fake_rows = [
        {"bucket": bucket_ts, "register_address": 0x0100, "avg_value": 2310.0},
        {"bucket": bucket_ts, "register_address": 0x0101, "avg_value": 2305.0},
        {"bucket": bucket_ts, "register_address": 0x0102, "avg_value": 2315.0},
    ]
    with patch("app.routes.telemetry.telemetry_repo.query_telemetry", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = fake_rows
        resp = await client.get(
            "/api/telemetry",
            params={
                "board_id": str(_BOARD_UUID),
                "metric": "voltage_ln",
                "bucket_minutes": 1,
            },
        )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)  # type: ignore[arg-type]

    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Top-level fields
    assert data["board_code"] == _BOARD_CODE
    assert data["metric"] == "voltage_ln"
    assert data["unit"] == "V"
    assert data["labels"] == ["L1-N", "L2-N", "L3-N"]

    # Three series (L1-N, L2-N, L3-N)
    assert len(data["series"]) == 3
    l1_series = data["series"][0]
    assert l1_series["label"] == "L1-N"
    assert l1_series["register_addr"] == 0x0100
    assert len(l1_series["data"]) == 1
    # 2310 raw × 0.1 scale = 231.0 V
    assert l1_series["data"][0]["value"] == pytest.approx(231.0, abs=0.01)


@pytest.mark.asyncio
async def test_telemetry_frequency_has_single_series(client: AsyncClient) -> None:
    """Frequency metric has only one register (0x0114) → one series."""
    from app.core.rbac import get_current_user
    from app.db.engine import get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()

    mock_board_row = _make_board_row()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_board_row
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.routes.telemetry.telemetry_repo.query_telemetry", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {
                "bucket": datetime(2026, 4, 17, tzinfo=timezone.utc),
                "register_address": 0x0114,
                "avg_value": 500.0,
            }
        ]
        resp = await client.get(
            "/api/telemetry",
            params={"board_id": str(_BOARD_UUID), "metric": "frequency"},
        )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)  # type: ignore[arg-type]

    assert resp.status_code == 200
    data = resp.json()
    assert data["unit"] == "Hz"
    assert len(data["series"]) == 1
    assert data["series"][0]["label"] == "Freq"
    # 500 × 0.1 = 50.0 Hz
    assert data["series"][0]["data"][0]["value"] == pytest.approx(50.0, abs=0.01)


@pytest.mark.asyncio
async def test_telemetry_empty_range_returns_empty_data(client: AsyncClient) -> None:
    """An empty repo result should give series with empty data lists — not an error."""
    from app.core.rbac import get_current_user
    from app.db.engine import get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()

    mock_board_row = _make_board_row()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_board_row
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.routes.telemetry.telemetry_repo.query_telemetry", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        resp = await client.get(
            "/api/telemetry",
            params={"board_id": str(_BOARD_UUID), "metric": "thd"},
        )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)  # type: ignore[arg-type]

    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "thd"
    assert data["unit"] == "%"
    assert len(data["series"]) == 3
    for s in data["series"]:
        assert s["data"] == []


# ── Valid metric names ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metric",
    ["voltage_ln", "voltage_ll", "current", "frequency", "power_factor", "thd"],
)
async def test_all_valid_metrics_accepted(client: AsyncClient, metric: str) -> None:
    """Each valid metric name should reach the repo (not fail at validation)."""
    from app.core.rbac import get_current_user
    from app.db.engine import get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _make_auth_user()

    mock_board_row = _make_board_row()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_board_row
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.routes.telemetry.telemetry_repo.query_telemetry", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        resp = await client.get(
            "/api/telemetry",
            params={"board_id": str(_BOARD_UUID), "metric": metric},
        )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)  # type: ignore[arg-type]

    assert resp.status_code == 200, f"Expected 200 for metric={metric}, got {resp.status_code}: {resp.text}"
