"""FY 2026/27 pay grid (includes 3.50% GWI). Source: SJFD bi-weekly pay schedule."""
from datetime import date
from decimal import Decimal

from .models import PayGrid

FIREFIGHTER_RECRUIT = "Firefighter Recruit"
FIREFIGHTER = "Firefighter"
FIRE_ENGINEER = "Fire Engineer"
FIRE_PREVENTION_INSPECTOR = "Fire Prevention Inspector"
ARSON_INVESTIGATOR = "Arson Investigator"
FIRE_CAPTAIN = "Fire Captain"
BATTALION_CHIEF = "Battalion Chief"

# Display order used by the pay-grid table and dropdowns.
RANKS_IN_SCOPE = [
    FIREFIGHTER_RECRUIT,
    FIREFIGHTER,
    FIRE_ENGINEER,
    FIRE_PREVENTION_INSPECTOR,
    ARSON_INVESTIGATOR,
    FIRE_CAPTAIN,
    BATTALION_CHIEF,
]

# Linear promotion ladder used to infer the rank-at-hire when promotions are
# scheduled but no explicit hire-rank is given. Specialty ranks (Inspector,
# Investigator) are off-ladder — they default to Firefighter as the prior rank.
LINEAR_LADDER = [
    FIREFIGHTER_RECRUIT,
    FIREFIGHTER,
    FIRE_ENGINEER,
    FIRE_CAPTAIN,
    BATTALION_CHIEF,
]
SPECIALTY_RANKS = {FIRE_PREVENTION_INSPECTOR, ARSON_INVESTIGATOR}

# Bi-weekly pay as photographed. Keyed (rank, step).
_RATES: dict[tuple[str, int], str] = {
    (FIREFIGHTER_RECRUIT, 1): "4148.72",
    (FIREFIGHTER, 1): "4769.02",
    (FIREFIGHTER, 2): "4998.58",
    (FIREFIGHTER, 3): "5239.87",
    (FIREFIGHTER, 4): "5494.83",
    (FIREFIGHTER, 5): "5760.53",
    (FIREFIGHTER, 6): "6036.98",
    (FIREFIGHTER, 7): "6343.70",
    (FIRE_ENGINEER, 1): "5816.21",
    (FIRE_ENGINEER, 2): "6097.55",
    (FIRE_ENGINEER, 3): "6391.58",
    (FIRE_ENGINEER, 4): "6707.11",
    (FIRE_ENGINEER, 5): "7041.59",
    (FIRE_PREVENTION_INSPECTOR, 1): "6097.55",
    (FIRE_PREVENTION_INSPECTOR, 2): "6391.58",
    (FIRE_PREVENTION_INSPECTOR, 3): "6707.11",
    (FIRE_PREVENTION_INSPECTOR, 4): "7033.38",
    (FIRE_PREVENTION_INSPECTOR, 5): "7384.54",
    (ARSON_INVESTIGATOR, 1): "6360.32",
    (ARSON_INVESTIGATOR, 2): "6669.01",
    (ARSON_INVESTIGATOR, 3): "6995.28",
    (ARSON_INVESTIGATOR, 4): "7335.23",
    (ARSON_INVESTIGATOR, 5): "7702.60",
    (FIRE_CAPTAIN, 1): "6669.01",
    (FIRE_CAPTAIN, 2): "6995.28",
    (FIRE_CAPTAIN, 3): "7335.23",
    (FIRE_CAPTAIN, 4): "7693.73",
    (FIRE_CAPTAIN, 5): "8079.66",
    (BATTALION_CHIEF, 1): "8304.27",
    (BATTALION_CHIEF, 2): "8713.57",
    (BATTALION_CHIEF, 3): "9138.51",
    (BATTALION_CHIEF, 4): "9590.79",
    (BATTALION_CHIEF, 5): "10071.00",
}

FY2627_PAY_GRID = PayGrid(
    rates={k: Decimal(v) for k, v in _RATES.items()}
)

FY2627_EFFECTIVE_DATE = date(2026, 7, 1)

DEFAULT_GWI_RATE = Decimal("0.035")
DEFAULT_COLA_RATE = Decimal("0.020")
