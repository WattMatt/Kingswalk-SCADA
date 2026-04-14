"""Tests for LocalBuffer — SQLite-backed telemetry sample buffer."""
import pytest
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from edge.buffer import LocalBuffer, RawSample

_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def _sample(device_id: str = "MB_1_1", register_address: int = 0, raw_value: int = 100) -> RawSample:
    return RawSample(
        device_id=device_id,
        register_address=register_address,
        raw_value=raw_value,
        sampled_at=_NOW,
    )


@pytest.fixture
async def buf() -> AsyncGenerator[LocalBuffer, None]:
    b = LocalBuffer(":memory:")
    await b.initialise()
    yield b
    await b.close()


@pytest.mark.asyncio
async def test_initialise_creates_table(buf: LocalBuffer) -> None:
    count = await buf.pending_count()
    assert count == 0


@pytest.mark.asyncio
async def test_add_increases_pending_count(buf: LocalBuffer) -> None:
    await buf.add(_sample())
    assert await buf.pending_count() == 1


@pytest.mark.asyncio
async def test_take_batch_returns_all_pending(buf: LocalBuffer) -> None:
    for i in range(3):
        await buf.add(_sample(device_id=f"MB_{i}", register_address=i, raw_value=i * 10))
    batch = await buf.take_batch(max_rows=10)
    assert len(batch) == 3


@pytest.mark.asyncio
async def test_take_batch_respects_max_rows(buf: LocalBuffer) -> None:
    for i in range(10):
        await buf.add(_sample(raw_value=i))
    batch = await buf.take_batch(max_rows=3)
    assert len(batch) == 3


@pytest.mark.asyncio
async def test_mark_synced_removes_from_pending(buf: LocalBuffer) -> None:
    await buf.add(_sample())
    await buf.add(_sample(device_id="MB_2"))
    batch = await buf.take_batch()
    ids = [row[0] for row in batch]
    await buf.mark_synced(ids[:1])
    assert await buf.pending_count() == 1


@pytest.mark.asyncio
async def test_take_batch_excludes_synced(buf: LocalBuffer) -> None:
    await buf.add(_sample())
    batch = await buf.take_batch()
    await buf.mark_synced([batch[0][0]])
    second_batch = await buf.take_batch()
    assert len(second_batch) == 0


@pytest.mark.asyncio
async def test_sample_roundtrip_preserves_fields(buf: LocalBuffer) -> None:
    s = _sample(device_id="MB_5_3", register_address=0x0300, raw_value=42)
    await buf.add(s)
    batch = await buf.take_batch()
    _, recovered = batch[0]
    assert recovered.device_id == "MB_5_3"
    assert recovered.register_address == 0x0300
    assert recovered.raw_value == 42
    assert recovered.sampled_at == _NOW


@pytest.mark.asyncio
async def test_to_dict_produces_iso_timestamp(buf: LocalBuffer) -> None:
    s = _sample()
    d = s.to_dict()
    assert d["sampled_at"] == "2026-01-15T10:00:00+00:00"
    assert d["device_id"] == "MB_1_1"
    assert d["register_address"] == 0
    assert d["raw_value"] == 100


@pytest.mark.asyncio
async def test_mark_synced_empty_list_is_no_op(buf: LocalBuffer) -> None:
    await buf.add(_sample())
    await buf.mark_synced([])  # must not raise
    assert await buf.pending_count() == 1
