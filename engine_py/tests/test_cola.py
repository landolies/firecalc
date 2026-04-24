"""§11.7 — COLA projection."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.pension import project_cola


def test_cola_year_by_year():
    """
    Retire Feb 1 (birthday Feb 1, 1986 → age 57 on Feb 1, 2043).
    First COLA: Feb 1, 2044 — exactly 12 full months → full 2% applied.
    Year 1 (2043): $80,000
    Year 2 (2044): $81,600
    Year 10 (2052): $80,000 × 1.02^9 = $95,605.87
    """
    birth = date(1986, 2, 1)
    retirement = date(2043, 2, 1)
    rows = project_cola(
        base_pension=Decimal("80000"),
        cola_rate=Decimal("0.02"),
        retirement_date=retirement,
        cola_month=2,
        cola_day=1,
        project_to_age=95,
        birth_date=birth,
    )

    # Year 1 is the retirement year
    year1 = next(r for r in rows if r.year == 2043)
    assert year1.annual_pension == Decimal("80000.00"), f"Year 1: {year1.annual_pension}"

    # Year 2 (2044): first full COLA
    year2 = next(r for r in rows if r.year == 2044)
    assert year2.annual_pension == Decimal("81600.00"), f"Year 2: {year2.annual_pension}"

    # Year 10 (2052): 9 full COLAs applied ($80,000 × 1.02^9)
    year10 = next(r for r in rows if r.year == 2052)
    expected = (Decimal("80000") * Decimal("1.02") ** 9).quantize(Decimal("0.01"))
    assert abs(year10.annual_pension - expected) <= Decimal("0.02"), (
        f"Year 10: expected ~{expected}, got {year10.annual_pension}"
    )


def test_cola_toggled_off_is_flat():
    """cola_rate=0 should produce flat pension across all years."""
    rows = project_cola(
        base_pension=Decimal("80000"),
        cola_rate=Decimal("0"),           # effectively toggled off
        retirement_date=date(2043, 2, 1),
        cola_month=2,
        cola_day=1,
        project_to_age=70,
        birth_date=date(1986, 2, 1),
    )
    for r in rows:
        assert r.annual_pension == Decimal("80000.00"), f"Expected flat $80k, got {r.annual_pension} in {r.year}"


def test_cola_proration_october_retirement():
    """
    Retire October 1. Next Feb 1 is 4 full months away (Oct, Nov, Dec, Jan).
    First COLA = 80000 × (1 + 0.02 × 4/12) = 80000 × 1.006667 = 80533.33.
    """
    birth = date(1986, 10, 1)
    retirement = date(2043, 10, 1)
    rows = project_cola(
        base_pension=Decimal("80000"),
        cola_rate=Decimal("0.02"),
        retirement_date=retirement,
        cola_month=2,
        cola_day=1,
        project_to_age=95,
        birth_date=birth,
    )

    year2043 = next(r for r in rows if r.year == 2043)
    assert year2043.annual_pension == Decimal("80000.00")

    # First COLA: Feb 1, 2044, 4 full months proration
    year2044 = next(r for r in rows if r.year == 2044)
    expected_2044 = (Decimal("80000") * (1 + Decimal("0.02") * Decimal("4") / Decimal("12"))).quantize(Decimal("0.01"))
    assert year2044.annual_pension == expected_2044, f"2044: expected {expected_2044}, got {year2044.annual_pension}"

    # Second COLA: Feb 1, 2045, full 2%
    year2045 = next(r for r in rows if r.year == 2045)
    expected_2045 = (expected_2044 * Decimal("1.02")).quantize(Decimal("0.01"))
    assert year2045.annual_pension == expected_2045
