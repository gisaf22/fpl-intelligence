"""Integration tests for the naive greedy construction candidates -- `DESIGN.md` §4.

Kept in its own file, entirely marked `integration`, rather than mixed into
`test_candidates.py` with a per-function `@pytest.mark.integration`: a module-level
`pytestmark = pytest.mark.unit` plus a per-function `integration` mark both apply to that
function, so `pytest -m unit` (what CI's unit-test job actually runs, against a fixture DB with
no live mart) would still collect and try to run it. This file requires `~/.fpl/fpl.db` and is
excluded from that job by carrying only the `integration` mark.
"""

from __future__ import annotations

import pytest

from decisions.free_hit.candidates import ConstructionPolicy, build_candidates
from decisions.free_hit.gameweek_population import qualifying_gameweeks
from decisions.free_hit.test_candidates import POLICIES, _is_legal_squad
from domain.fpl_squad import BUDGET_CAP_TENTHS, SQUAD_SELECT

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_produces_a_legal_squad_at_every_qualifying_gameweek(policy: ConstructionPolicy) -> None:
    from dal.pipeline import load

    live_mart = load().mart
    qualifying = qualifying_gameweeks(live_mart)
    assert len(qualifying) == 33  # DESIGN.md §2 / INVENTORY.md §1's cited figure

    for gw in sorted(qualifying):
        candidates = build_candidates(live_mart, gw)
        squad = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
        _is_legal_squad(squad)
