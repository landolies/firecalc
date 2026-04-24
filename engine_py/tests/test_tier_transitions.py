"""§11.3 — Tier transition edge cases."""
from datetime import date
from decimal import Decimal

from engine_py.pension import compute_benefit_pct, compute_yos


def _pct(yos_decimal: str) -> Decimal:
    detail = compute_benefit_pct(Decimal(yos_decimal))
    return detail.final_pct


def test_exactly_20yos():
    assert _pct("20.0") == Decimal("0.4800")


def test_exactly_25yos():
    # 48% + 5 × 3.0% = 63.0%
    assert _pct("25.0") == Decimal("0.6300")


def test_exactly_30yos_cap():
    # (20×2.4%) + (5×3.0%) + (5×3.4%) = 48+15+17 = 80% → capped
    detail = compute_benefit_pct(Decimal("30.0"))
    assert detail.final_pct == Decimal("0.8000")
    assert detail.capped


def test_35yos_still_capped():
    detail = compute_benefit_pct(Decimal("35.0"))
    assert detail.final_pct == Decimal("0.8000")
    assert detail.capped


def test_22_5yos():
    # 48% + 2.5 × 3.0% = 48% + 7.5% = 55.5%
    assert _pct("22.5") == Decimal("0.5550")


def test_27_8yos():
    # 48% + 15% + 2.8 × 3.4% = 63% + 9.52% = 72.52%
    detail = compute_benefit_pct(Decimal("27.8"))
    assert detail.final_pct == Decimal("0.7252")
