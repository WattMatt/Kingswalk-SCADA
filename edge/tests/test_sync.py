"""Tests for CloudSync — batch HTTP POST of SQLite buffer to cloud ingest API."""
import pytest
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from edge.buffer import LocalBuffer, RawSample
from edge.sync import CloudSync

_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def buf() -> AsyncGenerator[LocalBuffer, None]:
    b = LocalBuffer(":memory:")
    await b.initialise()
    yield b
    await b.close()


def _sample(device_id: str = "MB_1_1", raw_value: int = 100) -> RawSample:
    return RawSample(
        device_id=device_id,
        register_address=0,
        raw_value=raw_value,
        sampled_at=_NOW,
    )


@pytest.mark.asyncio
async def test_flush_posts_samples_to_cloud(buf: LocalBuffer) -> None:
    for i in range(3):
        await buf.add(_sample(raw_value=i))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    syncer = CloudSync(buf, cloud_url="https://cloud.example.com", edge_token="tok")
    await syncer._flush_one_batch(mock_client)

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer tok"
    payload = call_kwargs.kwargs["json"]
    assert len(payload["samples"]) == 3


@pytest.mark.asyncio
async def test_flush_marks_rows_synced(buf: LocalBuffer) -> None:
    await buf.add(_sample())
    await buf.add(_sample(device_id="MB_2"))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    syncer = CloudSync(buf, cloud_url="https://cloud.example.com", edge_token="tok")
    await syncer._flush_one_batch(mock_client)

    assert await buf.pending_count() == 0


@pytest.mark.asyncio
async def test_flush_respects_batch_size(buf: LocalBuffer) -> None:
    for i in range(600):
        await buf.add(_sample(raw_value=i))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    syncer = CloudSync(buf, cloud_url="https://cloud.example.com", edge_token="tok")
    await syncer._flush_one_batch(mock_client)

    payload = mock_client.post.call_args.kwargs["json"]
    assert len(payload["samples"]) == 500
    assert await buf.pending_count() == 100  # remaining 100 not yet synced


@pytest.mark.asyncio
async def test_flush_does_not_mark_synced_on_http_error(buf: LocalBuffer) -> None:
    await buf.add(_sample())

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    syncer = CloudSync(buf, cloud_url="https://cloud.example.com", edge_token="tok")
    with pytest.raises(httpx.HTTPStatusError):
        await syncer._flush_one_batch(mock_client)

    assert await buf.pending_count() == 1  # not marked synced


@pytest.mark.asyncio
async def test_flush_no_op_when_buffer_empty(buf: LocalBuffer) -> None:
    mock_client = AsyncMock()
    syncer = CloudSync(buf, cloud_url="https://cloud.example.com", edge_token="tok")
    await syncer._flush_one_batch(mock_client)
    mock_client.post.assert_not_called()


def test_cloud_url_normalised() -> None:
    """Trailing slash on cloud_url must not produce double-slash in endpoint."""
    buf = LocalBuffer(":memory:")
    syncer = CloudSync(buf, cloud_url="https://cloud.example.com/", edge_token="tok")
    assert syncer._endpoint == "https://cloud.example.com/api/ingest/batch"
