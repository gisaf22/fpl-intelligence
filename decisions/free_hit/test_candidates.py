"""Tests for the naive greedy construction candidates -- `DESIGN.md` §4.

Builds a small synthetic mart (mirroring `decisions/starting_xi/test_sampler.py`'s `_mart`
helper) so registration filtering, NaN-score handling, and the infeasibility exception are
exercised without the live DB. `test_candidates_integration.py` runs all three policies against
the real mart across every one of `DESIGN.md` §2's 33 qualifying gameweeks, in its own
integration-only file -- `decisions/starting_xi`'s own unit test files never touch the live DB,
for the same reason this pass keeps that split as a separate file rather than a mixed marker on
one: a module-level `pytestmark = pytest.mark.unit` plus a per-function
`@pytest.mark.integration` both apply to that function at once, so `pytest -m unit` (what CI
actually runs) would still collect and run it.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from decisions.free_hit.candidates import (
    ConstructionCandidate,
    ConstructionPolicy,
    InfeasibleGameweek,
    build_candidates,
    greedy_by_recent_form,
    greedy_by_season_ppg,
    greedy_by_value,
)
from domain.fpl_squad import BUDGET_CAP_TENTHS, MAX_PER_CLUB, SQUAD_SELECT, SQUAD_SIZE

pytestmark = pytest.mark.unit

POLICIES = (greedy_by_season_ppg, greedy_by_value, greedy_by_recent_form)


def _mart(
    counts: dict[str, int],
    gws: range,
    prices: dict[tuple[str, int], float],
    debuts: dict[tuple[str, int], int],
    points: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    player_id = 0
    for position, n in counts.items():
        for slot in range(n):
            player_id += 1
            debut = debuts[(position, slot)]
            for gw in gws:
                played = gw >= debut
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "position": position,
                        "purchase_price": prices[(position, slot)],
                        "team_id": (player_id % 10) + 1,
                        "minutes": 90 if played else None,
                        "total_points": int(points.integers(0, 12)) if played else None,
                    }
                )
    mart = pd.DataFrame(rows)
    mart["minutes"] = mart["minutes"].astype("Int64")
    mart["total_points"] = mart["total_points"].astype("Int64")
    return mart


@pytest.fixture
def mart() -> pd.DataFrame:
    """65 players (10 GK / 20 DEF / 20 MID / 15 FWD) over GW1-5, spread over 10 clubs. Every 4th
    slot debuts at GW3 instead of GW1, so registration filtering has something to exclude."""
    rng = np.random.default_rng(5)
    counts = {"GK": 10, "DEF": 20, "MID": 20, "FWD": 15}
    prices = {
        (position, slot): float(np.round(rng.uniform(4.0, 12.0), 1))
        for position, n in counts.items()
        for slot in range(n)
    }
    debuts = {(position, slot): (3 if slot % 4 == 0 else 1) for position, n in counts.items() for slot in range(n)}
    return _mart(counts, range(1, 6), prices, debuts, rng)


def _is_legal_squad(squad: Sequence[ConstructionCandidate]) -> None:
    assert len(squad) == SQUAD_SIZE
    assert len({c.player_id for c in squad}) == SQUAD_SIZE

    position_counts: dict[str, int] = {}
    club_counts: dict[int, int] = {}
    total_cost = 0
    for candidate in squad:
        position_counts[candidate.position] = position_counts.get(candidate.position, 0) + 1
        club_counts[candidate.team_id] = club_counts.get(candidate.team_id, 0) + 1
        total_cost += candidate.price_tenths

    assert position_counts == dict(SQUAD_SELECT)
    assert all(count <= MAX_PER_CLUB for count in club_counts.values())
    assert total_cost <= BUDGET_CAP_TENTHS


# ---------------------------------------------------------------------------
# Registration filtering
# ---------------------------------------------------------------------------


def test_a_not_yet_debuted_player_is_excluded_at_an_early_gameweek(mart: pd.DataFrame) -> None:
    total_players = mart["player_id"].nunique()
    candidates_gw1 = build_candidates(mart, gw=1)
    candidates_gw5 = build_candidates(mart, gw=5)
    assert len(candidates_gw1) < total_players  # the slot % 4 == 0 group hasn't debuted yet
    assert len(candidates_gw5) == total_players  # everyone has debuted by GW5


def test_every_candidate_carries_a_nan_score_before_a_policy_scores_it(mart: pd.DataFrame) -> None:
    for candidate in build_candidates(mart, gw=4):
        assert candidate.score != candidate.score  # NaN != NaN


def test_season_ppg_is_nan_for_every_candidate_at_gw1(mart: pd.DataFrame) -> None:
    """GW1 is the season's first row for every player -- `shift(1)` has nothing before it."""
    candidates = build_candidates(mart, gw=1)
    assert candidates  # some players are registered from GW1
    assert all(getattr(candidate, "season_ppg") != getattr(candidate, "season_ppg") for candidate in candidates)


# ---------------------------------------------------------------------------
# Each policy produces a legal squad
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_produces_a_legal_squad(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    squad = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    _is_legal_squad(squad)


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_still_produces_a_legal_squad_at_gw1_with_every_score_nan(
    policy: ConstructionPolicy, mart: pd.DataFrame
) -> None:
    """The degenerate case DECISION.md §4 names: at GW1 every PPG-derived signal is NaN for
    every player, so all three policies fall back to the tie-break order alone -- construction
    must still succeed."""
    candidates = build_candidates(mart, gw=1)
    squad = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    _is_legal_squad(squad)


# ---------------------------------------------------------------------------
# Infeasibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_an_impossibly_small_budget_raises_infeasible_gameweek(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(InfeasibleGameweek):
        policy(candidates, 1, dict(SQUAD_SELECT))


def test_an_impossible_quota_raises_infeasible_gameweek(mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(InfeasibleGameweek):
        greedy_by_season_ppg(candidates, BUDGET_CAP_TENTHS, {"GK": 99, "DEF": 5, "MID": 5, "FWD": 3})
