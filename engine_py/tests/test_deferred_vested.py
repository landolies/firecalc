"""§11.8 — Deferred vested retirement."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.engine import compute_retirement_scenario
from engine_py.models import PayGrid, ScenarioInputs
from .conftest import make_inputs


def test_deferred_vested_fc_frozen():
    """
    Separate at age 48 (30 years after birth: birth 1975-01-01 → sep 2023-01-01)
    with 15 YOS (hire 2008-01-01). FC_final at separation = $150,000.
    Start pension at age 57 (2032-01-01).
    Benefit % = 15 × 2.4% = 36%.
    Base pension = 150,000 × 36% = 54,000.
    No early reduction (starts at 57).
    FC must NOT grow with GWI during the wait.
    """
    birth = date(1975, 1, 1)
    hire = date(2008, 1, 1)
    separation = date(2023, 1, 1)   # age 48, 15 YOS
    pension_start = date(2032, 1, 1)  # age 57

    # Use a pay grid / GWI that would produce FC_final ≈ $150,000 at separation.
    # FF Step 7 base = 6343.70; GWI-adjusted to 2023-01-01 (fiscal year 2022/23).
    # FY2627 starts 2026-07-01 → to get to 2023-01-01, exponent = -4 FYs.
    # 6343.70 / 1.035^4 ≈ 5572.37 biweekly → 144,882 annual — close but not $150k.
    # For test simplicity, use a custom pay grid that yields exactly $150k annual.
    # $150,000 / 26 = $5769.23 biweekly for top step.
    biweekly_150k = Decimal("5769.23")  # × 26 = 149,999.98 ≈ 150,000
    custom_grid = PayGrid(rates={
        ("Firefighter", 1): biweekly_150k,
        ("Firefighter", 2): biweekly_150k,
        ("Firefighter", 3): biweekly_150k,
        ("Firefighter", 4): biweekly_150k,
        ("Firefighter", 5): biweekly_150k,
        ("Firefighter", 6): biweekly_150k,
        ("Firefighter", 7): biweekly_150k,
    })

    inputs = make_inputs(
        birth_date=birth,
        hire_date=hire,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2014, 1, 1),  # step 7 arrived after 6 years from hire
        pay_grid=custom_grid,
        pay_grid_effective_date=separation,  # grid is as-of separation so no GWI scaling at sep
        gwi_rate=Decimal("0.035"),           # GWI exists but FC must be frozen
        retirement_age=57,
        retirement_type="deferred_vested",
        separation_date=separation,
        pension_start_date=pension_start,
        show_cola=False,
    )

    result = compute_retirement_scenario(inputs)
    assert not result.warnings, f"Unexpected warnings: {result.warnings}"

    # YOS at separation: 2008-01-01 to 2023-01-01 = 15 years
    assert abs(result.yos_at_retirement - Decimal("15")) < Decimal("0.05"), (
        f"YOS: expected ~15, got {result.yos_at_retirement}"
    )

    # Benefit %: 15 × 2.4% = 36%
    assert result.benefit_pct_detail.final_pct == Decimal("0.3600"), (
        f"Benefit %: {result.benefit_pct_detail.final_pct}"
    )

    # No early reduction at pension_start age 57
    assert result.early_reduction.reduction_pct == Decimal("0.0000")

    # Annual pension ≈ 150,000 × 36% = 54,000
    # (FC_final = 5769.23 × 26 = 149,999.98)
    assert abs(result.annual_pension_final - Decimal("54000")) <= Decimal("1.00"), (
        f"Annual pension: expected ~54000, got {result.annual_pension_final}"
    )


def test_deferred_vested_fc_does_not_grow_with_gwi():
    """
    Verify that FC is computed from the timeline up to separation only —
    GWI applied after separation must not affect FC.
    We check by comparing a deferred vested scenario against an active one:
    the active retiree at the same age should have a higher FC due to GWI growth.
    """
    birth = date(1975, 1, 1)
    hire = date(2010, 1, 1)
    separation = date(2023, 1, 1)   # age 48
    pension_start = date(2032, 1, 1)

    dv_inputs = make_inputs(
        birth_date=birth,
        hire_date=hire,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2016, 1, 1),
        gwi_rate=Decimal("0.035"),
        retirement_age=57,
        retirement_type="deferred_vested",
        separation_date=separation,
        pension_start_date=pension_start,
    )
    active_inputs = make_inputs(
        birth_date=birth,
        hire_date=hire,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2016, 1, 1),
        gwi_rate=Decimal("0.035"),
        retirement_age=57,
        retirement_type="active",
    )

    dv = compute_retirement_scenario(dv_inputs)
    active = compute_retirement_scenario(active_inputs)

    # Deferred vested FC (frozen at 2023) must be less than active FC (grows to 2032)
    assert dv.fc_final.annual_fc < active.fc_final.annual_fc, (
        "Deferred vested FC should be less than active FC due to GWI freeze"
    )
