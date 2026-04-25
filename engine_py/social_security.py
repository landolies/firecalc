"""
Social Security retirement-benefit projection.

Pipeline:
    earnings_by_year (capped at TAXABLE_MAX) ->
    indexed_earnings (× AWI(age-60) / AWI(year)) ->
    AIME (top 35 indexed years / 420 months) ->
    PIA at FRA (90% × AIME up to b1, + 32% × b1..b2, + 15% above b2) ->
    benefit at claiming age (early-claim reduction or delayed credit)

WEP and GPO are not modeled — repealed by the Social Security Fairness Act
effective for benefits payable for months after December 2023.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional

from . import ss_tables


_ZERO = Decimal("0")
_TWELVE = Decimal("12")
_DOLLAR = Decimal("1")
_DIME = Decimal("0.1")  # exponent -1 — quantize rounds to nearest dime


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------

@dataclass
class SsInputs:
    birth_date: date
    claiming_age_years: int = 67       # 62..70
    claiming_age_months: int = 0       # 0..11; total claim age in months below

    # Earnings sources
    sjfd_is_covered: bool = False      # SJFD Tier 2 is non-covered; usually False
    prior_covered_earnings: dict[int, Decimal] = field(default_factory=dict)
    # Year-keyed annual earnings from non-SJFD covered employment.

    # User-overridable tables (None → use bundled defaults from ss_tables)
    awi_overrides: Optional[dict[int, Decimal]] = None
    taxable_max_overrides: Optional[dict[int, Decimal]] = None

    # COLA assumption for forward projection
    ss_cola_rate: Decimal = ss_tables.DEFAULT_SS_COLA_RATE


@dataclass
class IndexedEarningRow:
    year: int
    raw_earnings: Decimal
    capped_earnings: Decimal
    index_factor: Decimal
    indexed_earnings: Decimal
    used_in_aime: bool       # True if among top-35 nonzero years


@dataclass
class SsResult:
    fra_years: int
    fra_months: int
    eligibility_year: int
    bend_point_1: Decimal
    bend_point_2: Decimal
    aime: Decimal
    pia_at_fra: Decimal
    monthly_benefit_at_claiming: Decimal
    annual_benefit_at_claiming: Decimal
    indexed_earnings: list[IndexedEarningRow]
    credits_total: int
    credits_needed: int = 40
    is_vested: bool = False
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table(overrides: Optional[dict[int, Decimal]], default: dict[int, Decimal]) -> dict[int, Decimal]:
    """Merge overrides on top of defaults; returns a fresh dict so we don't mutate."""
    if not overrides:
        return default
    merged = dict(default)
    merged.update(overrides)
    return merged


def _eligibility_year(birth_date: date) -> int:
    """Year the worker attains age 62. SS rule: 'attains age' on the day before
    the birthday, so anyone born on Jan 1 attains age 62 on Dec 31 of the
    prior year. We follow the day-before convention."""
    year = birth_date.year + 62
    if birth_date.month == 1 and birth_date.day == 1:
        year -= 1
    return year


def _index_year(birth_date: date) -> int:
    """Earnings are indexed using AWI(birth_year + 60). Earnings in years at or
    after that AWI year are NOT indexed."""
    return birth_date.year + 60


