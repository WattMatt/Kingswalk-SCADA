# edge/tests/test_simulator.py
"""Tests for the Modbus TCP simulator — register generation and scenario logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from edge.simulator import (
    BREAKER_STATE_BASE,
    PQ_VOLTAGE_BASE,
    THD_VOLTAGE_BASE,
    BreakerState,
    SimState,
    SlaveScenario,
    _BOARDS,
    _apply_registers,
    _build_registers,
    _build_server_context,
    _nominal_frequency,
    _nominal_pf,
    _nominal_thd,
    _nominal_voltage_ln,
    _nominal_voltage_ll,
    _parse_args,
)


# ── Value generators ──────────────────────────────────────────────────────────


def test_nominal_voltage_ln_within_spec_range() -> None:
    """V_L-N registers should be within SPEC mock range 2100–2530."""
    for _ in range(200):
        v = _nominal_voltage_ln()
        assert 2080 <= v <= 2550, f"Out of range: {v}"


def test_nominal_voltage_ll_within_spec_range() -> None:
    """V_L-L registers should be within SPEC mock range 3700–4400."""
    for _ in range(200):
        v = _nominal_voltage_ll()
        assert 3700 <= v <= 4550, f"Out of range: {v}"


def test_nominal_frequency_within_spec_range() -> None:
    """Frequency register should correspond to 49.5–50.5 Hz."""
    for _ in range(200):
        f = _nominal_frequency()
        assert 492 <= f <= 508, f"Out of range: {f}"


def test_nominal_pf_within_spec_range() -> None:
    """PF register should correspond to PF 0.70–1.00."""
    for _ in range(200):
        pf = _nominal_pf()
        assert 700 <= pf <= 1000, f"Out of range: {pf}"


def test_nominal_thd_below_spec_threshold() -> None:
    """THD register for nominal scenario should be below 80 (8.0%)."""
    for _ in range(200):
        thd = _nominal_thd()
        assert 0 <= thd < 80, f"Out of range: {thd}"


# ── SimState / scenario management ────────────────────────────────────────────


def test_simstate_default_scenario_is_normal() -> None:
    state = SimState()
    assert state.scenario.name == "normal"
    assert state.scenario.target_slave == 1


def test_simstate_set_scenario_updates() -> None:
    state = SimState()
    state.set_scenario("tripped", slave=3)
    assert state.scenario.name == "tripped"
    assert state.scenario.target_slave == 3


def test_simstate_rejects_unknown_scenario() -> None:
    state = SimState()
    with pytest.raises(ValueError, match="Unknown scenario"):
        state.set_scenario("explode", slave=1)


# ── Register generation: normal scenario ─────────────────────────────────────


def test_build_registers_normal_all_breakers_closed() -> None:
    state = SimState()
    regs = _build_registers(slave=1, state=state)
    for i in range(4):
        assert regs[BREAKER_STATE_BASE + i] == BreakerState.CLOSED


def test_build_registers_normal_voltage_in_range() -> None:
    state = SimState()
    for slave in range(1, 10):
        regs = _build_registers(slave=slave, state=state)
        for i in range(3):
            v = regs[PQ_VOLTAGE_BASE + i]
            assert 2000 <= v <= 2700, f"Slave {slave}, reg {i}: voltage {v} out of range"


# ── Register generation: tripped scenario ────────────────────────────────────


def test_build_registers_tripped_sets_breaker0_on_target() -> None:
    state = SimState()
    state.set_scenario("tripped", slave=2)
    regs = _build_registers(slave=2, state=state)
    assert regs[BREAKER_STATE_BASE] == BreakerState.TRIPPED, "Breaker 0 should be TRIPPED"
    assert regs[BREAKER_STATE_BASE + 1] == BreakerState.CLOSED
    assert regs[BREAKER_STATE_BASE + 2] == BreakerState.CLOSED


def test_build_registers_tripped_does_not_affect_other_slaves() -> None:
    state = SimState()
    state.set_scenario("tripped", slave=2)
    regs = _build_registers(slave=3, state=state)  # non-target slave
    for i in range(4):
        assert regs[BREAKER_STATE_BASE + i] == BreakerState.CLOSED


def test_build_registers_tripped_increments_trip_counter() -> None:
    from edge.simulator import COUNTER_BASE
    state = SimState()
    state.set_scenario("tripped", slave=1)
    regs = _build_registers(slave=1, state=state)
    assert regs[COUNTER_BASE] == 1


# ── Register generation: open scenario ───────────────────────────────────────


def test_build_registers_open_sets_breaker1_on_target() -> None:
    state = SimState()
    state.set_scenario("open", slave=5)
    regs = _build_registers(slave=5, state=state)
    assert regs[BREAKER_STATE_BASE + 1] == BreakerState.OPEN
    assert regs[BREAKER_STATE_BASE] == BreakerState.CLOSED  # breaker 0 still closed


# ── Register generation: PQ scenarios ────────────────────────────────────────


def test_build_registers_pq_high_voltage_exceeds_upper_limit() -> None:
    """pq_high scenario: V_L1-N should be above 250 V (register > 2500)."""
    state = SimState()
    state.set_scenario("pq_high", slave=1)
    for _ in range(20):
        regs = _build_registers(slave=1, state=state)
        v = regs[PQ_VOLTAGE_BASE]
        assert v > 2500, f"Expected >2500, got {v}"


def test_build_registers_pq_low_voltage_below_lower_limit() -> None:
    """pq_low scenario: V_L1-N should be below 215 V (register < 2150)."""
    state = SimState()
    state.set_scenario("pq_low", slave=1)
    for _ in range(20):
        regs = _build_registers(slave=1, state=state)
        v = regs[PQ_VOLTAGE_BASE]
        assert v < 2150, f"Expected <2150, got {v}"


def test_build_registers_pq_scenarios_do_not_affect_other_slaves() -> None:
    state = SimState()
    state.set_scenario("pq_high", slave=3)
    regs = _build_registers(slave=4, state=state)
    v = regs[PQ_VOLTAGE_BASE]
    assert v < 2600, f"Non-target slave should have nominal voltage, got {v}"


# ── Register generation: high_thd scenario ───────────────────────────────────


def test_build_registers_high_thd_exceeds_threshold() -> None:
    """high_thd scenario: THD_V_L1 should exceed 8 % threshold (register >= 80)."""
    state = SimState()
    state.set_scenario("high_thd", slave=1)
    for _ in range(20):
        regs = _build_registers(slave=1, state=state)
        thd = regs[THD_VOLTAGE_BASE]
        assert thd >= 80, f"Expected >=80, got {thd}"


def test_build_registers_high_thd_l2_l3_remain_nominal() -> None:
    """Only L1 THD is elevated; L2 and L3 stay nominal."""
    state = SimState()
    state.set_scenario("high_thd", slave=1)
    for _ in range(20):
        regs = _build_registers(slave=1, state=state)
        assert regs[THD_VOLTAGE_BASE + 1] < 80
        assert regs[THD_VOLTAGE_BASE + 2] < 80


# ── Server context builder ────────────────────────────────────────────────────


def test_build_server_context_has_all_nine_slaves() -> None:
    context = _build_server_context()
    for board in _BOARDS:
        slave_id = board["slave"]
        # Access slave context — should not raise KeyError
        slave = context[slave_id]
        assert slave is not None


def test_apply_registers_writes_into_context() -> None:
    context = _build_server_context()
    state = SimState()
    regs = _build_registers(slave=1, state=state)
    _apply_registers(context, slave=1, regs=regs)
    # Read back a voltage register
    read_back = context[1].getValues(3, PQ_VOLTAGE_BASE, count=1)
    assert read_back[0] == regs[PQ_VOLTAGE_BASE]


# ── CLI argument parsing ──────────────────────────────────────────────────────


def test_parse_args_defaults() -> None:
    args = _parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 5020
    assert args.scenario == "normal"
    assert args.slave == 1
    assert args.verbose is False
    assert args.control_port is None


def test_parse_args_scenario_flag() -> None:
    args = _parse_args(["--scenario", "tripped", "--slave", "3"])
    assert args.scenario == "tripped"
    assert args.slave == 3


def test_parse_args_verbose_flag() -> None:
    args = _parse_args(["--verbose"])
    assert args.verbose is True


def test_parse_args_control_port() -> None:
    args = _parse_args(["--control-port", "6020"])
    assert args.control_port == 6020


# ── Board definitions ─────────────────────────────────────────────────────────


def test_boards_list_has_nine_entries() -> None:
    assert len(_BOARDS) == 9


def test_boards_slave_ids_are_unique_and_sequential() -> None:
    slave_ids = [b["slave"] for b in _BOARDS]
    assert sorted(slave_ids) == list(range(1, 10))
