"""§11.5 — FC methods diverge with mid-career promotion."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.engine import compute_retirement_scenario
from engine_py.models import PromotionEvent
from .conftest import make_inputs


def test_fc_methods_diverge_after_promotion():
    """
    Retire at age 57 after a promotion at age 54 (Engineer).
    FC_3yr_avg reflects a mix of pre/post-promotion salary.
    FC_final uses only the final year (post-promotion) salary.
    They should differ meaningfully.
    """
    birth = date(1980, 1, 1)
    hire = date(2005, 1, 1)
    promotion_date = date(2034, 1, 1)  # age 54

    inputs = make_inputs(
        birth_date=birth,
        hire_date=hire,
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2011, 1, 1),  # 6 years after hire
        gwi_rate=Decimal("0"),      # simplify: no GWI so the divergence is purely from promotion
        retirement_age=57,
        promotions=[PromotionEvent("Fire Engineer", promotion_date)],
    )

    result = compute_retirement_scenario(inputs)
    assert not result.warnings

    # FC_final = the post-promotion (Engineer) salary annualized
    # FC_3yr_avg = average of the 3 highest consecutive YOS windows
    # Since promotion is at age 54 and retirement at 57, some of the 3-year
    # window includes pre-promotion (FF) salary → FC_3yr_avg < FC_final
    assert result.fc_final.annual_fc > result.fc_3yr.annual_fc, (
        f"FC_final ({result.fc_final.annual_fc}) should exceed FC_3yr ({result.fc_3yr.annual_fc})"
    )
    # The difference should be non-trivial (promotion gives ≥5% raise)
    diff_pct = (result.fc_final.annual_fc - result.fc_3yr.annual_fc) / result.fc_3yr.annual_fc
    assert diff_pct >= Decimal("0.005"), f"FC difference too small: {diff_pct:.2%}"


def test_fc_methods_equal_no_promotion_constant_salary():
    """With no GWI and no promotion, all years have same salary → both FC methods equal."""
    inputs = make_inputs(
        birth_date=date(1980, 1, 1),
        hire_date=date(2005, 1, 1),
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2011, 1, 1),
        gwi_rate=Decimal("0"),
        retirement_age=57,
        promotions=[],
    )
    result = compute_retirement_scenario(inputs)
    assert not result.warnings
    assert result.fc_3yr.annual_fc == result.fc_final.annual_fc
