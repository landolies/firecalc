"""§11.4 — Promotion landing step logic."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.defaults import FY2627_EFFECTIVE_DATE, FY2627_PAY_GRID
from engine_py.pay_timeline import _adjusted_biweekly, _landing_step


def test_ff_step7_to_engineer():
    """
    FF Step 7 bi-weekly = 6343.70. 5% threshold = 6660.885.
    Lowest Engineer step ≥ 6660.885 on the promotion date
    (assuming no GWI adjustment needed if promotion is in the same fiscal year as the grid).
    Engineer Step 1: 5816.21  — no
    Engineer Step 2: 6097.55  — no
    Engineer Step 3: 6391.58  — no
    Engineer Step 4: 6707.11  — YES
    """
    # Promotion on FY2627_EFFECTIVE_DATE means GWI exponent = 0 → no scaling
    pre_bw = Decimal("6343.70")
    landing = _landing_step(
        "Fire Engineer", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (4, True), f"Expected (4, True), got {landing}"
    # Confirm the value
    assert FY2627_PAY_GRID.get("Fire Engineer", 4) == Decimal("6707.11")


def test_ff_step7_to_captain():
    """
    FF Step 7 bi-weekly = 6343.70. Threshold = 6660.885.
    Captain Step 1: 6669.01 ≥ 6660.885 → landing = Step 1 (lowest qualifying).
    """
    pre_bw = Decimal("6343.70")
    landing = _landing_step(
        "Fire Captain", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (1, True), f"Expected (1, True), got {landing}"
    assert FY2627_PAY_GRID.get("Fire Captain", 1) == Decimal("6669.01")


def test_landing_step_uses_gwi_adjusted_rate():
    """
    If promotion occurs one fiscal year after the grid date, each step's
    base rate is scaled by GWI before comparing.
    """
    # One year after FY2627_EFFECTIVE_DATE → GWI exponent = 1
    promotion_date = date(2027, 7, 1)
    # FF Step 6 base = 6036.98. After 1 GWI: 6036.98 × 1.035 = 6248.27
    # Threshold: 6248.27 × 1.05 = 6560.68
    # Engineer Step 3 after GWI: 6391.58 × 1.035 = 6615.28 ≥ 6560.68 → Step 3
    # But Step 2 after GWI: 6097.55 × 1.035 = 6310.97 < 6560.68 → no
    # And Step 1 after GWI: 5816.21 × 1.035 = 6019.78 < 6560.68 → no
    ff6_bw = _adjusted_biweekly(
        Decimal("6036.98"), FY2627_EFFECTIVE_DATE, promotion_date, Decimal("0.035"), 7, 1
    )
    landing = _landing_step(
        "Fire Engineer", ff6_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, promotion_date,
        Decimal("0.035"), 7, 1,
    )
    step, ok = landing
    assert ok, f"Expected ok=True, got {landing}"
    assert step in (3, 4), f"Expected Engineer Step 3 or 4, got {step}"


def test_engineer_step5_to_inspector_violates_5pct():
    """
    Engineer Step 5 = 7041.59. 5% threshold = 7393.67.
    Fire Prevention Inspector top step = 7384.54 — fails by ~$9.
    Engine should fall back to Inspector top step and return ok=False.
    """
    pre_bw = Decimal("7041.59")
    landing = _landing_step(
        "Fire Prevention Inspector", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (5, False), f"Expected (5, False), got {landing}"


def test_arson_investigator_step5_to_captain_violates_5pct():
    """
    Arson Investigator Step 5 = 7702.60. 5% threshold = 8087.73.
    Fire Captain top step = 8079.66 — fails by ~$8.
    """
    pre_bw = Decimal("7702.60")
    landing = _landing_step(
        "Fire Captain", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (5, False), f"Expected (5, False), got {landing}"


def test_ff_step7_to_battalion_chief():
    """
    FF Step 7 = 6343.70. Threshold = 6660.89.
    Battalion Chief Step 1 = 8304.27 ≥ threshold → Step 1.
    """
    pre_bw = Decimal("6343.70")
    landing = _landing_step(
        "Battalion Chief", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (1, True), f"Expected (1, True), got {landing}"


def test_ff_step7_to_arson_investigator():
    """
    FF Step 7 = 6343.70. Threshold = 6660.89.
    Investigator Step 1: 6360.32  — no
    Investigator Step 2: 6669.01  — YES
    """
    pre_bw = Decimal("6343.70")
    landing = _landing_step(
        "Arson Investigator", pre_bw, FY2627_PAY_GRID,
        FY2627_EFFECTIVE_DATE, FY2627_EFFECTIVE_DATE,
        Decimal("0.035"), 7, 1,
    )
    assert landing == (2, True), f"Expected (2, True), got {landing}"


def test_5pct_violation_emits_warning_through_engine():
    """End-to-end: an Engineer→Inspector promotion at top step surfaces a
    warning in the ScenarioResult."""
    from datetime import date as _date
    from engine_py.engine import compute_retirement_scenario
    from engine_py.models import PromotionEvent, ScenarioInputs

    # The engine replays promotions from hire forward (current_rank is ignored
    # when promotions exist). Hire as FF, promote to Engineer early enough to
    # reach top step 6, then promote to Inspector — that hop violates the rule.
    inputs = ScenarioInputs(
        birth_date=_date(1986, 10, 1),
        hire_date=_date(2010, 1, 1),
        current_rank="Fire Prevention Inspector",
        current_step=1,
        current_step_arrival_date=_date(2010, 1, 1),
        retirement_age=57,
        retirement_type="active",
        promotions=[
            PromotionEvent(new_rank="Fire Engineer", effective_date=_date(2015, 1, 1)),
            PromotionEvent(new_rank="Fire Prevention Inspector", effective_date=_date(2030, 1, 1)),
        ],
        pay_grid=FY2627_PAY_GRID,
        pay_grid_effective_date=FY2627_EFFECTIVE_DATE,
        gwi_rate=Decimal("0"),  # disable GWI scaling for a clean compare
        gwi_effective_month_day=(7, 1),
        cola_rate=Decimal("0.02"),
        cola_effective_month_day=(2, 1),
    )
    result = compute_retirement_scenario(inputs)
    assert any("5%-landing rule" in w for w in result.warnings), (
        f"Expected a 5%-rule warning, got: {result.warnings}"
    )
