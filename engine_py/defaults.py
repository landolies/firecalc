"""FY 2026/27 pay grid (includes 3.50% GWI). Source: SJFD bi-weekly pay schedule."""
from datetime import date
from decimal import Decimal

from .models import PayGrid

FIREFIGHTER_RECRUIT = "Firefighter Recruit"
FIREFIGHTER = "Firefighter"
FIRE_ENGINEER = "Fire Engineer"
FIRE_CAPTAIN = "Fire Captain"

RANKS_IN_SCOPE = [FIREFIGHTER_RECRUIT, FIREFIGHTER, FIRE_ENGINEER, FIRE_CAPTAIN]

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
    (FIRE_ENGINEER, 6): "7384.54",
    (FIRE_CAPTAIN, 1): "6669.01",
    (FIRE_CAPTAIN, 2): "6995.28",
    (FIRE_CAPTAIN, 3): "7335.23",
    (FIRE_CAPTAIN, 4): "7693.73",
    (FIRE_CAPTAIN, 5): "8079.66",
}

FY2627_PAY_GRID = PayGrid(
    rates={k: Decimal(v) for k, v in _RATES.items()}
)

FY2627_EFFECTIVE_DATE = date(2026, 7, 1)

DEFAULT_GWI_RATE = Decimal("0.035")
DEFAULT_COLA_RATE = Decimal("0.020")
