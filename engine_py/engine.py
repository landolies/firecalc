"""
Main entry point: compute_retirement_scenario(inputs) -> ScenarioResult.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from .models import (
    ColaRow,
    EarlyReductionDetail,
    ScenarioInputs,
    ScenarioResult,
)
from .pay_timeline import build_salary_timeline
from .pension import (
    build_yearly_earnings,
    compute_benefit_pct,
    compute_early_reduction,
    compute_fc_3yr_avg,
    compute_fc_final,
    compute_yos,
    project_cola,
    yos_at_cap,
)


_MIN_RETIREMENT_AGE = 50
_MIN_VESTING_YOS = Decimal("5")
_COLA_PROJECT_TO_AGE = 95


def _birthday(birth_date: date, age: int) -> date:
    """Date of the `age`-th birthday."""
    try:
        return birth_date.replace(year=birth_date.year + age)
    except ValueError:
        # Feb 29 birthday: use Feb 28
        return date(birth_date.year + age, birth_date.month, 28)


def compute_retirement_scenario(inputs: ScenarioInputs) -> ScenarioResult:
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Derived dates
    # ------------------------------------------------------------------
    retirement_date = _birthday(inputs.birth_date, inputs.retirement_age)

    if inputs.retirement_type == "deferred_vested":
        if inputs.separation_date is None or inputs.pension_start_date is None:
            raise ValueError("separation_date and pension_start_date required for deferred_vested")
        service_end = inputs.separation_date
        pension_start = inputs.pension_start_date
        pension_start_age = (
            pension_start.year - inputs.birth_date.year
            - ((pension_start.month, pension_start.day) < (inputs.birth_date.month, inputs.birth_date.day))
        )
        effective_retirement_age = pension_start_age
    else:
        service_end = retirement_date
        pension_start = retirement_date
        effective_retirement_age = inputs.retirement_age

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if effective_retirement_age < _MIN_RETIREMENT_AGE:
        warnings.append(
            f"Retirement age {effective_retirement_age} is below the minimum age of {_MIN_RETIREMENT_AGE}."
        )

    # ------------------------------------------------------------------
    # Salary timeline
    # ------------------------------------------------------------------
    timeline = build_salary_timeline(inputs, service_end, warnings=warnings)

    final_period = timeline[-1] if timeline else None
    final_rank = final_period.rank if final_period else inputs.current_rank
    final_step = final_period.step if final_period else inputs.current_step

    # ------------------------------------------------------------------
    # YOS
    # ------------------------------------------------------------------
    yos = compute_yos(inputs.hire_date, service_end)

    if yos < _MIN_VESTING_YOS:
        warnings.append(
            f"Not vested: {yos} YOS at {'separation' if inputs.retirement_type == 'deferred_vested' else 'retirement'} "
            f"(minimum {_MIN_VESTING_YOS} required)."
        )

    # ------------------------------------------------------------------
    # Final compensation
    # ------------------------------------------------------------------
    yearly = build_yearly_earnings(timeline, inputs.hire_date, service_end)
    fc_3yr = compute_fc_3yr_avg(yearly)
    fc_final = compute_fc_final(timeline, service_end)

    # ------------------------------------------------------------------
    # Benefit percentage
    # ------------------------------------------------------------------
    benefit_detail = compute_benefit_pct(yos)

    # Cap date: when did (or will) the employee hit 30 YOS?
    cap_yos = yos_at_cap()
    cap_reached = yos >= cap_yos
    if cap_reached:
        # Approximate cap date as hire_date + 30 years
        try:
            cap_date: Optional[date] = inputs.hire_date.replace(year=inputs.hire_date.year + 30)
        except ValueError:
            cap_date = date(inputs.hire_date.year + 30, inputs.hire_date.month, 28)
    else:
        cap_date = None

    # ------------------------------------------------------------------
    # Early retirement reduction
    # ------------------------------------------------------------------
    early_reduction = compute_early_reduction(effective_retirement_age)

    # ------------------------------------------------------------------
    # Pension figures
    # ------------------------------------------------------------------
    def _pension(fc: Decimal) -> Decimal:
        if warnings:
            return Decimal("0")
        return fc * benefit_detail.final_pct * early_reduction.factor

    annual_3yr = _pension(fc_3yr.annual_fc)
    monthly_3yr = annual_3yr / 12
    annual_final = _pension(fc_final.annual_fc)
    monthly_final = annual_final / 12

    from decimal import ROUND_HALF_UP
    _2p = Decimal("0.01")
    annual_3yr = annual_3yr.quantize(_2p, rounding=ROUND_HALF_UP)
    monthly_3yr = monthly_3yr.quantize(_2p, rounding=ROUND_HALF_UP)
    annual_final = annual_final.quantize(_2p, rounding=ROUND_HALF_UP)
    monthly_final = monthly_final.quantize(_2p, rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # COLA projection
    # ------------------------------------------------------------------
    cm, cd = inputs.cola_effective_month_day
    if inputs.show_cola and not warnings:
        cola_rows_3yr = project_cola(
            annual_3yr, inputs.cola_rate, pension_start, cm, cd,
            _COLA_PROJECT_TO_AGE, inputs.birth_date,
        )
        cola_rows_final = project_cola(
            annual_final, inputs.cola_rate, pension_start, cm, cd,
            _COLA_PROJECT_TO_AGE, inputs.birth_date,
        )
    else:
        cola_rows_3yr = []
        cola_rows_final = []

    return ScenarioResult(
        inputs=inputs,
        retirement_date=retirement_date,
        separation_date=inputs.separation_date,
        yos_at_retirement=yos,
        final_rank=final_rank,
        final_step=final_step,
        cap_reached=cap_reached,
        cap_date=cap_date,
        fc_3yr=fc_3yr,
        fc_final=fc_final,
        benefit_pct_detail=benefit_detail,
        early_reduction=early_reduction,
        annual_pension_3yr=annual_3yr,
        monthly_pension_3yr=monthly_3yr,
        annual_pension_final=annual_final,
        monthly_pension_final=monthly_final,
        cola_rows_3yr=cola_rows_3yr,
        cola_rows_final=cola_rows_final,
        salary_timeline=timeline,
        warnings=warnings,
    )
