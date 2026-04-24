"""Deterministic JSON-safe serialization for engine dataclasses.

Used by the fixture exporter and the drift test. Decimal becomes a string
to preserve precision for the JS engine comparison (SPEC §2.2).
"""
from __future__ import annotations

from dataclasses import is_dataclass, fields
from datetime import date
from decimal import Decimal
from typing import Any


def to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {_key(k): to_jsonable(v) for k, v in obj.items()}
    return obj


def _key(k: Any) -> str:
    if isinstance(k, tuple):
        return "|".join(str(x) for x in k)
    return str(k)
