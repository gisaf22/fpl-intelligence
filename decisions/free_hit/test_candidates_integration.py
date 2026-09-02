"""Integration tests for the naive greedy construction candidates -- `DESIGN.md` §4.

Kept in its own file, entirely marked `integration`, rather than mixed into
`test_candidates.py` with a per-function `@pytest.mark.integration`: a module-level
`pytestmark = pytest.mark.unit` plus a per-function `integration` mark both apply to that
function, so `pytest -m unit` (what CI's unit-test job actually runs, against a fixture DB with
no live mart) would still collect and try to run it. This file requires `~/.fpl/fpl.db` and is
excluded from that job by carrying only the `integration` mark.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.pipeline import load
from decisions.free_hit.candidates import (
    ConstructionCandidate,
    ConstructionPolicy,
    build_candidates,
    derive_signals,
)
from decisions.free_hit.gameweek_population import qualifying_gameweeks
from decisions.free_hit.test_candidates import POLICIES, _is_legal_squad
from domain.fpl_squad import BUDGET_CAP_TENTHS, SQUAD_SELECT

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_mart() -> pd.DataFrame:
    return load().mart


@pytest.fixture(scope="module")
def pools(live_mart: pd.DataFrame) -> dict[int, list[ConstructionCandidate]]:
    """Every qualifying gameweek's candidate pool, built once for the whole module.

    The pool is a property of the gameweek alone -- no policy influences it, which is exactly why
    `evaluate.build_squads` already shares one pool across all seven policies. Building it per
    parametrized policy instead meant 7 x 32 full-mart derivations for a set of 32 pools; the
    mart-wide pass is hoisted here for the same reason `build_squads` hoists it.
    """
    derived = derive_signals(live_mart)
    return {gw: build_candidates(live_mart, gw, derived=derived) for gw in sorted(qualifying_gameweeks(live_mart))}


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_produces_a_legal_squad_at_every_qualifying_gameweek(
    policy: ConstructionPolicy, pools: dict[int, list[ConstructionCandidate]]
) -> None:
    assert len(pools) == 32  # DESIGN.md §2 / INVENTORY.md §1's 33, less METRIC.md §3.3's GW1

    for gw in sorted(pools):
        squad = policy(pools[gw], BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
        _is_legal_squad(squad)


def test_the_two_new_c5_signals_hold_their_measured_nan_rates_on_the_live_mart(
    pools: dict[int, list[ConstructionCandidate]],
) -> None:
    """`DESIGN.MD` §8.2's NaN characterisation, re-measured at the eligible-candidate grain rather
    than assumed -- §8.6 explicitly leaves the observed count to this build pass.

    **Flagged deviation from §8.2's stated figure.** §8.2 cites `minutes_roll3` at **2.827%**,
    "five times C4's", ~22 rows per gameweek. Measured here through `build_candidates` it is
    **138/24,918 = 0.554%**, ~4.3 rows per gameweek -- i.e. *exactly* C4's points-term rate, not
    five times it. The gap is `build_candidates`'s registration filter: a player's first
    `minutes`-bearing row is also the first gameweek at which he is an eligible candidate, so the
    cold-start rows §8.2 counted are mostly filtered out before the composite ever sees them. The
    mechanism §8.2 describes is unchanged and the resolution is unchanged (NaN composite ->
    `_sort_key`'s unrankable tier); only the population estimate was pessimistic. Pinned here so
    the correction is a checked fact rather than a claim in prose.
    """
    assert len(pools) == 32

    total = 0
    transfers_in_nan = 0
    minutes_roll3_nan = 0
    for gw in sorted(pools):
        pool = pools[gw]
        total += len(pool)
        transfers_in_nan += sum(1 for c in pool if getattr(c, "transfers_in") != getattr(c, "transfers_in"))
        minutes_roll3_nan += sum(1 for c in pool if getattr(c, "minutes_roll3") != getattr(c, "minutes_roll3"))

    assert total == 24_918  # the same grain §7.7 measured C4's terms at
    assert transfers_in_nan == 0  # §8.2's 0.000%, and fct_contracts.py:237's `never_null`
    assert minutes_roll3_nan == 138  # 0.554%, not §8.2's 2.827% -- see this test's docstring


def test_minutes_roll3_is_the_governed_column_not_a_local_re_derivation(live_mart: pd.DataFrame) -> None:
    """§8.6's Tier A claim, checked rather than assumed: `minutes_roll3` reaches the candidate
    unchanged from `dal/feat/feat_player_gameweek.py`'s governed output, so C5 takes no local
    re-derivation of the kind C4's points terms needed to dodge `model/eval`'s fan-out (§4)."""
    assert "minutes_roll3" in live_mart.columns
    assert "transfers_in" in live_mart.columns

    gw = 20
    week = live_mart.loc[live_mart["gw"] == gw].set_index("player_id")
    pool = build_candidates(live_mart, gw)
    assert pool
    for candidate in pool:
        row = week.loc[candidate.player_id]
        got = getattr(candidate, "minutes_roll3")
        expected = float(row["minutes_roll3"])
        assert got == expected or (got != got and expected != expected)
        assert getattr(candidate, "transfers_in") == float(row["transfers_in"])
