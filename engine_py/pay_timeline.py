"""
Salary timeline builder.

Produces a list of PayPeriod objects covering [hire_date, end_date) where
end_date is retirement_date (active) or separation_date (deferred_vested).

Strategy: maintain a cursor state (rank, step, step_clock) and at each step
determine the soonest upcoming event, emit a segment, advance state.

Event types:
  "hired"        — first segment
  "step_increase"— anniversary of step_clock (resets at hire and at promotions)
  "gwi"          — July 1 (configurable) each fiscal year
  "gwi+step"     — both fire on the same date
  "promotion"    — caller-supplied promotion date
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .models import PayGrid, PayPeriod, PromotionEvent, ScenarioInputs


_TWO_PLACES = Decimal("0.01")


def _round2(d: Decimal) -> Decimal:
    return d.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _add_years(d: date, n: int) -> date:
    """Add n years to d, clamping Feb 29 to Feb 28."""
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return date(d.year + n, d.month, 28)


def _gwi_exponent(grid_effective: date, target: date, gwi_month: int, gwi_day: int) -> int:
    """
    Number of GWI events that have fired in [grid_effective_date, target_date).
    Positive = future of grid; negative = past.
    """
    def _fy(d: date) -> int:
        """Most recent fiscal year start on or before d."""
        cutoff = date(d.year, gwi_month, gwi_day)
        return d.year if d >= cutoff else d.year - 1

    return _fy(target) - _fy(grid_effective)


def _adjusted_biweekly(
    base: Decimal,
    grid_effective: date,
    target: date,
    gwi_rate: Decimal,
    gwi_month: int,
    gwi_day: int,
) -> Decimal:
    n = _gwi_exponent(grid_effective, target, gwi_month, gwi_day)
    if n == 0:
        return _round2(base)
    factor = Decimal(str((1 + float(gwi_rate)) ** abs(n)))
    return _round2(base * factor if n > 0 else base / factor)


def _next_gwi_after(d: date, gwi_month: int, gwi_day: int) -> date:
    """First GWI date strictly after d."""
    candidate = date(d.year, gwi_month, gwi_day)
    if candidate > d:
        return candidate
    return date(d.year + 1, gwi_month, gwi_day)


def _landing_step(
    new_rank: str,
    pre_promotion_biweekly: Decimal,
    pay_grid: PayGrid,
    grid_effective: date,
    promotion_date: date,
    gwi_rate: Decimal,
    gwi_month: int,
    gwi_day: int,
) -> int:
    """
    Lowest step in new_rank whose GWI-adjusted bi-weekly on promotion_date
    is at least 5% above pre_promotion_biweekly.
    """
    threshold = pre_promotion_biweekly * Decimal("1.05")
    max_step = pay_grid.max_step(new_rank)
    for step in range(1, max_step + 1):
        base = pay_grid.get(new_rank, step)
        if base is None:
            continue
        adjusted = _adjusted_biweekly(base, grid_effective, promotion_date, gwi_rate, gwi_month, gwi_day)
        if adjusted >= threshold:
            return step
    return max_step  # fallback: should not happen with valid data


def build_salary_timeline(inputs: ScenarioInputs, end_date: date) -> list[PayPeriod]:
    """
    Return non-overlapping PayPeriod list covering [hire_date, end_date).
    end_date is exclusive.
    """
    if end_date <= inputs.hire_date:
        return []

    gm, gd = inputs.gwi_effective_month_day
    grid_eff = inputs.pay_grid_effective_date

    # Sort & validate promotions
    promotions: list[PromotionEvent] = sorted(
        [p for p in inputs.promotions if p.effective_date < end_date],
        key=lambda p: p.effective_date,
    )
    for p in promotions:
        if p.effective_date <= inputs.hire_date:
            raise ValueError(f"Promotion date {p.effective_date} must be after hire date {inputs.hire_date}")

    # All promotions are replayed from hire_date forward. The hire-time rank
    # is the rank just below the first promotion's target (using _RANK_ORDER);
    # with no promotions it's simply inputs.current_rank.
    initial_rank = inputs.current_rank
    if promotions:
        _RANK_ORDER = ["Firefighter Recruit", "Firefighter", "Fire Engineer", "Fire Captain"]

        def _rank_before_promotion(promo_new_rank: str) -> str:
            idx = _RANK_ORDER.index(promo_new_rank)
            if idx <= 1:
                return "Firefighter"
            return _RANK_ORDER[idx - 1]

        initial_rank = _rank_before_promotion(promotions[0].new_rank)

    if not promotions or initial_rank == inputs.current_rank:
        # The date the employee arrived at step 1 of their original rank:
        step_clock_0 = _add_years(inputs.current_step_arrival_date, -(inputs.current_step - 1))
        # Step at hire_date = 1 + whole years elapsed from step_clock_0 to hire_date.
        # (If step_clock_0 == hire_date → started at step 1; if step_clock_0 is years
        #  before hire_date → lateral hire who came in above step 1.)
        initial_step = 1 + _years_between(step_clock_0, inputs.hire_date)
        initial_step = max(1, min(initial_step, inputs.pay_grid.max_step(initial_rank)))
    else:
        # Promotions exist and initial_rank != current_rank: start at step 1 at hire
        initial_step = 1
        step_clock_0 = inputs.hire_date

    # ------------------------------------------------------------------
    # Forward walk
    # ------------------------------------------------------------------
    rank = initial_rank
    step = initial_step
    step_clock = step_clock_0  # anniversary base; step k arrived at step_clock + (k-1) years
    promo_queue = list(promotions)

    cursor = inputs.hire_date
    event_label = "hired"
    periods: list[PayPeriod] = []

    _MAX_ITERATIONS = 10_000
    _iteration = 0
    while cursor < end_date:
        _iteration += 1
        if _iteration > _MAX_ITERATIONS:
            raise RuntimeError(
                f"build_salary_timeline exceeded {_MAX_ITERATIONS} iterations "
                f"(cursor={cursor}, end_date={end_date}) — likely non-advancing loop"
            )
        # What's the soonest upcoming event?
        candidates: list[tuple[date, str]] = []

        # Next GWI
        next_gwi = _next_gwi_after(cursor, gm, gd)
        if next_gwi < end_date:
            candidates.append((next_gwi, "gwi"))

        # Next step increase (only if not at top step)
        max_st = inputs.pay_grid.max_step(rank)
        if step < max_st:
            # Step k arrived on: _add_years(step_clock, k-1)
            # Next step (k+1) arrives on: _add_years(step_clock, k)
            next_step_date = _add_years(step_clock, step)
            if next_step_date < end_date:
                candidates.append((next_step_date, "step_increase"))

        # Next promotion
        if promo_queue:
            candidates.append((promo_queue[0].effective_date, "promotion"))

        if not candidates:
            # No more events: emit final segment and done
            break

        next_event_date = min(d for d, _ in candidates)
        assert next_event_date > cursor, (
            f"timeline not advancing: cursor={cursor}, next_event_date={next_event_date}, "
            f"candidates={candidates}"
        )

        # Emit segment [cursor, next_event_date)
        base_rate = inputs.pay_grid.get(rank, step)
        if base_rate is None:
            raise ValueError(f"No pay defined for ({rank!r}, step {step})")
        bw = _adjusted_biweekly(base_rate, grid_eff, cursor, inputs.gwi_rate, gm, gd)
        periods.append(PayPeriod(
            start=cursor,
            end=next_event_date,
            rank=rank,
            step=step,
            biweekly=bw,
            annual=_round2(bw * 26),
            event=event_label,
        ))

        # Determine which events fire on next_event_date
        firing = {label for d, label in candidates if d == next_event_date}

        # Apply events (promotion takes priority over step; GWI is independent)
        if "promotion" in firing:
            pre_bw = _adjusted_biweekly(
                inputs.pay_grid.get(rank, step),
                grid_eff, next_event_date, inputs.gwi_rate, gm, gd,
            )
            p = promo_queue.pop(0)
            rank = p.new_rank
            step = _landing_step(rank, pre_bw, inputs.pay_grid, grid_eff,
                                  next_event_date, inputs.gwi_rate, gm, gd)
            step_clock = _add_years(next_event_date, -(step - 1))
            event_label = "promotion"
        else:
            if "step_increase" in firing and "gwi" in firing:
                step += 1
                event_label = "gwi+step"
            elif "step_increase" in firing:
                step += 1
                event_label = "step_increase"
            else:
                event_label = "gwi"

        cursor = next_event_date

    # Emit the tail segment
    if cursor < end_date:
        base_rate = inputs.pay_grid.get(rank, step)
        if base_rate is None:
            raise ValueError(f"No pay defined for ({rank!r}, step {step})")
        bw = _adjusted_biweekly(base_rate, grid_eff, cursor, inputs.gwi_rate, gm, gd)
        periods.append(PayPeriod(
            start=cursor,
            end=end_date,
            rank=rank,
            step=step,
            biweekly=bw,
            annual=_round2(bw * 26),
            event=event_label,
        ))

    return periods


def _years_between(earlier: date, later: date) -> int:
    """Whole years from earlier to later (floored)."""
    years = later.year - earlier.year
    if (later.month, later.day) < (earlier.month, earlier.day):
        years -= 1
    return max(0, years)
