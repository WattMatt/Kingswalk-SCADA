# edge/poller.py
"""MbPoller — polls one main board across 5 priority tiers via ReadOnlyModbusClient."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Awaitable, Callable

import structlog

from edge.buffer import LocalBuffer, RawSample
from edge.modbus_client import ReadOnlyModbusClient

log = structlog.get_logger()

_TIMEOUT_LIMIT = 3  # consecutive timeouts per tier before COMMS LOSS is declared


class PollTier(IntEnum):
    """Poll interval in milliseconds per spec priority order."""

    BREAKER_STATE = 250    # breaker open/closed/tripped — highest priority
    PQ            = 1000   # voltage, current, power factor, frequency
    THD           = 5000   # total harmonic distortion
    ENERGY        = 30000  # kWh / kVArh registers
    COUNTER       = 60000  # operational counters


@dataclass
class MbConfig:
    mb_id: str    # e.g. "MB_1_1" — used as device_id prefix in telemetry
    host: str     # Modbus TCP host (IP on VLAN)
    port: int = 502
    slave: int = 1  # Modbus unit ID


# ─── Register base addresses ───────────────────────────────────────────────────
# ALL addresses are assumed from ABB datasheets.
# TODO: VERIFY_REGISTER — address assumed from ABB datasheet
BREAKER_STATE_BASE = 0x0000  # TODO: VERIFY_REGISTER — 4 registers per breaker group
PQ_VOLTAGE_BASE    = 0x0100  # TODO: VERIFY_REGISTER — V_L1-N, V_L2-N, V_L3-N, V_L1-L2, V_L2-L3, V_L3-L1
PQ_CURRENT_BASE    = 0x0110  # TODO: VERIFY_REGISTER — I_L1, I_L2, I_L3, I_N
THD_VOLTAGE_BASE   = 0x0200  # TODO: VERIFY_REGISTER — THD_V L1, L2, L3
ENERGY_BASE        = 0x0300  # TODO: VERIFY_REGISTER — kWh_imp, kWh_exp, kVArh_imp, kVArh_exp
COUNTER_BASE       = 0x0400  # TODO: VERIFY_REGISTER — operational counters


class MbPoller:
    """Polls one main board (one VLAN) across all 5 priority tiers.

    Each tier runs in its own asyncio task. Samples are written to `LocalBuffer`
    for CloudSync to drain.
    """

    def __init__(self, config: MbConfig, buffer: LocalBuffer) -> None:
        self._config = config
        self._buffer = buffer
        self._client = ReadOnlyModbusClient(config.host, config.port)
        self._consecutive_timeouts: dict[PollTier, int] = {t: 0 for t in PollTier}
        self._comms_loss: bool = False
        self._last_poll: datetime | None = None

    # ─── Public state ──────────────────────────────────────────────────────────

    @property
    def last_poll(self) -> datetime | None:
        return self._last_poll

    @property
    def comms_loss(self) -> bool:
        return self._comms_loss

    @property
    def mb_id(self) -> str:
        return self._config.mb_id

    # ─── Timeout tracking (called by _poll_loop, exposed for unit tests) ───────

    def _on_timeout(self, tier: PollTier) -> None:
        self._consecutive_timeouts[tier] += 1
        if self._consecutive_timeouts[tier] >= _TIMEOUT_LIMIT:
            if not self._comms_loss:
                log.error("comms_loss", mb=self._config.mb_id, tier=tier.name)
            self._comms_loss = True

    def _on_success(self, tier: PollTier) -> None:
        self._consecutive_timeouts[tier] = 0
        self._last_poll = datetime.now(timezone.utc)
        # Clear comms_loss once ALL tiers have successfully polled at least once
        # since the last timeout cascade.
        if self._comms_loss and all(v == 0 for v in self._consecutive_timeouts.values()):
            log.info("comms_restored", mb=self._config.mb_id)
            self._comms_loss = False

    # ─── Entry point ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Connect and start all 5 polling tiers concurrently."""
        await self._client.connect()
        log.info("poller_started", mb=self._config.mb_id)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._poll_loop(PollTier.BREAKER_STATE, self._poll_breaker_state))
            tg.create_task(self._poll_loop(PollTier.PQ,            self._poll_pq))
            tg.create_task(self._poll_loop(PollTier.THD,           self._poll_thd))
            tg.create_task(self._poll_loop(PollTier.ENERGY,        self._poll_energy))
            tg.create_task(self._poll_loop(PollTier.COUNTER,       self._poll_counter))

    async def _poll_loop(
        self,
        tier: PollTier,
        fn: Callable[[], Awaitable[None]],
    ) -> None:
        interval_s = tier.value / 1000.0
        while True:
            try:
                await fn()
                self._on_success(tier)
            except TimeoutError:
                self._on_timeout(tier)
                log.warning("poll_timeout", mb=self._config.mb_id, tier=tier.name)
            except Exception:
                self._on_timeout(tier)
                log.exception("poll_error", mb=self._config.mb_id, tier=tier.name)
            await asyncio.sleep(interval_s)

    # ─── Per-tier poll functions ───────────────────────────────────────────────

    async def _poll_breaker_state(self) -> None:
        result = await self._client.read_holding_registers(
            BREAKER_STATE_BASE,
            count=4,  # TODO: VERIFY_REGISTER — count depends on breaker count per MB
            slave=self._config.slave,
        )
        now = datetime.now(timezone.utc)
        for i, val in enumerate(result.registers):
            await self._buffer.add(
                RawSample(
                    device_id=f"{self._config.mb_id}_breaker_{i}",
                    register_address=BREAKER_STATE_BASE + i,
                    raw_value=val,
                    sampled_at=now,
                )
            )

    async def _poll_pq(self) -> None:
        result = await self._client.read_holding_registers(
            PQ_VOLTAGE_BASE,
            count=6,  # TODO: VERIFY_REGISTER — V_L1-N, V_L2-N, V_L3-N, V_L1-L2, V_L2-L3, V_L3-L1
            slave=self._config.slave,
        )
        now = datetime.now(timezone.utc)
        for i, val in enumerate(result.registers):
            await self._buffer.add(
                RawSample(
                    device_id=f"{self._config.mb_id}_pq",
                    register_address=PQ_VOLTAGE_BASE + i,
                    raw_value=val,
                    sampled_at=now,
                )
            )

    async def _poll_thd(self) -> None:
        result = await self._client.read_holding_registers(
            THD_VOLTAGE_BASE,
            count=3,  # TODO: VERIFY_REGISTER — THD_V L1, L2, L3
            slave=self._config.slave,
        )
        now = datetime.now(timezone.utc)
        for i, val in enumerate(result.registers):
            await self._buffer.add(
                RawSample(
                    device_id=f"{self._config.mb_id}_thd",
                    register_address=THD_VOLTAGE_BASE + i,
                    raw_value=val,
                    sampled_at=now,
                )
            )

    async def _poll_energy(self) -> None:
        result = await self._client.read_holding_registers(
            ENERGY_BASE,
            count=4,  # TODO: VERIFY_REGISTER — kWh_imp, kWh_exp, kVArh_imp, kVArh_exp
            slave=self._config.slave,
        )
        now = datetime.now(timezone.utc)
        for i, val in enumerate(result.registers):
            await self._buffer.add(
                RawSample(
                    device_id=f"{self._config.mb_id}_energy",
                    register_address=ENERGY_BASE + i,
                    raw_value=val,
                    sampled_at=now,
                )
            )

    async def _poll_counter(self) -> None:
        result = await self._client.read_holding_registers(
            COUNTER_BASE,
            count=2,  # TODO: VERIFY_REGISTER — operational counters
            slave=self._config.slave,
        )
        now = datetime.now(timezone.utc)
        for i, val in enumerate(result.registers):
            await self._buffer.add(
                RawSample(
                    device_id=f"{self._config.mb_id}_counter",
                    register_address=COUNTER_BASE + i,
                    raw_value=val,
                    sampled_at=now,
                )
            )
