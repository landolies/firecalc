"""§11.6 — GWI scaling."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pytest

from engine_py.defaults import FY2627_EFFECTIVE_DATE, FY2627_PAY_GRID
from engine_py.pay_timeline import _adjusted_biweekly


_FF7_BASE = Decimal("6343.70")
_FF7_ANNUAL_BASE = _FF7_BASE * 26  # 164,936.20


def _annual(biweekly: Decimal) -> Decimal:
    return (biweekly * 26).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_gwi_zero_no_change():
    """GWI = 0%: bi-weekly is unchanged regardless of year."""
    bw = _adjusted_biweekly(
        _FF7_BASE, FY2627_EFFECTIVE_DATE,
        date(2036, 7, 1),  # 10 years later
        Decimal("0"), 7, 1,
    )
    assert bw == _FF7_BASE
    assert _annual(bw) == Decimal("164936.20")


def test_gwi_one_year():
    """
    After 1 GWI: bw = round2(6343.70 × 1.035) = round2(6565.7295) = 6565.73.
    Annual = 6565.73 × 26 = 170,708.98.
    Note: spec §11.6 claims 170,708.97 (computed annual × 1.035 directly);
    our value is correct — biweekly is rounded first, then annualized.
    """
    bw = _adjusted_biweekly(
        _FF7_BASE, FY2627_EFFECTIVE_DATE,
        date(2027, 7, 1),
        Decimal("0.035"), 7, 1,
    )
    expected_bw = (_FF7_BASE * Decimal("1.035")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert bw == expected_bw
    assert _annual(bw) == Decimal("170708.98")


def test_gwi_ten_years():
    """
    After 10 GWI applications: annual ≈ 232,658.
    Note: spec §11.6 claims 232,693.43 — that figure is a calculation error in the spec.
    The correct value (164,936.20 × 1.035^10) = 232,658.80; our implementation gives
    232,658.92 (small difference due to biweekly rounding at each step).
    """
    bw = _adjusted_biweekly(
        _FF7_BASE, FY2627_EFFECTIVE_DATE,
        date(2036, 7, 1),
        Decimal("0.035"), 7, 1,
    )
    annual = _annual(bw)
    # Direct: 164936.20 × 1.035^10 = 232658.80
    direct = (Decimal("164936.20") * Decimal("1.035") ** 10).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert abs(annual - direct) <= Decimal("0.20"), (
        f"Expected ~{direct}, got {annual}"
    )


def test_gwi_exponent_same_fy():
    """Target on the grid's own effective date → exponent 0 → no scaling."""
    bw = _adjusted_biweekly(
        _FF7_BASE, FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert bw == _FF7_BASE


def test_gwi_backward_one_year():
    """One fiscal year BEFORE the grid date → divide by GWI factor."""
    bw = _adjusted_biweekly(
        _FF7_BASE, FY2627_EFFECTIVE_DATE,
        date(2025, 7, 1),  # one FY before 2026-07-01
        Decimal("0.035"), 7, 1,
    )
    expected = (_FF7_BASE / Decimal("1.035")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert bw == expected
