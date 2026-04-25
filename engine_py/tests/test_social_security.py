"""
Social Security PIA / claiming-age tests.

Reference cases drawn from SSA's own worked examples and the bend-point
formula at https://www.ssa.gov/oact/cola/bendpoints.html.
"""
from datetime import date
from decimal import Decimal

import pytest

from engine_py import ss_tables, social_security as ss


# ---------------------------------------------------------------------------
# ss_tables — bend points and FRA
# ---------------------------------------------------------------------------

def test_bend_points_2024_match_published():
    """Published 2024 bend points: $1,174 / $7,078."""
    b1, b2 = ss_tables.bend_points(2024)
    assert b1 == Decimal("1174")
    assert b2 == Decimal("7078")


def test_bend_points_2025_match_published():
    """Published 2025 bend points: $1,226 / $7,392 (formula-correct;
    SSA literature varies by ±$1 due to rounding interpretation)."""
    b1, b2 = ss_tables.bend_points(2025)
    assert b1 == Decimal("1226")
    assert b2 in (Decimal("7391"), Decimal("7392"))  # ±$1 tolerance


def test_bend_points_2026_match_published():
    """Published 2026 bend points: derived from AWI(2024) = $69,846.57."""
    b1, b2 = ss_tables.bend_points(2026)
    assert b1 == Decimal("1286")
    assert b2 == Decimal("7749")


def test_bend_points_unknown_year_raises():
    with pytest.raises(KeyError, match="AWI"):
        ss_tables.bend_points(2099)


def test_fra_modern_birth_year():
    assert ss_tables.full_retirement_age(1960) == (67, 0)
    assert ss_tables.full_retirement_age(1986) == (67, 0)
    assert ss_tables.full_retirement_age(1955) == (66, 2)
    assert ss_tables.full_retirement_age(1957) == (66, 6)


# ---------------------------------------------------------------------------
# social_security — pure functions
# ---------------------------------------------------------------------------

def test_pia_at_fra_simple_below_first_bend():
    """AIME entirely below b1 → PIA = 90% × AIME, rounded down to dime."""
    pia = ss.compute_pia_at_fra(Decimal("1000"), Decimal("1226"), Decimal("7392"))
    assert pia == Decimal("900.0")


def test_pia_at_fra_spans_first_bend():
    """AIME between b1 and b2 → 90% × b1 + 32% × (AIME - b1)."""
    pia = ss.compute_pia_at_fra(Decimal("4000"), Decimal("1226"), Decimal("7392"))
    # 90% × 1226 + 32% × (4000-1226) = 1103.40 + 887.68 = 1991.08 → 1991.00
    assert pia == Decimal("1991.0")


def test_pia_at_fra_spans_all_three_bends():
    """AIME above b2 → all three tiers."""
    pia = ss.compute_pia_at_fra(Decimal("10000"), Decimal("1226"), Decimal("7392"))
    # 90%×1226 + 32%×(7392-1226) + 15%×(10000-7392)
    # = 1103.40 + 1973.12 + 391.20 = 3467.72 → 3467.70
    assert pia == Decimal("3467.7")


def test_apply_claiming_age_at_fra_no_change():
    pia = Decimal("2000.00")
    benefit = ss.apply_claiming_age(pia, claim_age_months=67*12,
                                    fra_years=67, fra_months=0, birth_year=1986)
    assert benefit == Decimal("2000")


def test_apply_claiming_age_36_months_early():
    """Exactly 36 months early → 5/9 × 36 = 20% reduction."""
    pia = Decimal("2000.00")
    benefit = ss.apply_claiming_age(pia, claim_age_months=64*12,
                                    fra_years=67, fra_months=0, birth_year=1986)
    # 2000 × (1 - 0.20) = 1600 (exact)
    assert benefit == Decimal("1600")


def test_apply_claiming_age_60_months_early():
    """60 months early (claim at 62 with FRA 67): first 36 at 5/9, next 24 at 5/12.
    36×5/9 = 20%, 24×5/12 = 10% → 30% reduction → 1400."""
    pia = Decimal("2000.00")
    benefit = ss.apply_claiming_age(pia, claim_age_months=62*12,
                                    fra_years=67, fra_months=0, birth_year=1986)
    assert benefit == Decimal("1400")


