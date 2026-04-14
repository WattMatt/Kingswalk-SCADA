# edge/modbus_client.py
"""ReadOnlyModbusClient — FC03/FC04 only. Raises RuntimeError on any write attempt."""
from __future__ import annotations

from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.pdu import ModbusPDU as ModbusResponse

# Every Modbus write function code / helper method that must be blocked.
_WRITE_METHODS: frozenset[str] = frozenset(
    {
        "write_register",        # FC06
        "write_registers",       # FC16
        "write_coil",            # FC05
        "write_coils",           # FC15
        "write_file_record",     # FC21
        "readwrite_registers",   # FC23
        "mask_write_register",   # FC22
    }
)


class ReadOnlyModbusClient:
    """Wraps AsyncModbusTcpClient exposing only FC03/FC04 read methods.

    Any attempt to access a write method raises RuntimeError immediately —
    even attribute access, before any call is made.

    This is a safety-critical constraint: the system is monitoring-only and
    must never send control commands to field devices.
    """

    def __init__(self, host: str, port: int = 502, timeout: float = 0.5) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        # Always set __client before the try so __getattr__ never recurses if
        # an unexpected exception (OSError, ImportError, etc.) fires mid-__init__.
        self.__client: AsyncModbusTcpClient | None = None
        # Attempt eager construction. pymodbus >= 3.7 calls asyncio.get_running_loop()
        # in __init__, which fails outside an event loop. In that case we defer to
        # first use inside an async context. Under test patches the mock constructor
        # succeeds synchronously.
        try:
            self.__client = AsyncModbusTcpClient(host, port=port, timeout=timeout)
        except RuntimeError:
            pass  # No running event loop — defer construction until we are inside one.

    def _get_client(self) -> AsyncModbusTcpClient:
        if self.__client is None:
            self.__client = AsyncModbusTcpClient(
                self._host, port=self._port, timeout=self._timeout
            )
        return self.__client

    def __getattr__(self, name: str) -> Any:
        if name in _WRITE_METHODS:
            raise RuntimeError(
                f"ReadOnlyModbusClient: write operation '{name}' is forbidden. "
                "This system is monitoring-only. FC06/FC16 are never permitted."
            )
        return getattr(self._get_client(), name)

    async def read_holding_registers(
        self, address: int, count: int = 1, slave: int = 1
    ) -> ModbusResponse:
        """FC03 — read holding registers."""
        return await self._get_client().read_holding_registers(address, count, slave=slave)

    async def read_input_registers(
        self, address: int, count: int = 1, slave: int = 1
    ) -> ModbusResponse:
        """FC04 — read input registers."""
        return await self._get_client().read_input_registers(address, count, slave=slave)

    async def connect(self) -> bool:
        return await self._get_client().connect()

    def close(self) -> None:
        self._get_client().close()

    @property
    def connected(self) -> bool:
        return self._get_client().connected
