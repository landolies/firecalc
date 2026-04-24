"""Shared fixtures for pytest tests."""
from datetime import date
from decimal import Decimal

import pytest

from engine_py.defaults import (
    DEFAULT_COLA_RATE,
    DEFAULT_GWI_RATE,
    FY2627_EFFECTIVE_DATE,
    FY2627_PAY_GRID,
)
from engine_py.models import ScenarioInputs


def make_inputs(**overrides) -> ScenarioInputs:
    """
    Build a ScenarioInputs with sensible defaults (spec author profile).
    Override any field by name.
    """
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