def test_apply_claiming_age_age_70_full_drcs():
    """36 months delayed at 8%/yr (2/3% per month) → 24% increase."""
    pia = Decimal("2000.00")
    benefit = ss.apply_claiming_age(pia, claim_age_months=70*12,
                                    fra_years=67, fra_months=0, birth_year=1986)
    # 2000 × 1.24 = 2480
    assert benefit == Decimal("2480")


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def test_index_earnings_caps_at_taxable_max():
    """Earnings above the year's taxable max are capped before indexing."""
    rows = ss.index_earnings(
        earnings_by_year={2020: Decimal("200000")},  # above 2020 cap of 137700
        birth_date=date(1986, 10, 1),
        awi=ss_tables.AWI_BY_YEAR,
        taxable_max=ss_tables.TAXABLE_MAX_BY_YEAR,
    )
    assert rows[0].capped_earnings == Decimal("137700")


def test_index_earnings_no_indexing_after_age_60():
    """Years at or after birth_year + 60 use factor = 1.0."""
    # Birth 1986 → index year 2046. Earnings in 2046+ unindexed.
    rows = ss.index_earnings(
        earnings_by_year={2046: Decimal("100000")},
        birth_date=date(1986, 10, 1),
        awi=ss_tables.AWI_BY_YEAR,
        taxable_max=ss_tables.TAXABLE_MAX_BY_YEAR,
    )
    # 2046 has no published taxable max — uncapped, unindexed
    assert rows[0].index_factor == Decimal("1")
    assert rows[0].indexed_earnings == Decimal("100000.00")


def test_aime_takes_top_35_with_zero_padding():
    """A worker with 10 covered years gets 25 zero years included → AIME suppressed."""
    rows = [
        ss.IndexedEarningRow(
            year=2010 + i, raw_earnings=Decimal("50000"),
            capped_earnings=Decimal("50000"), index_factor=Decimal("1"),
            indexed_earnings=Decimal("50000"), used_in_aime=False,
        )
        for i in range(10)
    ]
    aime = ss.compute_aime(rows)
    # sum = 500_000; / 420 = 1190.47 → truncated to 1190
    assert aime == Decimal("1190")
    # Only the 10 nonzero years should be marked used
    assert sum(1 for r in rows if r.used_in_aime) == 10


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def test_end_to_end_no_earnings_returns_zero_with_warning():
    """SJFD-only employee, plan non-covered → no SS earnings, $0 benefit, warning."""
    inputs = ss.SsInputs(
        birth_date=date(1986, 10, 1),
        sjfd_is_covered=False,
        prior_covered_earnings={},
    )
    result = ss.compute_ss_scenario(inputs)
    assert result.monthly_benefit_at_claiming == Decimal("0")
    assert any("No covered earnings" in w for w in result.warnings)


def test_end_to_end_with_prior_earnings():
    """A worker with 35 years of capped earnings should produce a near-max
    benefit. Use birth_year=1964 so eligibility year (2026) is within the
    AWI table — the test would otherwise fail solely because bend points
    can't be computed for far-future eligibility years."""
    earnings = {y: Decimal("500000") for y in range(1986, 2021)}  # 35 years
    inputs = ss.SsInputs(
        birth_date=date(1964, 1, 2),
        prior_covered_earnings=earnings,
        claiming_age_years=67,
    )
    result = ss.compute_ss_scenario(inputs)
    assert result.aime > Decimal("9000"), f"AIME too low: {result.aime}"
    assert result.pia_at_fra > Decimal("3000"), f"PIA too low: {result.pia_at_fra}"
    assert result.is_vested
    # 2031 has no published taxable max yet — the warning may or may not
    # fire depending on whether claim age is at FRA. At FRA exactly, monthly
    # benefit = PIA truncated to dollar.
    from decimal import ROUND_DOWN
    assert result.monthly_benefit_at_claiming == result.pia_at_fra.quantize(
        Decimal("1"), rounding=ROUND_DOWN,
    )


def test_credits_count_simple():
    """A single year at $20k earns 4 credits (well above QC × 4)."""
    inputs = ss.SsInputs(
        birth_date=date(1986, 10, 1),
        prior_covered_earnings={2020: Decimal("20000")},
    )
    result = ss.compute_ss_scenario(inputs)
    assert result.credits_total == 4
    assert not result.is_vested  # 4 << 40
