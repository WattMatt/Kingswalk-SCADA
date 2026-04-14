"""Tests for ReadOnlyModbusClient — verifies FC06/FC16 write protection."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edge.modbus_client import ReadOnlyModbusClient


def test_write_register_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="write operation 'write_register' is forbidden"):
        _ = client.write_register  # attribute access raises — no call needed


def test_write_registers_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="forbidden"):
        _ = client.write_registers


def test_write_coil_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="forbidden"):
        _ = client.write_coil


def test_write_coils_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="forbidden"):
        _ = client.write_coils


def test_readwrite_registers_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="forbidden"):
        _ = client.readwrite_registers


def test_mask_write_register_raises() -> None:
    client = ReadOnlyModbusClient("localhost")
    with pytest.raises(RuntimeError, match="forbidden"):
        _ = client.mask_write_register


@pytest.mark.asyncio
async def test_read_holding_registers_allowed() -> None:
    """FC03 must be allowed."""
    with patch("edge.modbus_client.AsyncModbusTcpClient") as mock_class:
        mock_inner = AsyncMock()
        mock_class.return_value = mock_inner
        mock_inner.read_holding_registers = AsyncMock(
            return_value=MagicMock(registers=[100, 200])
        )
        client = ReadOnlyModbusClient("localhost")
        result = await client.read_holding_registers(address=0, count=2)
        assert result.registers == [100, 200]
        mock_inner.read_holding_registers.assert_called_once_with(0, 2, slave=1)


@pytest.mark.asyncio
async def test_read_input_registers_allowed() -> None:
    """FC04 must be allowed."""
    with patch("edge.modbus_client.AsyncModbusTcpClient") as mock_class:
        mock_inner = AsyncMock()
        mock_class.return_value = mock_inner
        mock_inner.read_input_registers = AsyncMock(
            return_value=MagicMock(registers=[300])
        )
        client = ReadOnlyModbusClient("localhost")
        result = await client.read_input_registers(address=10, count=1)
        assert result.registers == [300]
        mock_inner.read_input_registers.assert_called_once_with(10, 1, slave=1)


def test_timeout_configured() -> None:
    """Client must be created with 500ms timeout."""
    with patch("edge.modbus_client.AsyncModbusTcpClient") as mock_class:
        ReadOnlyModbusClient("192.168.1.1", port=502)
        mock_class.assert_called_once_with("192.168.1.1", port=502, timeout=0.5)
