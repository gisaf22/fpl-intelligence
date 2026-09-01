"""Integration tests for the evaluation orchestration -- `METRIC.md` §1 end to end.

Kept in its own file, entirely marked `integration`, rather than mixed into `test_evaluate.py`
with a per-function `@pytest.mark.integration`: a module-level `pytestmark = pytest.mark.unit`
plus a per-function `integration` mark both apply to that function, so `pytest -m unit` (what CI's
unit-test job actually runs, against a fixture DB with no live mart) would still collect and try
to run it. This file requires `~/.fpl/fpl.db` and is excluded from that job by carrying only the
`integration` mark.

The end-to-end pass runs over a **gameweek-truncated slice** of the live mart rather than the full
season. `evaluate` derives its own gameweek set from the mart it is handed, so truncating the mart
is the supported way to run a subset -- and it keeps this file at a few seconds rather than the
full-season replay, while still exercising real prices, real registrations and real points.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.pipeline import load
from decisions.free_hit.evaluate import POLICIES, build, evaluate
from decisions.free_hit.gameweek_population import WARM_UP_EXCLUDED, qualifying_gameweeks
from domain.fpl_squad import SQUAD_SIZE

pytestmark = pytest.mark.integration

_SUBSET_LAST_GW = 8
"""Truncate at GW8: past GW5, where `METRIC.md` §3.3 measures C1's and C3's signals as first
diverging, so the subset is not silently inside the collinear stretch."""


@pytest.fixture(scope="module")
def live_mart() -> pd.DataFrame:
    return load().mart


@pytest.fixture(scope="module")
def subset(live_mart: pd.DataFrame) -> pd.DataFrame:
    return live_mart.loc[live_mart["gw"] <= _SUBSET_LAST_GW].copy()


def test_the_pipeline_runs_end_to_end_on_a_real_gameweek_subset(subset: pd.DataFrame) -> None:
    result = evaluate(subset)
    gameweeks = sorted(qualifying_gameweeks(subset))

    assert gameweeks, "the subset must contain at least one qualifying gameweek"
    assert 1 not in gameweeks  # METRIC.md §3.3
    assert len(result.squads) == len(POLICIES) * len(gameweeks) * SQUAD_SIZE
    assert len(result.squad_weeks) == len(POLICIES) * len(gameweeks)
    assert len(result.construction_regret) == len(POLICIES) * (len(POLICIES) - 1) * len(gameweeks)


def test_the_real_subset_output_is_not_degenerate(subset: pd.DataFrame) -> None:
    """Non-degeneracy, stated as the properties GW1 fails, so this test is the positive image of
    `test_evaluate.py::test_gw1_would_be_degenerate_if_it_were_run`."""
    result = evaluate(subset)

    # Real points were scored, and the three policies did not all pick the same squad.
    assert (result.squad_weeks["chosen_xi_points"] > 0).all()
    per_gw_squads = result.squads.groupby("gw")["squad_id"].nunique()
    assert (per_gw_squads == len(POLICIES)).all()
    distinct = result.squads.groupby(["squad_id", "gw"])["player_id"].apply(frozenset).groupby("gw").nunique()
    assert (distinct > 1).all(), "every policy returned the same squad at some gameweek"

    # Construction regret carries real, signed variation -- not a column of zeros.
    regret = result.construction_regret["construction_regret"]
    assert (regret != 0).any()
    assert (regret > 0).any() and (regret < 0).any()
    assert regret.std() > 0

    # Selection regret is non-negative and non-trivial (METRIC.md §1.2's bound, on real data).
    assert (result.selection_regret["selection_regret"] >= 0).all()
    assert (result.selection_regret["selection_regret"] > 0).any()


def test_the_full_run_excludes_the_warm_up_gameweek_and_keeps_thirty_two(live_mart: pd.DataFrame) -> None:
    """`METRIC.md` §3.3's resolution against the live mart, at the grain the figures were measured
    at: 33 schedule-clean gameweeks less GW1. Pinned so a future change cannot put the
    guaranteed-zero observation back without failing here."""
    qualifying = qualifying_gameweeks(live_mart)
    assert WARM_UP_EXCLUDED == frozenset({1})
    assert len(qualifying) == 32
    assert 1 not in qualifying


def test_the_reported_construction_regret_means_are_reproduced() -> None:
    """The three mean pairwise series `METRIC.md` §3.3 cites for the post-exclusion run, over the
    full live mart via `build` -- the same entry point a caller uses, `DB_PATH` and all.

    Pinned to the **exact** means rather than to §3.3's 2dp prose figures. The C2-C3 mean is
    -100/32 = -3.125 exactly, a rounding tie: §3.3 writes -3.13 (half away from zero) while
    `numpy.round` gives -3.12 (half to even). Asserting the exact value sidesteps a tie-break
    convention that has nothing to do with what this test is guarding -- a silent drift in the
    population, the ranker or the policies, which must show up here rather than as a document
    that has quietly stopped describing the code.
    """
    result = build()
    means = result.construction_regret.groupby(["policy_c", "policy_b"])["construction_regret"].mean()

    assert means[("C1_season_ppg", "C2_value")] == pytest.approx(263 / 32)  # 8.21875 -> +8.22
    assert means[("C1_season_ppg", "C3_recent_form")] == pytest.approx(163 / 32)  # 5.09375 -> +5.09
    assert means[("C2_value", "C3_recent_form")] == pytest.approx(-100 / 32)  # -3.125 -> -3.13
    assert result.construction_regret["gw"].nunique() == 32


def test_c1_and_c3_are_collinear_until_gw5_on_the_live_mart(live_mart: pd.DataFrame) -> None:
    """`METRIC.md` §3.3's GW2-GW4 finding, pinned as the reason those gameweeks are recorded as a
    constraint rather than excluded. If `candidates.RECENT_FORM_WINDOW` changes, the stretch moves
    and §3.3's "effective n = 29 for that pair" stops being true -- this test is what catches it."""
    from decisions.free_hit.candidates import RECENT_FORM_WINDOW, build_candidates

    assert RECENT_FORM_WINDOW == 3

    for gw in (2, 3, 4):
        pool = build_candidates(live_mart, gw)
        assert pool
        assert all(
            c.season_ppg == c.recent_form_ppg
            # NaN != NaN, so an unregistered-window pair must be matched as both-NaN.
            or (c.season_ppg != c.season_ppg and c.recent_form_ppg != c.recent_form_ppg)
            for c in pool
        ), f"C1 and C3 signals were expected to be identical at GW{gw}"

    diverged = build_candidates(live_mart, RECENT_FORM_WINDOW + 2)
    assert any(c.season_ppg != c.recent_form_ppg for c in diverged), "C1 and C3 must diverge by GW5"
