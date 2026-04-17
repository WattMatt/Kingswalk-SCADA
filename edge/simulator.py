#!/usr/bin/env python3
# edge/simulator.py
"""Kingswalk SCADA — Modbus TCP Simulator

Emulates the 9 main-board Modbus devices for local development and integration
testing. Runs a single Modbus TCP server on a configurable port (default 5020)
with 9 unit IDs (slave IDs 1-9), one per main board.

Register map per slave
----------------------
Holding registers (FC03) only — matches edge/poller.py address constants:

  0x0000–0x000F  Breaker state     4 registers: 0=CLOSED,1=OPEN,2=TRIPPED
  0x0100–0x0105  Voltage L-N/L-L   V_L1-N, V_L2-N, V_L3-N, V_L1-L2, V_L2-L3, V_L3-L1
  0x0110–0x0113  Current           I_L1, I_L2, I_L3, I_N
  0x0114         Frequency         × 10  (495–505 → 49.5–50.5 Hz)
  0x0115–0x0117  Power factor      × 1000 (700–1000 → 0.700–1.000)
  0x0200–0x0202  THD voltage       × 10 (0–79 → 0–7.9%)
  0x0300–0x0303  Energy            kWh_imp, kWh_exp, kVArh_imp, kVArh_exp
  0x0400–0x0401  Counters          trip_count, connection_count

Scale conventions (SPEC §3.2 / ABB M4M 30 assumed):
  Voltage L-N  : register × 0.1 → Volts      (range 2100–2530 → 210–253 V)
  Voltage L-L  : register × 0.1 → Volts      (range 3700–4400 → 370–440 V)
  Current      : register × 0.01 → Amps
  Frequency    : register × 0.1 → Hz
  Power factor : register × 0.001 → dimensionless
  THD          : register × 0.1 → %

Scenarios (–-scenario flag)
---------------------------
  normal       Nominal values, small random drift each cycle (default)
  tripped      Breaker 0 on the selected slave is set to TRIPPED (2)
  open         Breaker 1 on the selected slave is set to OPEN (1)
  pq_high      L1-N voltage drifts above 250 V (upper limit)
  pq_low       L1-N voltage drops below 215 V (lower limit)
  high_thd     THD_V L1 exceeds 8 % threshold

Usage
-----
  python -m edge.simulator                    # all 9 boards on port 5020
  python -m edge.simulator --port 5020 --scenario tripped --slave 1
  python -m edge.simulator --verbose

Scenario control at runtime via HTTP (port = Modbus port + 1000, default 6020):
  POST http://localhost:6020/scenario  body: {"scenario": "tripped", "slave": 1}
  GET  http://localhost:6020/status
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import random
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog
from aiohttp import web
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

log = structlog.get_logger()

# ── Register base addresses (must match edge/poller.py constants) ─────────────

BREAKER_STATE_BASE  = 0x0000
PQ_VOLTAGE_BASE     = 0x0100
PQ_CURRENT_BASE     = 0x0110
PQ_FREQ_REG         = 0x0114
PQ_PF_BASE          = 0x0115
THD_VOLTAGE_BASE    = 0x0200
ENERGY_BASE         = 0x0300
COUNTER_BASE        = 0x0400

_STORE_SIZE = 0x0500  # 1280 registers covers all addresses above


# ── Breaker state codes ───────────────────────────────────────────────────────

class BreakerState(IntEnum):
    CLOSED     = 0
    OPEN       = 1
    TRIPPED    = 2
    COMMS_LOSS = 3


# ── Board definitions ─────────────────────────────────────────────────────────

_BOARDS = [
    {"slave": 1, "code": "MB-1.1", "vlan": 11},
    {"slave": 2, "code": "MB-1.2", "vlan": 12},
    {"slave": 3, "code": "MB-2.1", "vlan": 21},
    {"slave": 4, "code": "MB-2.2", "vlan": 22},
    {"slave": 5, "code": "MB-3.1", "vlan": 31},
    {"slave": 6, "code": "MB-4.1", "vlan": 41},
    {"slave": 7, "code": "MB-5.1", "vlan": 51},
    {"slave": 8, "code": "MB-5.2", "vlan": 52},
    {"slave": 9, "code": "MB-5.3", "vlan": 53},
]


# ── Scenario definitions ──────────────────────────────────────────────────────

SCENARIOS = frozenset({"normal", "tripped", "open", "pq_high", "pq_low", "high_thd"})


@dataclass
class SlaveScenario:
    """Active scenario for one slave device."""
    name: str = "normal"
    target_slave: int = 1


@dataclass
class SimState:
    """Mutable simulation state shared between the drift task and HTTP control."""
    scenario: SlaveScenario = field(default_factory=SlaveScenario)
    running: bool = True

    def set_scenario(self, name: str, slave: int = 1) -> None:
        if name not in SCENARIOS:
            raise ValueError(f"Unknown scenario {name!r}. Valid: {sorted(SCENARIOS)}")
        self.scenario = SlaveScenario(name=name, target_slave=slave)
        log.info("scenario_changed", scenario=name, slave=slave)


# ── Register value generation ─────────────────────────────────────────────────


def _nominal_voltage_ln() -> int:
    """Return a nominal L-N voltage register value with small drift.

    SPEC mock range: 210–253 V → registers 2100–2530.
    Nominal centred on 230 V ± 2 V drift.
    """
    return round(2300 + random.uniform(-20, 20))


def _nominal_voltage_ll() -> int:
    """Return a nominal L-L voltage register value. Nominal 400 V ± 5 V drift."""
    return round(4000 + random.uniform(-50, 50))


def _nominal_current() -> int:
    """Return a plausible current (1–15 A × 100)."""
    return round(random.uniform(100, 1500))


def _nominal_frequency() -> int:
    """Return 50 Hz ± 0.3 Hz × 10."""
    return round(500 + random.uniform(-3, 3))


def _nominal_pf() -> int:
    """Return a power factor in range 0.85–0.97 × 1000."""
    return round(random.uniform(850, 970))


def _nominal_thd() -> int:
    """Return THD < 4 % × 10."""
    return round(random.uniform(15, 39))


def _build_registers(slave: int, state: SimState) -> dict[int, int]:
    """Generate a full register snapshot for one slave.

    Applies the active scenario to the target slave; all other slaves get
    nominal values.
    """
    sc = state.scenario
    is_target = slave == sc.target_slave

    regs: dict[int, int] = {}

    # ── Breaker states ──────────────────────────────────────────────────────
    for i in range(4):
        addr = BREAKER_STATE_BASE + i
        if is_target and sc.name == "tripped" and i == 0:
            regs[addr] = BreakerState.TRIPPED
        elif is_target and sc.name == "open" and i == 1:
            regs[addr] = BreakerState.OPEN
        else:
            regs[addr] = BreakerState.CLOSED

    # ── Voltage L-N (0x0100–0x0102) ────────────────────────────────────────
    for i in range(3):
        addr = PQ_VOLTAGE_BASE + i
        if is_target and sc.name == "pq_high":
            # 252–260 V — above upper limit of 253 V
            regs[addr] = round(2520 + random.uniform(0, 80))
        elif is_target and sc.name == "pq_low":
            # 195–212 V — below lower limit of 210 V
            regs[addr] = round(1950 + random.uniform(0, 170))
        else:
            regs[addr] = _nominal_voltage_ln()

    # ── Voltage L-L (0x0103–0x0105) ────────────────────────────────────────
    for i in range(3):
        regs[PQ_VOLTAGE_BASE + 3 + i] = _nominal_voltage_ll()

    # ── Current (0x0110–0x0113) ─────────────────────────────────────────────
    for i in range(4):
        regs[PQ_CURRENT_BASE + i] = _nominal_current()

    # ── Frequency (0x0114) ──────────────────────────────────────────────────
    regs[PQ_FREQ_REG] = _nominal_frequency()

    # ── Power factor (0x0115–0x0117) ────────────────────────────────────────
    for i in range(3):
        regs[PQ_PF_BASE + i] = _nominal_pf()

    # ── THD voltage (0x0200–0x0202) ─────────────────────────────────────────
    for i in range(3):
        addr = THD_VOLTAGE_BASE + i
        if is_target and sc.name == "high_thd" and i == 0:
            # 8.5–10 % → registers 85–100
            regs[addr] = round(random.uniform(85, 100))
        else:
            regs[addr] = _nominal_thd()

    # ── Energy counters (0x0300–0x0303) — slow increment ────────────────────
    # We keep energy values synthetic but monotonically increasing via slave offset.
    base_energy = slave * 10_000
    regs[ENERGY_BASE]     = base_energy + round(random.uniform(0, 100))
    regs[ENERGY_BASE + 1] = 0  # No export (PV not in scope for R1)
    regs[ENERGY_BASE + 2] = base_energy // 3 + round(random.uniform(0, 30))
    regs[ENERGY_BASE + 3] = 0

    # ── Operational counters (0x0400–0x0401) ────────────────────────────────
    regs[COUNTER_BASE]     = 1 if (is_target and sc.name == "tripped") else 0
    regs[COUNTER_BASE + 1] = slave * 10  # connection_count — static per slave

    return regs


def _apply_registers(
    context: ModbusServerContext,
    slave: int,
    regs: dict[int, int],
) -> None:
    """Write register values into the server data store for one slave."""
    for addr, val in regs.items():
        # setValues(fx, address, values) — fx=3 for holding registers
        context[slave].setValues(3, addr, [val])


# ── Background drift task ─────────────────────────────────────────────────────


async def drift_task(context: ModbusServerContext, state: SimState) -> None:
    """Update register values every second to simulate realistic sensor drift."""
    cycle = 0
    while state.running:
        await asyncio.sleep(1.0)
        for board in _BOARDS:
            slave = board["slave"]
            regs = _build_registers(slave, state)
            _apply_registers(context, slave, regs)
        cycle += 1
        if cycle % 30 == 0:
            sc = state.scenario
            log.debug(
                "sim_drift",
                cycle=cycle,
                scenario=sc.name,
                target_slave=sc.target_slave,
            )


# ── HTTP control server ───────────────────────────────────────────────────────


def _make_control_app(state: SimState) -> web.Application:
    """Build an aiohttp app for runtime scenario control."""
    app = web.Application()

    async def get_status(request: web.Request) -> web.Response:  # noqa: ARG001
        return web.json_response(
            {
                "running": state.running,
                "scenario": state.scenario.name,
                "target_slave": state.scenario.target_slave,
                "boards": _BOARDS,
            }
        )

    async def post_scenario(request: web.Request) -> web.Response:
        try:
            body: dict[str, Any] = await request.json()
            scenario = str(body.get("scenario", "normal"))
            slave = int(body.get("slave", 1))
            state.set_scenario(scenario, slave)
            return web.json_response({"ok": True, "scenario": scenario, "slave": slave})
        except (ValueError, json.JSONDecodeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    app.router.add_get("/status", get_status)
    app.router.add_post("/scenario", post_scenario)
    return app


# ── Server bootstrap ──────────────────────────────────────────────────────────


def _build_server_context() -> ModbusServerContext:
    """Build a ModbusServerContext with one slave per main board, all zeroed."""
    slaves: dict[int, ModbusSlaveContext] = {}
    for board in _BOARDS:
        slave_id = board["slave"]
        hr_block = ModbusSequentialDataBlock(0, [0] * _STORE_SIZE)
        slaves[slave_id] = ModbusSlaveContext(
            hr=hr_block,
            ir=ModbusSequentialDataBlock(0, [0] * _STORE_SIZE),
            co=ModbusSequentialDataBlock(0, [False] * 256),
            di=ModbusSequentialDataBlock(0, [False] * 256),
        )
    return ModbusServerContext(slaves=slaves, single=False)


async def run_simulator(
    host: str = "0.0.0.0",
    port: int = 5020,
    control_port: int | None = None,
    scenario: str = "normal",
    target_slave: int = 1,
) -> None:
    """Start the Modbus TCP simulator and optional HTTP control server.

    Args:
        host: Bind address for the Modbus TCP server.
        port: Modbus TCP port (default 5020 — avoids requiring root for 502).
        control_port: If set, start HTTP control server on this port.
        scenario: Initial scenario name.
        target_slave: Slave ID the initial scenario targets.
    """
    context = _build_server_context()
    state = SimState()
    state.set_scenario(scenario, target_slave)

    # Seed initial register values immediately
    for board in _BOARDS:
        regs = _build_registers(board["slave"], state)
        _apply_registers(context, board["slave"], regs)

    log.info(
        "simulator_starting",
        host=host,
        port=port,
        slaves=len(_BOARDS),
        scenario=scenario,
    )

    tasks: list[asyncio.Task[Any]] = []
    tasks.append(asyncio.create_task(drift_task(context, state), name="sim-drift"))

    if control_port is not None:
        ctl_app = _make_control_app(state)
        runner = web.AppRunner(ctl_app)
        await runner.setup()
        site = web.TCPSite(runner, host, control_port)
        await site.start()
        log.info("control_server_started", port=control_port)

    try:
        await StartAsyncTcpServer(
            context=context,
            address=(host, port),
        )
    finally:
        state.running = False
        for t in tasks:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m edge.simulator",
        description="Kingswalk SCADA — Modbus TCP Simulator",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=5020,
        help="Modbus TCP port (default: 5020, non-privileged alternative to 502)",
    )
    parser.add_argument(
        "--control-port", type=int, default=None,
        help="HTTP control server port (default: disabled). Enables /status and /scenario endpoints.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="normal",
        help="Initial scenario (default: normal)",
    )
    parser.add_argument(
        "--slave", type=int, default=1,
        help="Target slave ID for the selected scenario (1-9, default: 1)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)

    asyncio.run(
        run_simulator(
            host=args.host,
            port=args.port,
            control_port=args.control_port,
            scenario=args.scenario,
            target_slave=args.slave,
        )
    )


if __name__ == "__main__":
    main()
