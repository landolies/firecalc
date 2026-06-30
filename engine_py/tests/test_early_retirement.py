"""§11.2 — Early retirement reduction cases (monthly proration)."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.pension import compute_benefit_pct, compute_early_reduction

# Canonical birth date for unit tests: Jan 1 1970.
# Nth birthday = date(1970+N, 1, 1), so months_before_57 = (57-N)*12 exactly.
_BIRTH = date(1970, 1, 1)


def _at_age(n):
    """pension_start = Nth birthday of someone born on _BIRTH."""
    return date(1970 + n, 1, 1)


def test_reduction_age_54():
    """Retire at 54: 36 months before 57 → 36/12 × 7% = 21% reduction."""
    r = compute_early_reduction(_at_age(54), _BIRTH)
    assert r.months_before_57 == 36
    assert r.reduction_pct == Decimal("0.2100")
    assert r.factor == Decimal("0.7900")


def test_reduction_age_50():
    """Retire at 50: 84 months before 57 → 84/12 × 7% = 49% reduction."""
    r = compute_early_reduction(_at_age(50), _BIRTH)
    assert r.months_before_57 == 84
    assert r.reduction_pct == Decimal("0.4900")
    assert r.factor == Decimal("0.5100")


def test_no_reduction_at_57():
    r = compute_early_reduction(_at_age(57), _BIRTH)
    assert r.months_before_57 == 0
    assert r.reduction_pct == Decimal("0.0000")
    assert r.factor == Decimal("1.0000")


def test_no_reduction_above_57():
    r = compute_early_reduction(_at_age(60), _BIRTH)
    assert r.months_before_57 == 0
    assert r.reduction_pct == Decimal("0.0000")
    assert r.factor == Decimal("1.0000")


def test_monthly_proration_mid_year():
    """Retire 6 months before 57th birthday → 6 months → 6/12 × 7% = 3.5% reduction."""
    birth = date(1980, 6, 15)
    age_57 = date(2037, 6, 15)
    pension_start = date(2036, 12, 15)  # exactly 6 months before 57th birthday
    r = compute_early_reduction(pension_start, birth)
    assert r.months_before_57 == 6
    assert r.reduction_pct == Decimal("0.0350")
    assert r.factor == Decimal("0.9650")


def test_full_case_age54_yos20_fc160k():
    """§11.2: Retire at 54, YOS 20, FC $160,000."""
    pct = compute_benefit_pct(Decimal("20")).final_pct    # 48%
    red = compute_early_reduction(_at_age(54), _BIRTH)    # factor 0.79
    fc = Decimal("160000")
    pension = fc * pct * red.factor
    assert pension == Decimal("60672.00"), f"Got {pension}"


def test_full_case_age50_yos20():
    """§11.2: Retire at 50, YOS 20, 49% reduction."""
    pct = compute_benefit_pct(Decimal("20")).final_pct    # 48%
    red = compute_early_reduction(_at_age(50), _BIRTH)    # factor 0.51
    fc = Decimal("160000")
    pension = fc * pct * red.factor
    assert pension == Decimal("160000") * Decimal("0.4800") * Decimal("0.5100")
