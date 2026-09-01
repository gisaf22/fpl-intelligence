"""Integration test for the gameweek population utility -- `DESIGN.md` §2.

Kept in its own file, entirely marked `integration`, rather than mixed into
`test_gameweek_population.py` with a per-function `@pytest.mark.integration`: a module-level
`pytestmark = pytest.mark.unit` plus a per-function `integration` mark both apply to that
function, so `pytest -m unit` (what CI's unit-test job actually runs, against a fixture DB with
no live mart) would still collect and try to run it. This file requires `~/.fpl/fpl.db` and is
excluded from that job by carrying only the `integration` mark.
"""

from __future__ import annotations

import pytest

from dal.pipeline import load
from decisions.free_hit.gameweek_population import (
    WARM_UP_EXCLUDED,
    qualifying_gameweeks,
    schedule_clean_gameweeks,
)

pytestmark = pytest.mark.integration


def test_schedule_axis_matches_the_known_anomaly_list_on_the_live_mart() -> None:
    live_mart = load().mart
    schedule_clean = schedule_clean_gameweeks(live_mart)
    all_gws = frozenset(int(gw) for gw in live_mart["gw"].unique())
    assert all_gws - schedule_clean == frozenset({26, 31, 33, 34, 36})  # DESIGN.md §2 / INVENTORY.md §1
    assert len(schedule_clean) == 33


def test_qualifying_drops_the_warm_up_gameweek_on_the_live_mart() -> None:
    """`METRIC.md` §3.3's second axis, pinned separately from §3.2's above."""
    live_mart = load().mart
    qualifying = qualifying_gameweeks(live_mart)
    assert WARM_UP_EXCLUDED == frozenset({1})
    assert 1 not in qualifying
    assert qualifying == schedule_clean_gameweeks(live_mart) - frozenset({1})
    assert len(qualifying) == 32
