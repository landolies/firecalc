"""Generate fixtures/scenarios.json from end-to-end engine scenarios.

Invoke:  .venv/bin/python -m engine_py.export_fixtures

Each scenario runs compute_retirement_scenario and serializes (inputs, result)
so the JS port can diff against byte-identical expected output (SPEC §2.2).
The scenario set mirrors the end-to-end pytest cases in engine_py/tests/.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from .defaults import (
    DEFAULT_COLA_RATE,
    DEFAULT_GWI_RATE,
    FY2627_EFFECTIVE_DATE,
    FY2627_PAY_GRID,
)
from .engine import compute_retirement_scenario
from .models import PayGrid, PromotionEvent, ScenarioInputs
from ._serialize import to_jsonable


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_PATH = _PROJECT_ROOT / "fixtures" / "scenarios.json"


def _make_inputs(**overrides) -> ScenarioInputs:
    defaults = dict(
        birth_date=date(1986, 10, 1),
        hire_date=date(2019, 3, 24),
        current_rank="Firefighter",
        current_step=7,
        current_step_arrival_date=date(2025, 3, 24),
        pay_grid=FY2627_PAY_GRID,
        pay_grid_effective_date=FY2627_EFFECTIVE_DATE,
        gwi_rate=DEFAULT_GWI_RATE,
        cola_rate=DEFAULT_COLA_RATE,
        gwi_effective_month_day=(7, 1),
        cola_effective_month_day=(2, 1),
        retirement_age=57,
        promotions=[],
        retirement_type="active",
        separation_date=None,
        pension_start_date=None,
        show_cola=False,
        as_of_date=date(2026, 4, 24),
    )
    defaults.update(overrides)
    return ScenarioInputs(**defaults)


# ---------- scenario builders (one per end-to-end pytest case) --------------

def _vesting_minimum_5yos() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1968, 1, 1), hire_date=date(2020, 1, 1),
        retirement_age=57, current_step=1,
        current_step_arrival_date=date(2020, 1, 1),
        gwi_rate=Decimal("0"), show_cola=False,
    )


def _vesting_80pct_cap_30yos() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1966, 1, 1), hire_date=date(1993, 1, 1),
        retirement_age=57, current_step=7,
        current_step_arrival_date=date(1999, 1, 1),
        gwi_rate=Decimal("0"), show_cola=False,
    )


def _vesting_below_minimum_age() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1990, 1, 1), hire_date=date(2010, 1, 1),
        retirement_age=49, current_step=7,
        current_step_arrival_date=date(2017, 1, 1),
        gwi_rate=Decimal("0"),
    )


def _vesting_not_vested_4yos() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1966, 1, 1), hire_date=date(2019, 1, 1),
        retirement_age=57, current_step=4,
        current_step_arrival_date=date(2022, 1, 1),
        gwi_rate=Decimal("0"),
    )


def _fc_methods_diverge_after_promotion() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1980, 1, 1), hire_date=date(2005, 1, 1),
        current_step=7, current_step_arrival_date=date(2011, 1, 1),
        gwi_rate=Decimal("0"), retirement_age=57,
        promotions=[PromotionEvent("Fire Engineer", date(2034, 1, 1))],
    )


def _fc_methods_equal_no_promotion_constant_salary() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1980, 1, 1), hire_date=date(2005, 1, 1),
        current_step=7, current_step_arrival_date=date(2011, 1, 1),
        gwi_rate=Decimal("0"), retirement_age=57, promotions=[],
    )


def _reference_case_spec_author_gwi35() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1986, 10, 1), hire_date=date(2019, 3, 24),
        current_rank="Firefighter", current_step=7,
        current_step_arrival_date=date(2025, 3, 24),
        gwi_rate=Decimal("0.035"), retirement_age=57,
        promotions=[], show_cola=False,
    )


def _deferred_vested_fc_frozen() -> ScenarioInputs:
    biweekly_150k = Decimal("5769.23")
    custom_grid = PayGrid(rates={("Firefighter", s): biweekly_150k for s in range(1, 8)})
    return _make_inputs(
        birth_date=date(1975, 1, 1), hire_date=date(2008, 1, 1),
        current_rank="Firefighter", current_step=7,
        current_step_arrival_date=date(2014, 1, 1),
        pay_grid=custom_grid, pay_grid_effective_date=date(2023, 1, 1),
        gwi_rate=Decimal("0.035"), retirement_age=57,
        retirement_type="deferred_vested",
        separation_date=date(2023, 1, 1),
        pension_start_date=date(2032, 1, 1),
        show_cola=False,
    )


def _deferred_vested_fc_does_not_grow_with_gwi() -> ScenarioInputs:
    return _make_inputs(
        birth_date=date(1975, 1, 1), hire_date=date(2010, 1, 1),
        current_rank="Firefighter", current_step=7,
        current_step_arrival_date=date(2016, 1, 1),
        gwi_rate=Decimal("0.035"), retirement_age=57,
        retirement_type="deferred_vested",
        separation_date=date(2023, 1, 1),
        pension_start_date=date(2032, 1, 1),
    )


SCENARIOS: list[tuple[str, Callable[[], ScenarioInputs]]] = [
    ("vesting.minimum_5yos", _vesting_minimum_5yos),
    ("vesting.80pct_cap_30yos", _vesting_80pct_cap_30yos),
    ("vesting.below_minimum_age", _vesting_below_minimum_age),
    ("vesting.not_vested_4yos", _vesting_not_vested_4yos),
    ("fc_methods.diverge_after_promotion", _fc_methods_diverge_after_promotion),
    ("fc_methods.equal_no_promotion_constant_salary", _fc_methods_equal_no_promotion_constant_salary),
    ("reference_case.spec_author_gwi35", _reference_case_spec_author_gwi35),
    ("deferred_vested.fc_frozen", _deferred_vested_fc_frozen),
    ("deferred_vested.fc_does_not_grow_with_gwi", _deferred_vested_fc_does_not_grow_with_gwi),
]


def build_all_fixtures() -> list[dict]:
    out = []
    for name, builder in SCENARIOS:
        inputs = builder()
        result = compute_retirement_scenario(inputs)
        out.append({
            "name": name,
            "inputs": to_jsonable(inputs),
            "result": to_jsonable(result),
        })
    return out


def main() -> None:
    fixtures = build_all_fixtures()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _OUTPUT_PATH.open("w") as f:
        json.dump(fixtures, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Wrote {len(fixtures)} scenarios to {_OUTPUT_PATH.relative_to(_PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
