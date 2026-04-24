"""Drift guard: fixtures/scenarios.json must match the current engine output."""
import json
from pathlib import Path

from engine_py.export_fixtures import build_all_fixtures


_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios.json"


def test_fixtures_on_disk_match_current_engine():
    assert _FIXTURE_PATH.exists(), (
        f"{_FIXTURE_PATH} missing. Run: python -m engine_py.export_fixtures"
    )
    on_disk = json.loads(_FIXTURE_PATH.read_text())
    fresh = build_all_fixtures()
    assert on_disk == fresh, (
        "fixtures/scenarios.json is stale. Re-run: python -m engine_py.export_fixtures"
    )
