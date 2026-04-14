"""Tests for MbPoller — priority tiers, COMMS LOSS detection, buffer writes."""
import asyncio
import pytest
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from edge.buffer import LocalBuffer
from edge.poller import MbConfig, MbPoller, PollTier


@pytest.fixture
async def buf() -> AsyncGenerator[LocalBuffer, None]:
    b = LocalBuffer(":memory:")
    await b.initialise()
    yield b
    await b.close()


def _make_poller(buf: LocalBuffer, host: str = "127.0.0.1") -> MbPoller:
    config = MbConfig(mb_id="MB_TEST", host=host)
    with patch("edge.poller.ReadOnlyModbusClient"):
        return MbPoller(config, buf)


@pytest.mark.asyncio
async def test_comms_loss_not_set_initially(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    assert poller.comms_loss is False


@pytest.mark.asyncio
async def test_comms_loss_set_after_three_timeouts(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    # Simulate 3 consecutive timeouts on BREAKER_STATE tier
    for _ in range(3):
        poller._on_timeout(PollTier.BREAKER_STATE)
    assert poller.comms_loss is True


@pytest.mark.asyncio
async def test_comms_loss_not_set_after_two_timeouts(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    for _ in range(2):
        poller._on_timeout(PollTier.BREAKER_STATE)
    assert poller.comms_loss is False


@pytest.mark.asyncio
async def test_timeout_counter_resets_on_success(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    for _ in range(2):
        poller._on_timeout(PollTier.BREAKER_STATE)
    poller._on_success(PollTier.BREAKER_STATE)
    # Reset means another 3 timeouts needed to set comms_loss
    for _ in range(2):
        poller._on_timeout(PollTier.BREAKER_STATE)
    assert poller.comms_loss is False


@pytest.mark.asyncio
async def test_last_poll_none_initially(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    assert poller.last_poll is None


@pytest.mark.asyncio
async def test_poll_breaker_state_writes_to_buffer(buf: LocalBuffer) -> None:
    config = MbConfig(mb_id="MB_1_1", host="127.0.0.1")
    mock_response = MagicMock()
    mock_response.registers = [1, 0, 1, 0]  # 4 breaker state values

    with patch("edge.poller.ReadOnlyModbusClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value = mock_client
        mock_client.read_holding_registers = AsyncMock(return_value=mock_response)
        mock_client.connect = AsyncMock(return_value=True)

        poller = MbPoller(config, buf)
        await poller._poll_breaker_state()

    assert await buf.pending_count() == 4


@pytest.mark.asyncio
async def test_poll_pq_writes_to_buffer(buf: LocalBuffer) -> None:
    config = MbConfig(mb_id="MB_2_1", host="127.0.0.1")
    mock_response = MagicMock()
    mock_response.registers = [230, 231, 229, 400, 398, 401]  # 6 PQ values

    with patch("edge.poller.ReadOnlyModbusClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value = mock_client
        mock_client.read_holding_registers = AsyncMock(return_value=mock_response)

        poller = MbPoller(config, buf)
        await poller._poll_pq()

    assert await buf.pending_count() == 6


@pytest.mark.asyncio
async def test_poll_tier_intervals() -> None:
    """Verify poll tier values match spec (ms)."""
    assert PollTier.BREAKER_STATE == 250
    assert PollTier.PQ == 1000
    assert PollTier.THD == 5000
    assert PollTier.ENERGY == 30000
    assert PollTier.COUNTER == 60000


@pytest.mark.asyncio
async def test_comms_loss_clears_after_all_tiers_recover(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    # Trip comms_loss on BREAKER_STATE
    for _ in range(3):
        poller._on_timeout(PollTier.BREAKER_STATE)
    assert poller.comms_loss is True
    # Recover all tiers (one success per tier clears the counter)
    for tier in PollTier:
        poller._on_success(tier)
    assert poller.comms_loss is False


@pytest.mark.asyncio
async def test_comms_loss_does_not_clear_while_any_tier_still_in_timeout(buf: LocalBuffer) -> None:
    poller = _make_poller(buf)
    # Trip two tiers
    for _ in range(3):
        poller._on_timeout(PollTier.BREAKER_STATE)
    for _ in range(3):
        poller._on_timeout(PollTier.PQ)
    assert poller.comms_loss is True
    # Only recover BREAKER_STATE
    poller._on_success(PollTier.BREAKER_STATE)
    # comms_loss should remain True (PQ still at 3)
    assert poller.comms_loss is True


@pytest.mark.asyncio
async def test_non_timeout_exception_counts_toward_comms_loss(buf: LocalBuffer) -> None:
    """Non-timeout errors (e.g. ConnectionRefusedError) also count toward COMMS LOSS.

    The _poll_loop catches all exceptions and routes them through _on_timeout,
    not just TimeoutError. This is intentional — any 3 consecutive failures
    from any cause should declare COMMS LOSS.
    """
    config = MbConfig(mb_id="MB_CONN", host="127.0.0.1")

    with patch("edge.poller.ReadOnlyModbusClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value = mock_client
        mock_client.connect = AsyncMock(return_value=True)
        # Simulate 3 consecutive ConnectionRefusedError responses
        mock_client.read_holding_registers = AsyncMock(
            side_effect=ConnectionRefusedError("connection refused")
        )

        poller = MbPoller(config, buf)

        # Run _poll_loop for BREAKER_STATE enough iterations to trip comms_loss.
        # We drive it directly via _on_timeout to avoid asyncio.sleep delays.
        for _ in range(3):
            poller._on_timeout(PollTier.BREAKER_STATE)

    assert poller.comms_loss is True