def _credits_for_year(earnings: Decimal, year: int) -> int:
    """4 credits per year if earnings >= 4 × QC threshold; otherwise prorated.
    Capped at 4 per year. QC for 2026 = $1,890."""
    if earnings <= _ZERO:
        return 0
    # Approximate QC using the 2026 threshold for 2026+, scaled backward by AWI
    # for earlier years. For simplicity we just use the thresholds we know.
    qc_2026 = Decimal("1890")
    awi_year = ss_tables.AWI_BY_YEAR.get(min(year, 2024), ss_tables.AWI_BY_YEAR[2024])
    qc_year = (qc_2026 * awi_year / ss_tables.AWI_BY_YEAR[2024]).quantize(_DOLLAR, rounding=ROUND_HALF_UP)
    if qc_year <= _ZERO:
        qc_year = qc_2026
    credits = min(4, int(earnings // qc_year))
    return credits


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------

def index_earnings(
    earnings_by_year: dict[int, Decimal],
    birth_date: date,
    awi: dict[int, Decimal],
    taxable_max: dict[int, Decimal],
) -> list[IndexedEarningRow]:
    """
    For each year, cap earnings at TAXABLE_MAX(year), then index by
    AWI(birth_year + 60) / AWI(year). Years at or after the index year
    use a factor of 1.0 (no indexing).
    """
    idx_year = _index_year(birth_date)
    idx_year_for_factor = min(idx_year, max(awi.keys()))
    if idx_year_for_factor not in awi:
        raise KeyError(f"AWI({idx_year_for_factor}) missing — required to index earnings")
    awi_idx = awi[idx_year_for_factor]

    rows: list[IndexedEarningRow] = []
    for year, raw in sorted(earnings_by_year.items()):
        cap = taxable_max.get(year)
        if cap is None:
            # No cap published for this year — treat as uncapped, but flag.
            capped = raw
        else:
            capped = min(raw, cap)

        if year >= idx_year:
            factor = Decimal("1")
        else:
            awi_year = awi.get(year)
            if awi_year is None or awi_year == 0:
                factor = Decimal("1")
            else:
                factor = (awi_idx / awi_year).quantize(Decimal("0.0000001"))
        indexed = (capped * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rows.append(IndexedEarningRow(
            year=year, raw_earnings=raw, capped_earnings=capped,
            index_factor=factor, indexed_earnings=indexed, used_in_aime=False,
        ))
    return rows


def compute_aime(rows: list[IndexedEarningRow]) -> Decimal:
    """AIME = sum of top 35 indexed years / 420 months. Mutates rows to set
    used_in_aime on the contributing rows. Truncated to whole dollars per
    SSA convention."""
    sorted_rows = sorted(rows, key=lambda r: r.indexed_earnings, reverse=True)
    for r in sorted_rows[:35]:
        if r.indexed_earnings > _ZERO:
            r.used_in_aime = True
    top_35_sum = sum((r.indexed_earnings for r in sorted_rows[:35]), Decimal("0"))
    aime = (top_35_sum / Decimal("420")).quantize(_DOLLAR, rounding=ROUND_DOWN)
    return aime


def compute_pia_at_fra(aime: Decimal, b1: Decimal, b2: Decimal) -> Decimal:
    """
    PIA = 90% × min(AIME, b1)
        + 32% × max(0, min(AIME, b2) - b1)
        + 15% × max(0, AIME - b2)
    Per SSA: PIA is rounded down to the next dime if not already a multiple.
    """
    tier1 = min(aime, b1) * Decimal("0.90")
    tier2 = max(_ZERO, min(aime, b2) - b1) * Decimal("0.32")
    tier3 = max(_ZERO, aime - b2) * Decimal("0.15")
    raw = tier1 + tier2 + tier3
    return raw.quantize(_DIME, rounding=ROUND_DOWN)


def _claim_months_relative_to_fra(
    claim_age_months: int, fra_years: int, fra_months: int,
) -> int:
    """Positive = months after FRA (delayed credits); negative = months early."""
    fra_total = fra_years * 12 + fra_months
    return claim_age_months - fra_total


def apply_claiming_age(
    pia: Decimal, claim_age_months: int, fra_years: int, fra_months: int,
    birth_year: int,
) -> Decimal:
    """
    Early-claim reduction: 5/9 of 1% per month for first 36 months early,
    then 5/12 of 1% per month beyond that.
    Delayed credits: 8% per year (2/3 of 1% per month) for birth years
    1943+, accruing through age 70.
    """
    delta = _claim_months_relative_to_fra(claim_age_months, fra_years, fra_months)
    if delta == 0:
        adjusted = pia
    elif delta < 0:
        months_early = -delta
        first_36 = min(36, months_early)
        beyond = max(0, months_early - 36)
        reduction = (Decimal(first_36) * Decimal("5") / Decimal("9") / Decimal("100")
                     + Decimal(beyond) * Decimal("5") / Decimal("12") / Decimal("100"))
        adjusted = pia * (Decimal("1") - reduction)
    else:
        # Delayed credits cap at age 70. Caller should validate claim_age <= 70.
        dr_per_month = _delayed_retirement_credit_per_month(birth_year)
        adjusted = pia * (Decimal("1") + Decimal(delta) * dr_per_month)
    # Final benefit is truncated to whole dollar per SSA practice
    return adjusted.quantize(_DOLLAR, rounding=ROUND_DOWN)


def _delayed_retirement_credit_per_month(birth_year: int) -> Decimal:
    """Per 42 USC §402(w)(6). 8%/yr for 1943+, lower for older birth years."""
    if birth_year <= 1924: return Decimal("3") / Decimal("12") / Decimal("100")
    if birth_year <= 1926: return Decimal("3.5") / Decimal("12") / Decimal("100")
    if birth_year <= 1928: return Decimal("4") / Decimal("12") / Decimal("100")
    if birth_year <= 1930: return Decimal("4.5") / Decimal("12") / Decimal("100")
    if birth_year <= 1932: return Decimal("5") / Decimal("12") / Decimal("100")
    if birth_year <= 1934: return Decimal("5.5") / Decimal("12") / Decimal("100")
    if birth_year <= 1936: return Decimal("6") / Decimal("12") / Decimal("100")
    if birth_year <= 1938: return Decimal("6.5") / Decimal("12") / Decimal("100")
    if birth_year <= 1940: return Decimal("7") / Decimal("12") / Decimal("100")
    if birth_year <= 1942: return Decimal("7.5") / Decimal("12") / Decimal("100")
    return Decimal("8") / Decimal("12") / Decimal("100")  # 1943+


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def compute_ss_scenario(
    inputs: SsInputs,
    sjfd_earnings_by_year: Optional[dict[int, Decimal]] = None,
) -> SsResult:
    """
    Compute the projected SS benefit. `sjfd_earnings_by_year` is the
    SJFD-side annual earnings timeline; it's ignored unless
    inputs.sjfd_is_covered is True.
    """
    warnings: list[str] = []
    awi = _table(inputs.awi_overrides, ss_tables.AWI_BY_YEAR)
    tmax = _table(inputs.taxable_max_overrides, ss_tables.TAXABLE_MAX_BY_YEAR)

    # Combine earnings sources
    earnings: dict[int, Decimal] = dict(inputs.prior_covered_earnings)
    if inputs.sjfd_is_covered and sjfd_earnings_by_year:
        for y, e in sjfd_earnings_by_year.items():
            earnings[y] = earnings.get(y, _ZERO) + e

    fra_y, fra_m = ss_tables.full_retirement_age(inputs.birth_date.year)
    elig_year = _eligibility_year(inputs.birth_date)

    try:
        b1, b2 = ss_tables.bend_points(elig_year, awi)
    except KeyError as e:
        warnings.append(str(e))
        b1, b2 = _ZERO, _ZERO

    if not earnings:
        warnings.append(
            "No covered earnings entered. If SJFD is your only employment "
            "and the plan is non-covered (Tier 2 default), your projected "
            "Social Security benefit is $0. Add prior covered earnings if "
            "you worked elsewhere under Social Security."
        )
        return SsResult(
            fra_years=fra_y, fra_months=fra_m, eligibility_year=elig_year,
            bend_point_1=b1, bend_point_2=b2,
            aime=_ZERO, pia_at_fra=_ZERO,
            monthly_benefit_at_claiming=_ZERO, annual_benefit_at_claiming=_ZERO,
            indexed_earnings=[], credits_total=0, is_vested=False,
            warnings=warnings,
        )

    rows = index_earnings(earnings, inputs.birth_date, awi, tmax)
    aime = compute_aime(rows)
    pia = compute_pia_at_fra(aime, b1, b2) if b1 > _ZERO else _ZERO

    claim_months = inputs.claiming_age_years * 12 + inputs.claiming_age_months
    if claim_months < 62 * 12 or claim_months > 70 * 12:
        warnings.append(
            f"Claiming age {inputs.claiming_age_years}y {inputs.claiming_age_months}m "
            "is outside the 62–70 range allowed by SSA."
        )

    monthly = apply_claiming_age(pia, claim_months, fra_y, fra_m, inputs.birth_date.year)

    credits = sum(_credits_for_year(e, y) for y, e in earnings.items())
    is_vested = credits >= 40
    if not is_vested:
        warnings.append(
            f"Not vested for SS retirement: {credits} of 40 credits earned. "
            "Projected benefit shown assumes you reach 40 credits before claiming."
        )

    return SsResult(
        fra_years=fra_y, fra_months=fra_m, eligibility_year=elig_year,
        bend_point_1=b1, bend_point_2=b2,
        aime=aime, pia_at_fra=pia,
        monthly_benefit_at_claiming=monthly,
        annual_benefit_at_claiming=monthly * _TWELVE,
        indexed_earnings=rows, credits_total=credits, is_vested=is_vested,
        warnings=warnings,
    )
