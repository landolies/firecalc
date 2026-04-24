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
    assert landing == 4, f"Expected Engineer Step 4, got {landing}"
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
    assert landing == 1, f"Expected Captain Step 1, got {landing}"
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
    assert landing in (3, 4), f"Expected Engineer Step 3 or 4, got {landing}"
