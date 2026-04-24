from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class PayGrid:
    """Bi-weekly pay by (rank_name, step). Missing pairs mean that step doesn't exist."""
    rates: dict[tuple[str, int], Decimal]

    def get(self, rank: str, step: int) -> Optional[Decimal]:
        return self.rates.get((rank, step))

    def max_step(self, rank: str) -> int:
        steps = [s for (r, s) in self.rates if r == rank]
        if not steps:
            raise ValueError(f"Unknown rank: {rank!r}")
        return max(steps)


@dataclass
class PromotionEvent:
    new_rank: str          # "Fire Engineer" or "Fire Captain"
    effective_date: date


@dataclass
class ScenarioInputs:
    # Personal
    birth_date: date
    hire_date: date
    current_rank: str
    current_step: int
    current_step_arrival_date: date

    # Pay grid
    pay_grid: PayGrid
    pay_grid_effective_date: date   # GWI grows forward and shrinks backward from here

    # Rates
    gwi_rate: Decimal               # e.g. Decimal("0.035")
    cola_rate: Decimal              # e.g. Decimal("0.020")
    gwi_effective_month_day: tuple[int, int] = (7, 1)
    cola_effective_month_day: tuple[int, int] = (2, 1)

    # Scenario
    retirement_age: int = 57
    promotions: list[PromotionEvent] = field(default_factory=list)
    retirement_type: str = "active"                 # "active" or "deferred_vested"
    separation_date: Optional[date] = None          # required if deferred_vested
    pension_start_date: Optional[date] = None       # required if deferred_vested

    # Display
    show_cola: bool = False
    as_of_date: date = field(default_factory=date.today)


# ---------------------------------------------------------------------------
# Internal building blocks (also exposed for audit/testing)
# ---------------------------------------------------------------------------

@dataclass
class PayPeriod:
    """A contiguous date range during which rank, step, and bi-weekly pay are constant."""
    start: date
    end: date          # exclusive — the first day the next segment begins
    rank: str
    step: int
    biweekly: Decimal
    annual: Decimal    # biweekly × 26
    event: str         # "hired", "step_increase", "gwi", "promotion", "gwi+step"


@dataclass
class YearlyEarning:
    """Annual base pay for a single year-of-service window."""
    year_start: date
    year_end: date     # exclusive
    annual_base: Decimal


@dataclass
class FcDetail:
    method: str                        # "3yr_avg" or "final"
    annual_fc: Decimal
    yearly_earnings: list[YearlyEarning]   # the 3 years used (empty for "final")
    note: str = ""


@dataclass
class BenefitPctDetail:
    yos: Decimal
    tier1_years: Decimal    # min(yos, 20)
    tier1_pct: Decimal
    tier2_years: Decimal    # years in 21–25 band
    tier2_pct: Decimal
    tier3_years: Decimal    # years beyond 25
    tier3_pct: Decimal
    raw_pct: Decimal        # before 80% cap
    capped: bool
    final_pct: Decimal      # after cap


@dataclass
class EarlyReductionDetail:
    retirement_age: int
    years_before_57: int    # max(0, 57 - retirement_age)
    reduction_pct: Decimal  # years_before_57 * 0.07
    factor: Decimal         # 1 - reduction_pct


@dataclass
class ColaRow:
    age: int
    year: int
    annual_pension: Decimal
    monthly_pension: Decimal


@dataclass
class ScenarioResult:
    # Inputs echo
    inputs: ScenarioInputs

    # Derived dates
    retirement_date: date
    separation_date: Optional[date]       # same as inputs for deferred_vested

    # Service
    yos_at_retirement: Decimal            # at retirement for active; at separation for deferred_vested
    final_rank: str
    final_step: int
    cap_reached: bool
    cap_date: Optional[date]              # first date 80% cap was achieved (if applicable)

    # FC
    fc_3yr: FcDetail
    fc_final: FcDetail

    # Benefit
    benefit_pct_detail: BenefitPctDetail

    # Early reduction
    early_reduction: EarlyReductionDetail

    # Pension figures (at retirement, before COLA)
    annual_pension_3yr: Decimal
    monthly_pension_3yr: Decimal
    annual_pension_final: Decimal
    monthly_pension_final: Decimal

    # COLA projections (empty if show_cola=False)
    cola_rows_3yr: list[ColaRow]
    cola_rows_final: list[ColaRow]

    # Full salary timeline
    salary_timeline: list[PayPeriod]

    # Warnings
    warnings: list[str]
