"""Deterministic JSON-safe serialization for engine dataclasses.

Used by the fixture exporter and the drift test. Decimal becomes a string
to preserve precision for the JS engine comparison (SPEC §2.2).
"""
from __future__ import annotations

from dataclasses import is_dataclass, fields
from datetime import date
from decimal import Decimal
from typing import Any

from .models import PayGrid


def to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        # (date, PayGrid) → {effective_date, rates} object so JS can round-trip it.
        if len(obj) == 2 and isinstance(obj[0], date) and isinstance(obj[1], PayGrid):
            return {"effective_date": obj[0].isoformat(), "rates": to_jsonable(obj[1].rates)}
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {_key(k): to_jsonable(v) for k, v in obj.items()}
    return obj


def _key(k: Any) -> str:
    if isinstance(k, tuple):
        return "|".join(str(x) for x in k)
    return str(k)
