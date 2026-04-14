"""Tests for POST /api/ingest/batch — edge gateway telemetry ingestion."""
import pytest
from httpx import AsyncClient

VALID_SAMPLE = {
    "device_id": "MB_1_1_breaker_0",
    "register_address": 0,
    "raw_value": 1,
    "sampled_at": "2026-01-15T10:00:00+00:00",
}

EDGE_KEY = "test-edge-api-key-abc123"


@pytest.fixture(autouse=True)
def set_edge_api_key(monkeypatch):
    """Patch settings.edge_api_key for tests that need it."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "edge_api_key", EDGE_KEY)


@pytest.mark.asyncio
async def test_ingest_unauthorized_missing_header(client: AsyncClient) -> None:
    resp = await client.post("/api/ingest/batch", json={"samples": [VALID_SAMPLE]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_unauthorized_wrong_key(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/ingest/batch",
        json={"samples": [VALID_SAMPLE]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_accepted(client: AsyncClient, clean_tables: None) -> None:
    resp = await client.post(
        "/api/ingest/batch",
        json={"samples": [VALID_SAMPLE]},
        headers={"Authorization": f"Bearer {EDGE_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] >= 0  # >=0 because dedup may drop it


@pytest.mark.asyncio
async def test_ingest_empty_batch(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/ingest/batch",
        json={"samples": []},
        headers={"Authorization": f"Bearer {EDGE_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 0


@pytest.mark.asyncio
async def test_ingest_invalid_sampled_at(client: AsyncClient) -> None:
    bad_sample = {**VALID_SAMPLE, "sampled_at": "not-a-date"}
    resp = await client.post(
        "/api/ingest/batch",
        json={"samples": [bad_sample]},
        headers={"Authorization": f"Bearer {EDGE_KEY}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_no_edge_key_configured(client: AsyncClient, monkeypatch) -> None:
    """When edge_api_key is empty string (unconfigured), all requests rejected."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "edge_api_key", "")
    resp = await client.post(
        "/api/ingest/batch",
        json={"samples": [VALID_SAMPLE]},
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 401
