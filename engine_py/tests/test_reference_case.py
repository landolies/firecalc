"""§11.9 — Reference case: the spec author."""
from datetime import date
from decimal import Decimal

from engine_py.engine import compute_retirement_scenario
from engine_py.pension import compute_yos
from .conftest import make_inputs


# Spec author profile
BIRTH = date(1986, 10, 1)
HIRE = date(2019, 3, 24)
RETIRE_AGE = 57
RETIRE_DATE = date(2043, 10, 1)  # 57th birthday


def test_yos_at_retirement():
    """
    3/24/2019 → 10/1/2043.
    Exact YOS by day-count: (end - start).days / 365.25
    Spec says 24.52 YOS; verify within 0.01.
    """
    yos = compute_yos(HIRE, RETIRE_DATE)
    assert abs(yos - Decimal("24.52")) <= Decimal("0.01"), (
        f"Expected ~24.52 YOS, got {yos}"
    )


def test_benefit_pct():
    """
    YOS ≈ 24.52:
    20 × 2.4% = 48%
    4.52 × 3.0% = 13.56%
    Total ≈ 61.56%
    """
    from engine_py.pension import compute_benefit_pct
    yos = compute_yos(HIRE, RETIRE_DATE)
    detail = compute_benefit_pct(yos)
    expected = Decimal("0.6156")
    assert abs(detail.final_pct - expected) <= Decimal("0.001"), (
        f"Expected ~61.56%, got {detail.final_pct}"
    )
    assert not detail.capped


def test_no_early_reduction_at_57():
    from engine_py.pension import compute_early_reduction
    r = compute_early_reduction(57)
    assert r.factor == Decimal("1.0000")


def test_full_scenario_no_promotions_gwi35():
    """Full end-to-end: spec author, no promotions, GWI=3.5%."""
    inputs = make_inputs(
        birth_date=BIRTH,
        hire_date=HIRE,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2025, 3, 24),
        gwi_rate=Decimal("0.035"),
        retirement_age=RETIRE_AGE,
        promotions=[],
        show_cola=False,
    )
    result = compute_retirement_scenario(inputs)
    assert not result.warnings, f"Unexpected warnings: {result.warnings}"

    # YOS check
    assert abs(result.yos_at_retirement - Decimal("24.52")) <= Decimal("0.01")

    # Benefit % check
    assert abs(result.benefit_pct_detail.final_pct - Decimal("0.6156")) <= Decimal("0.001")

    # No early reduction
    assert result.early_reduction.years_before_57 == 0

    # FC_final should be positive (exact value depends on GWI compounding to 2043)
    assert result.fc_final.annual_fc > Decimal("200000"), (
        f"Expected FC_final > $200k with 17 years of 3.5% GWI, got {result.fc_final.annual_fc}"
    )

    # FC_3yr_avg should be ≤ FC_final (final years are highest with consistent GWI)
    assert result.fc_3yr.annual_fc <= result.fc_final.annual_fc

    # Monthly pension should be reasonable (sanity check $5,000–$15,000/mo range)
    assert Decimal("5000") < result.monthly_pension_3yr < Decimal("15000"), (
        f"Monthly pension out of range: {result.monthly_pension_3yr}"
    )
