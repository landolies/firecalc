"""§11.1 — Vesting and trivial cases."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.engine import compute_retirement_scenario
from engine_py.pension import compute_benefit_pct, compute_yos
from .conftest import make_inputs


def test_vested_minimum_5yos():
    """Hire 1/1/2020, retire at 57 on 1/1/2025 (exactly 5 YOS)."""
    inputs = make_inputs(
        birth_date=date(1968, 1, 1),   # turns 57 on 1/1/2025
        hire_date=date(2020, 1, 1),
        retirement_age=57,
        current_rank="Firefighter",
        current_step=1,
        current_step_arrival_date=date(2020, 1, 1),
        gwi_rate=Decimal("0"),          # simplify: no raises
        show_cola=False,
    )
    result = compute_retirement_scenario(inputs)
    assert not result.warnings, f"Unexpected warnings: {result.warnings}"
    assert result.benefit_pct_detail.final_pct == Decimal("0.1200"), (
        f"Expected 12.0%, got {result.benefit_pct_detail.final_pct}"
    )
    assert not result.benefit_pct_detail.capped
    assert result.early_reduction.reduction_pct == Decimal("0.0000")


def test_80pct_cap_at_30yos():
    """30 YOS retirement at 57+ should give exactly 80%."""
    inputs = make_inputs(
        birth_date=date(1966, 1, 1),   # turns 57 on 1/1/2023, 30 YOS from 1/1/1993
        hire_date=date(1993, 1, 1),
        retirement_age=57,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(1999, 1, 1),
        gwi_rate=Decimal("0"),
        show_cola=False,
    )
    result = compute_retirement_scenario(inputs)
    assert not result.warnings
    assert result.benefit_pct_detail.capped
    assert result.benefit_pct_detail.final_pct == Decimal("0.8000"), (
        f"Expected 80.0%, got {result.benefit_pct_detail.final_pct}"
    )


def test_below_minimum_age_warning():
    """Retire at 49 → warning, no pension figure."""
    inputs = make_inputs(
        birth_date=date(1990, 1, 1),
        hire_date=date(2010, 1, 1),
        retirement_age=49,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2017, 1, 1),
        gwi_rate=Decimal("0"),
    )
    result = compute_retirement_scenario(inputs)
    assert any("minimum age" in w.lower() or "below" in w.lower() for w in result.warnings), (
        f"Expected age warning, got: {result.warnings}"
    )
    assert result.annual_pension_3yr == Decimal("0")


def test_not_vested_4yos():
    """Retire at 57 with 4 YOS → not vested warning, no pension."""
    inputs = make_inputs(
        birth_date=date(1966, 1, 1),
        hire_date=date(2019, 1, 1),
        retirement_age=57,
        current_rank="Firefighter",
        current_step=4,
        current_step_arrival_date=date(2022, 1, 1),
        gwi_rate=Decimal("0"),
    )
    # Retirement date = 1/1/2023, hire = 1/1/2019 → 4 YOS
    result = compute_retirement_scenario(inputs)
    assert any("not vested" in w.lower() or "vesting" in w.lower() for w in result.warnings), (
        f"Expected vesting warning, got: {result.warnings}"
    )
    assert result.annual_pension_3yr == Decimal("0")
