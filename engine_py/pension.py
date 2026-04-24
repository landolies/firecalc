"""
Pension calculation functions:
  - YOS computation
  - Yearly earnings from salary timeline
  - FC (both methods: highest 3-consecutive and final-year)
  - Benefit percentage with tier breakdowns and 80% cap
  - Early retirement reduction
  - COLA projection
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .models import (
    BenefitPctDetail,
    ColaRow,
    EarlyReductionDetail,
    FcDetail,
    PayPeriod,
    YearlyEarning,
)


_TWO_PLACES = Decimal("0.01")
_FOUR_PLACES = Decimal("0.0001")
_ZERO = Decimal("0")
_TWELVE = Decimal("12")


def _round2(d: Decimal) -> Decimal:
    return d.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _round4(d: Decimal) -> Decimal:
    return d.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def _add_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return date(d.year + n, d.month, 28)


def compute_yos(start: date, end: date) -> Decimal:
    """
    Years of service as a Decimal, counted by calendar anniversaries.
    Whole years come from year/month/day comparison; the fractional remainder
    is days-since-last-anniversary / days-in-current-anniversary-year.
    `end` is the retirement or separation date (exclusive end of service).
    """
    whole = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        whole -= 1
    last_anniv = _add_years(start, whole)
    next_anniv = _add_years(start, whole + 1)
    period = (next_anniv - last_anniv).days
    elapsed = (end - last_anniv).days
    return _round4(Decimal(whole) + Decimal(elapsed) / Decimal(period))


def _date_overlap_days(seg_start: date, seg_end: date, win_start: date, win_end: date) -> int:
    """Days of overlap between [seg_start, seg_end) and [win_start, win_end)."""
    lo = max(seg_start, win_start)
    hi = min(seg_end, win_end)
    return max(0, (hi - lo).days)


def build_yearly_earnings(
    timeline: list[PayPeriod],
    service_start: date,
    service_end: date,
) -> list[YearlyEarning]:
    """
    Convert a salary timeline into a list of YearlyEarning objects, one per
    year-of-service window starting at `service_start`.

    Each window is exactly [service_start + k years, service_start + (k+1) years).
    Annual earnings for a window = sum over timeline segments of:
      (overlap_days / total_window_days) × segment.annual
    """
    from datetime import timedelta

    def _add_years(d: date, n: int) -> date:
        try:
            return d.replace(year=d.year + n)
        except ValueError:
            return date(d.year + n, d.month, 28)

    yearly: list[YearlyEarning] = []
    k = 0
    while True:
        win_start = _add_years(service_start, k)
        win_end = _add_years(service_start, k + 1)
        if win_start >= service_end:
            break
        win_end = min(win_end, service_end)
        win_days = (win_end - win_start).days
        if win_days <= 0:
            break

        # Time-weighted average annual rate for this window.
        # For each segment: weight = overlap_days / win_days.
        # annual_base = Σ(seg.annual × overlap) / win_days
        weighted_sum = _ZERO
        for seg in timeline:
            overlap = _date_overlap_days(seg.start, seg.end, win_start, win_end)
            if overlap > 0:
                weighted_sum += seg.annual * Decimal(overlap)

        annual_base = weighted_sum / Decimal(win_days)

        yearly.append(YearlyEarning(
            year_start=win_start,
            year_end=win_end,
            annual_base=_round2(annual_base),
        ))
        k += 1

    return yearly


def compute_fc_3yr_avg(yearly_earnings: list[YearlyEarning]) -> FcDetail:
    """
    Find the highest 3 consecutive years-of-service windows by aggregate base pay.
    FC = average of those 3 years' annual base pay.
    If fewer than 3 years exist, use all available years.
    """
    n = len(yearly_earnings)
    if n == 0:
        return FcDetail(method="3yr_avg", annual_fc=_ZERO, yearly_earnings=[], note="No earnings data")

    window = min(3, n)
    best_sum = _ZERO
    best_start = 0
    for i in range(n - window + 1):
        s = sum((y.annual_base for y in yearly_earnings[i: i + window]), _ZERO)
        if s > best_sum:
            best_sum = s
            best_start = i

    best_years = yearly_earnings[best_start: best_start + window]
    fc = _round2(best_sum / Decimal(window))
    return FcDetail(
        method="3yr_avg",
        annual_fc=fc,
        yearly_earnings=list(best_years),
        note=f"Average of highest {window} consecutive YOS windows",
    )


def compute_fc_final(timeline: list[PayPeriod], service_end: date) -> FcDetail:
    """
    FC from the final year only: annualize the pay rate in effect on the last
    day of service (service_end - 1 day).
    """
    if not timeline:
        return FcDetail(method="final", annual_fc=_ZERO, yearly_earnings=[], note="No earnings data")

    last_seg = timeline[-1]
    fc = _round2(last_seg.annual)
    return FcDetail(
        method="final",
        annual_fc=fc,
        yearly_earnings=[],
        note=f"Annualized final pay: {last_seg.biweekly} × 26 = {fc}",
    )


def compute_benefit_pct(yos: Decimal) -> BenefitPctDetail:
    """
    Tiered benefit percentage:
      Years 1–20:  2.4% per year
      Years 21–25: 3.0% per year  (beginning of 21st year)
      Years 26+:   3.4% per year  (beginning of 26th year)
      Hard cap: 80%
    """
    TIER1_MAX = Decimal("20")
    TIER2_MAX = Decimal("25")
    TIER1_RATE = Decimal("0.024")
    TIER2_RATE = Decimal("0.030")
    TIER3_RATE = Decimal("0.034")
    CAP = Decimal("0.80")

    t1 = min(yos, TIER1_MAX)
    t2 = max(_ZERO, min(yos, TIER2_MAX) - TIER1_MAX)
    t3 = max(_ZERO, yos - TIER2_MAX)

    raw = t1 * TIER1_RATE + t2 * TIER2_RATE + t3 * TIER3_RATE
    capped = raw >= CAP
    final = min(raw, CAP)

    return BenefitPctDetail(
        yos=yos,
        tier1_years=_round4(t1),
        tier1_pct=_round4(t1 * TIER1_RATE),
        tier2_years=_round4(t2),
        tier2_pct=_round4(t2 * TIER2_RATE),
        tier3_years=_round4(t3),
        tier3_pct=_round4(t3 * TIER3_RATE),
        raw_pct=_round4(raw),
        capped=capped,
        final_pct=_round4(final),
    )


def yos_at_cap() -> Decimal:
    """YOS where the 80% cap is first reached: exactly 30.0."""
    return Decimal("30")


def compute_early_reduction(retirement_age: int) -> EarlyReductionDetail:
    """
    7% per year for each whole year between retirement_age and 57.
    v0: whole-year ages only, so no monthly proration needed.
    """
    years_before_57 = max(0, 57 - retirement_age)
    reduction_pct = _round4(Decimal(years_before_57) * Decimal("0.07"))
    factor = _round4(Decimal("1") - reduction_pct)
    return EarlyReductionDetail(
        retirement_age=retirement_age,
        years_before_57=years_before_57,
        reduction_pct=reduction_pct,
        factor=max(_ZERO, factor),
    )


def project_cola(
    base_pension: Decimal,
    cola_rate: Decimal,
    retirement_date: date,
    cola_month: int,
    cola_day: int,
    project_to_age: int,
    birth_date: date,
) -> list[ColaRow]:
    """
    Project annual pension forward with COLA compounding.

    First COLA (on next Feb 1 after retirement): prorated by full months retired
    prior to that Feb 1. Partial months excluded per Fact Sheet.
    All subsequent COLAs: full annual increase.

    Returns one ColaRow per retirement year, starting at retirement_date through
    the year the retiree turns project_to_age.
    """
    rows: list[ColaRow] = []

    # First COLA strictly after retirement_date (prorated by full months retired)
    candidate = date(retirement_date.year, cola_month, cola_day)
    next_cola_date = candidate if candidate > retirement_date else date(candidate.year + 1, cola_month, cola_day)

    def _full_months(start: date, end: date) -> int:
        m = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day < start.day:
            m -= 1
        return max(0, m)

    first_cola_months = _full_months(retirement_date, next_cola_date)
    next_cola_factor = Decimal(1) + cola_rate * Decimal(first_cola_months) / _TWELVE
    full_cola_factor = Decimal(1) + cola_rate

    # Walk year by year. Compute age from birthday, not raw year subtraction.
    age = retirement_date.year - birth_date.year
    if (retirement_date.month, retirement_date.day) < (birth_date.month, birth_date.day):
        age -= 1

    current_pension = base_pension
    year = retirement_date.year
    while age <= project_to_age:
        next_year_start = date(year + 1, 1, 1)
        while next_cola_date < next_year_start:
            current_pension = _round2(current_pension * next_cola_factor)
            next_cola_date = date(next_cola_date.year + 1, cola_month, cola_day)
            next_cola_factor = full_cola_factor

        rows.append(ColaRow(
            age=age,
            year=year,
            annual_pension=_round2(current_pension),
            monthly_pension=_round2(current_pension / _TWELVE),
        ))
        year += 1
        age += 1

    return rows
