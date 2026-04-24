"""§11.2 — Early retirement reduction cases."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.pension import compute_benefit_pct, compute_early_reduction


def test_reduction_age_54():
    """Retire at 54: 3 years before 57, 21% reduction."""
    r = compute_early_reduction(54)
    assert r.years_before_57 == 3
    assert r.reduction_pct == Decimal("0.2100")
    assert r.factor == Decimal("0.7900")


def test_reduction_age_50():
    """Retire at 50: 7 years before 57, 49% reduction."""
    r = compute_early_reduction(50)
    assert r.years_before_57 == 7
    assert r.reduction_pct == Decimal("0.4900")
    assert r.factor == Decimal("0.5100")


def test_no_reduction_at_57():
    r = compute_early_reduction(57)
    assert r.years_before_57 == 0
    assert r.reduction_pct == Decimal("0.0000")
    assert r.factor == Decimal("1.0000")


def test_no_reduction_above_57():
    r = compute_early_reduction(60)
    assert r.years_before_57 == 0
    assert r.reduction_pct == Decimal("0.0000")
    assert r.factor == Decimal("1.0000")


def test_full_case_age54_yos20_fc160k():
    """§11.2: Retire at 54, YOS 20, FC $160,000."""
    pct = compute_benefit_pct(Decimal("20")).final_pct    # 48%
    red = compute_early_reduction(54)                      # factor 0.79
    fc = Decimal("160000")
    pension = fc * pct * red.factor
    assert pension == Decimal("60672.00"), f"Got {pension}"


def test_full_case_age50_yos20():
    """§11.2: Retire at 50, YOS 20, 49% reduction."""
    pct = compute_benefit_pct(Decimal("20")).final_pct    # 48%
    red = compute_early_reduction(50)                      # factor 0.51
    fc = Decimal("160000")
    pension = fc * pct * red.factor
    # 160000 × 0.48 × 0.51 = 39,321.60... let's verify
    assert pension == Decimal("160000") * Decimal("0.4800") * Decimal("0.5100")
