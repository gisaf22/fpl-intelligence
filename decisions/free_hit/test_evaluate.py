"""Unit tests for the evaluation orchestration -- `METRIC.md` §1 over `DESIGN.md` §2's gameweeks.

Everything here runs against a synthetic mart, never the live DB. `test_evaluate_integration.py`
carries the live-mart pass in its own integration-only file, following the split
`test_candidates.py`, `test_gameweek_population.py` and `decisions/starting_xi`'s own test files
all state and keep: a module-level `pytestmark = pytest.mark.unit` plus a per-function
`@pytest.mark.integration` both apply to that function at once, so `pytest -m unit` (what CI
actually runs, against a fixture DB with no live mart) would still collect and try to run it.

**What is tested here that is not tested through `candidates.py` or `harness.py`.** This module's
own job is projection and arithmetic, not construction or replay:

* `build_squads` -- the list-of-candidates -> (`squad_id`, `gw`, `player_id`) frame projection.
* `rank_season_ppg` -- the locally re-derived Tier A ranker, checked both numerically and, in a
  clean subprocess, for the `model/` fan-out it exists to avoid.
* `selection_regret` / `construction_regret` -- `METRIC.md` §1.2/§1.3/§1.4's series, checked as
  algebra against a hand-built `squad_weeks` frame. Building that frame by hand rather than
  running the harness is deliberate: the identity under test is a property of these two functions,
  and driving it through the harness would let a harness change mask a defect here.
* The warm-up exclusion -- pinned so a future change cannot silently put GW1 back in the run.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from decisions.free_hit.candidates import build_candidates, greedy_by_season_ppg, greedy_by_value
from decisions.free_hit.evaluate import (
    LOCAL_SEASON_PPG,
    POLICIES,
    STUDY_WINDOW,
    build_squads,
    construction_regret,
    evaluate,
    rank_season_ppg,
    selection_regret,
)
from decisions.free_hit.gameweek_population import WARM_UP_EXCLUDED, qualifying_gameweeks
from domain.fpl_squad import BUDGET_CAP_TENTHS, SQUAD_SELECT, SQUAD_SIZE

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mart(gws: range) -> pd.DataFrame:
    """65 players (10 GK / 20 DEF / 20 MID / 15 FWD) over `gws`, spread over 10 clubs.

    Deliberately close to `test_candidates.py`'s own `mart` fixture -- same counts, same club
    assignment, same price band -- with two additions this module needs and that one does not:
    `fixture_count`, which `gameweek_population.qualifying_gameweeks` classifies on, and a range
    long enough for C1's expanding window and C3's rolling window to diverge (`METRIC.md` §3.3:
    not before GW5). Every player debuts at GW1 so that `fixture_count` is the only thing deciding
    which gameweeks qualify -- registration filtering is `test_candidates.py`'s subject, not this
    module's.
    """
    rng = np.random.default_rng(11)
    counts = {"GK": 10, "DEF": 20, "MID": 20, "FWD": 15}
    rows = []
    player_id = 0
    for position, n in counts.items():
        for _ in range(n):
            player_id += 1
            price = float(np.round(rng.uniform(4.0, 12.0), 1))
            for gw in gws:
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "position": position,
                        "purchase_price": price,
                        "team_id": (player_id % 10) + 1,
                        "fixture_count": 1,
                        "minutes": 90,
                        "total_points": int(rng.integers(0, 12)),
                        # C4's fdr term needs a rating; integer 1-5, as the live mart carries.
                        "fdr_avg": float(((player_id + gw) % 5) + 1),
                        # C5's two new terms (`DESIGN.MD` §8.2), both read straight off the
                        # governed mart rather than derived in `candidates.py`. `transfers_in`
                        # is `never_null` at this grain and deliberately spans several orders of
                        # magnitude, matching the live column's shape that §8.3 cites as making
                        # rank normalization non-negotiable.
                        "transfers_in": float(10 ** ((player_id % 5) + 1) + gw),
                    }
                )
    mart = pd.DataFrame(rows)
    mart["minutes"] = mart["minutes"].astype("Int64")
    mart["total_points"] = mart["total_points"].astype("Int64")
    # `minutes_roll3` mirrors the governed FEAT column's construction exactly
    # (`dal/feat/feat_player_gameweek.py:98-101`): lag-1 then a 3-gameweek rolling mean, so a
    # player's first row is NaN and lands in `_sort_key`'s unrankable tier -- the structural
    # cold-start §8.2 measures at 2.827% on the live mart.
    mart["minutes_roll3"] = (
        mart.sort_values(["player_id", "gw"])
        .groupby("player_id")["minutes"]
        .transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        .astype("float64")
    )
    return mart


@pytest.fixture
def mart() -> pd.DataFrame:
    return _mart(range(1, 9))


@pytest.fixture
def squad_weeks() -> pd.DataFrame:
    """A hand-built `squad_weeks` frame in the harness's own T2 shape (`harness.py` §7.2).

    Only the five columns `selection_regret` and `construction_regret` read are populated. `regret`
    carries the harness's own definition -- `best_legal_xi_points - chosen_xi_points`, floored at
    zero (`harness.py`'s `max(regret, 0.0)`) -- rather than an independently invented number, since
    §1.2 defines `SelectionRegret` as exactly that quantity.

    The oracles deliberately differ across policies within a gameweek: a frame where every squad
    shares one oracle would satisfy §1.3's identity trivially, since the `Oracle_C - Oracle_B` term
    would vanish.
    """
    rows = [
        # gw, policy, oracle, harness points
        (2, "C1_season_ppg", 61.0, 55.0),
        (2, "C2_value", 58.0, 49.0),
        (2, "C3_recent_form", 61.0, 61.0),  # a zero-regret squad-week: the floor's boundary
        (3, "C1_season_ppg", 44.0, 40.0),
        (3, "C2_value", 71.0, 62.0),
        (3, "C3_recent_form", 50.0, 33.0),
    ]
    return pd.DataFrame(
        [
            {
                "squad_id": policy,
                "gw": gw,
                "ranker": LOCAL_SEASON_PPG,
                "chosen_xi_points": chosen,
                "best_legal_xi_points": oracle,
                "regret": max(oracle - chosen, 0.0),
            }
            for gw, policy, oracle, chosen in rows
        ]
    )


# ---------------------------------------------------------------------------
# build_squads -- the projection, and nothing more
# ---------------------------------------------------------------------------


def test_build_squads_emits_fifteen_rows_per_policy_gameweek(mart: pd.DataFrame) -> None:
    gameweeks = [2, 3, 4]
    squads = build_squads(mart, gameweeks)

    assert list(squads.columns) == ["squad_id", "gw", "player_id"]
    assert len(squads) == len(POLICIES) * len(gameweeks) * SQUAD_SIZE
    per_squad = squads.groupby(["squad_id", "gw"]).size()
    assert (per_squad == SQUAD_SIZE).all()
    assert set(squads["squad_id"]) == set(POLICIES)
    assert sorted(squads["gw"].unique()) == gameweeks


def test_build_squads_reproduces_each_policys_own_output(mart: pd.DataFrame) -> None:
    """The projection must carry the policy's squad through unchanged -- `build_squads` is the
    reshaping step `evaluate.py`'s docstring point 1 names, not a second selection step."""
    squads = build_squads(mart, [4])
    pool = build_candidates(mart, 4)

    for name, policy in POLICIES.items():
        expected = sorted(c.player_id for c in policy(pool, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT)))
        projected = sorted(squads.loc[squads["squad_id"] == name, "player_id"])
        assert projected == expected, name


def test_build_squads_does_not_depend_on_the_policy_mapping_order(mart: pd.DataFrame) -> None:
    """`POLICIES`'s docstring claims insertion order does not leak into the output. Executed."""
    reversed_policies = dict(reversed(list(POLICIES.items())))
    assert list(reversed_policies) != list(POLICIES)

    first = build_squads(mart, [3, 2], POLICIES)
    second = build_squads(mart, [2, 3], reversed_policies)
    pd.testing.assert_frame_equal(first, second)


def test_build_squads_is_deterministic(mart: pd.DataFrame) -> None:
    """The module docstring's "no RNG anywhere" claim, executed for the one function that loops."""
    pd.testing.assert_frame_equal(build_squads(mart, [2, 5]), build_squads(mart, [2, 5]))


def test_build_squads_shares_one_candidate_pool_across_the_three_policies(mart: pd.DataFrame) -> None:
    """Every player any policy picks at a gameweek must come from that gameweek's own pool --
    the sharing `build_squads`'s docstring describes, checked as a containment rather than by
    counting calls."""
    squads = build_squads(mart, [6])
    pool_ids = {c.player_id for c in build_candidates(mart, 6)}
    assert set(squads["player_id"]) <= pool_ids


# ---------------------------------------------------------------------------
# rank_season_ppg -- the local Tier A ranker
# ---------------------------------------------------------------------------


def test_rank_season_ppg_is_the_lag_one_expanding_mean() -> None:
    """Hand-computed, not compared against another implementation of the same formula."""
    mart = pd.DataFrame(
        {
            "player_id": [7, 7, 7, 7],
            "gw": [1, 2, 3, 4],
            "total_points": [2, 8, 5, 1],
        }
    )
    scores = rank_season_ppg(mart).scores.sort_values("gw")["score"].tolist()

    assert pd.isna(scores[0])  # no prior row at GW1
    assert scores[1] == 2.0  # mean(2)
    assert scores[2] == 5.0  # mean(2, 8)
    assert scores[3] == 5.0  # mean(2, 8, 5)


def test_rank_season_ppg_never_reads_a_gameweeks_own_outcome() -> None:
    """The lag-1 property, executed as a counterfactual: rewriting the *last* gameweek's points
    must leave every score untouched, because no score may depend on its own row."""
    mart = pd.DataFrame({"player_id": [7] * 4, "gw": [1, 2, 3, 4], "total_points": [2, 8, 5, 1]})
    tampered = mart.copy()
    tampered.loc[tampered["gw"] == 4, "total_points"] = 99

    pd.testing.assert_frame_equal(
        rank_season_ppg(mart).scores.reset_index(drop=True),
        rank_season_ppg(tampered).scores.reset_index(drop=True),
    )


def test_rank_season_ppg_scores_players_independently() -> None:
    mart = pd.DataFrame(
        {
            "player_id": [1, 1, 2, 2],
            "gw": [1, 2, 1, 2],
            "total_points": [10, 0, 0, 0],
        }
    )
    scores = rank_season_ppg(mart).scores.set_index(["player_id", "gw"])["score"]
    assert scores[(1, 2)] == 10.0
    assert scores[(2, 2)] == 0.0


def test_rank_season_ppg_reports_the_study_window_and_a_distinct_name() -> None:
    """`LOCAL_SEASON_PPG`'s docstring: the name must not collide with `rankers.F2_SEASON_PPG`,
    which is frozen in `decisions/starting_xi/PRE_REGISTRATION.yaml` against a different module."""
    output = rank_season_ppg(pd.DataFrame({"player_id": [1], "gw": [1], "total_points": [3]}))
    assert output.window == STUDY_WINDOW
    assert output.name == LOCAL_SEASON_PPG
    assert output.name != "F2_season_ppg"
    assert list(output.scores.columns) == ["player_id", "gw", "score"]


def test_the_import_closure_is_tier_a() -> None:
    """`DESIGN.md` §4's Tier A property and this module's stated reason for re-deriving the ranker:
    importing it must not pull in `model/`, which `decisions.starting_xi.rankers` would.

    Run as a subprocess, for the reason `decisions/starting_xi/test_rankers.py`'s equivalent gives:
    `pyproject.toml`'s `testpaths` imports `model` before any test here runs, so an in-process
    `sys.modules` check would pass against any module at all. `.importlinter` cannot cover this
    yet -- no contract names `decisions.free_hit.*` (`DESIGN.md` §4 defers that to its own
    falsify-then-revert commit) -- so this test is the only thing holding the property.
    """
    program = (
        "import sys;"
        "import decisions.free_hit.evaluate;"
        "banned = ('model', 'research', 'serve', 'operational');"
        "reached = sorted(m for m in sys.modules if m.split('.')[0] in banned);"
        "print(repr(reached));"
        "print('decisions.starting_xi.harness' in sys.modules);"
        "print('decisions.starting_xi.rankers' in sys.modules)"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    reached, harness_imported, rankers_imported = child.stdout.splitlines()
    assert reached == "[]"
    # The positive half: the harness edge this module exists to use IS taken, and the Tier B
    # ranker module it deliberately does not use is NOT.
    assert harness_imported == "True"
    assert rankers_imported == "False"


# ---------------------------------------------------------------------------
# METRIC.md §1.2 -- selection regret
# ---------------------------------------------------------------------------


def test_selection_regret_renames_the_harnesss_own_columns(squad_weeks: pd.DataFrame) -> None:
    """§1.2 is a projection, not a recomputation -- the values must be the harness's, unaltered."""
    result = selection_regret(squad_weeks)

    assert list(result.columns) == ["policy", "gw", "oracle", "harness", "selection_regret"]
    merged = result.merge(squad_weeks, left_on=["policy", "gw"], right_on=["squad_id", "gw"])
    assert (merged["oracle"] == merged["best_legal_xi_points"]).all()
    assert (merged["harness"] == merged["chosen_xi_points"]).all()
    assert (merged["selection_regret"] == merged["regret"]).all()


def test_selection_regret_is_never_negative(squad_weeks: pd.DataFrame) -> None:
    """§1.2's stated lower bound. It holds because the oracle is the *best* legal XI over the same
    15 players the harness chose from, so it cannot be beaten by the chosen XI."""
    result = selection_regret(squad_weeks)
    assert (result["selection_regret"] >= 0).all()
    assert (result["selection_regret"] == result["oracle"] - result["harness"]).all()
    assert (result["selection_regret"] == 0).any()  # the boundary is reachable, not merely allowed


def test_selection_regret_is_one_row_per_policy_gameweek(squad_weeks: pd.DataFrame) -> None:
    result = selection_regret(squad_weeks)
    assert len(result) == len(squad_weeks)
    assert not result.duplicated(subset=["policy", "gw"]).any()
    assert result[["policy", "gw"]].equals(result[["policy", "gw"]].sort_values(["policy", "gw"]))


# ---------------------------------------------------------------------------
# METRIC.md §1.3 / §1.4 -- construction regret
# ---------------------------------------------------------------------------


def test_construction_regret_emits_every_ordered_pair_and_no_self_pair(squad_weeks: pd.DataFrame) -> None:
    """§1.3's quantity is signed and directional, so `(C1, C2)` and `(C2, C1)` are both emitted --
    `DECISION.md` §4 forbids collapsing them to an upper triangle."""
    result = construction_regret(squad_weeks)
    policies = sorted(set(squad_weeks["squad_id"]))
    gameweeks = sorted(set(squad_weeks["gw"]))

    assert len(result) == len(policies) * (len(policies) - 1) * len(gameweeks)
    assert not (result["policy_c"] == result["policy_b"]).any()
    assert set(map(tuple, result[["policy_c", "policy_b"]].to_numpy())) == {
        (c, b) for c in policies for b in policies if c != b
    }


def test_construction_regret_is_antisymmetric(squad_weeks: pd.DataFrame) -> None:
    """Reversing the pair must negate the quantity exactly -- the property that makes the two
    directional readings of one comparison consistent rather than two independent numbers."""
    result = construction_regret(squad_weeks)
    forward = result.set_index(["policy_c", "policy_b", "gw"])["construction_regret"]
    reverse = result.set_index(["policy_b", "policy_c", "gw"])["construction_regret"]

    assert (forward + reverse.reindex(forward.index) == 0).all()


def test_construction_regret_decomposes_into_oracle_and_selection_terms(squad_weeks: pd.DataFrame) -> None:
    """The identity tying §1.3 to §1.2:

        ConstructionRegret_{C,B}(g) = (Oracle_C - Oracle_B) - (SelectionRegret_C - SelectionRegret_B)

    It holds because both sides reduce to `Harness_C - Harness_B`, and it is worth pinning because
    it is the reason §1.3 can be computed from harness points alone without ever recomputing an
    oracle: any future "optimisation" that recomputed one would have to preserve this.
    """
    construction = construction_regret(squad_weeks)
    selection = selection_regret(squad_weeks).set_index(["policy", "gw"])

    for row in construction.itertuples(index=False):
        c = selection.loc[(row.policy_c, row.gw)]
        b = selection.loc[(row.policy_b, row.gw)]
        decomposed = (c["oracle"] - b["oracle"]) - (c["selection_regret"] - b["selection_regret"])
        assert decomposed == pytest.approx(row.construction_regret), (row.policy_c, row.policy_b, row.gw)


def test_combined_regret_is_the_same_column_not_a_second_computation(squad_weeks: pd.DataFrame) -> None:
    """§1.4 resolves Combined regret to the same computed quantity under a second framing;
    emitting two independently-computed numbers would assert a distinction §1.4 says is absent."""
    result = construction_regret(squad_weeks)
    assert (result["combined_regret"] == result["construction_regret"]).all()
    assert (result["construction_regret"] == result["harness_c"] - result["harness_b"]).all()


def test_construction_regret_skips_a_pair_a_gameweek_does_not_carry(squad_weeks: pd.DataFrame) -> None:
    """The guard in the comprehension, executed: a policy missing at one gameweek must drop that
    gameweek's pairs rather than raise a KeyError or fabricate a zero."""
    partial = squad_weeks.loc[~((squad_weeks["squad_id"] == "C2_value") & (squad_weeks["gw"] == 3))]
    result = construction_regret(partial)

    at_gw3 = result.loc[result["gw"] == 3]
    assert not (at_gw3[["policy_c", "policy_b"]] == "C2_value").any().any()
    assert len(at_gw3) == 2  # C1<->C3 only
    assert len(result.loc[result["gw"] == 2]) == 6


# ---------------------------------------------------------------------------
# METRIC.md §3.3 -- the warm-up exclusion, pinned against silent reintroduction
# ---------------------------------------------------------------------------


def test_evaluate_does_not_run_the_warm_up_gameweek(mart: pd.DataFrame) -> None:
    """`METRIC.md` §3.3's resolution, as a regression test.

    The fixture mart has clean `fixture_count == 1` everywhere, so GW1 is schedule-clean and only
    the warm-up axis can remove it. Every frame `evaluate` emits must be free of it -- if a future
    change reverts `WARM_UP_EXCLUDED` or bypasses `qualifying_gameweeks`, the guaranteed-zero,
    zero-variance observation §3.3 excludes comes straight back and this test is what notices.
    """
    assert 1 in qualifying_gameweeks(mart) | WARM_UP_EXCLUDED  # schedule-clean in this fixture
    assert 1 not in qualifying_gameweeks(mart)

    result = evaluate(mart)
    for frame, column in (
        (result.squads, "gw"),
        (result.squad_weeks, "gw"),
        (result.selection_regret, "gw"),
        (result.construction_regret, "gw"),
    ):
        assert set(WARM_UP_EXCLUDED).isdisjoint(set(frame[column])), frame.columns.tolist()


def test_the_study_window_starts_after_every_excluded_warm_up_gameweek() -> None:
    """The ranker's declared window and the population must not drift apart: `harness.run` only
    raises when a *narrower* declaration is asked to cover a wider run, so a window that reached
    back into an excluded gameweek would fail silently rather than loudly."""
    assert STUDY_WINDOW[0] > max(WARM_UP_EXCLUDED)
    assert STUDY_WINDOW[0] == max(WARM_UP_EXCLUDED) + 1  # no gap: nothing beyond §3.3 is dropped
    assert STUDY_WINDOW == (2, 38)


def test_gw1_would_be_degenerate_if_it_were_run(mart: pd.DataFrame) -> None:
    """The counterfactual §3.3's resolution rests on, executed rather than asserted.

    At GW1 every `shift(1)`-derived signal is NaN, so the greedy fill falls through to its
    ascending-`player_id` tie-break and two policies ranking on *different* signals return the
    identical squad -- which is what makes every pairwise `ConstructionRegret_{C,B}(1)` a
    guaranteed zero rather than an observed one.
    """
    pool = build_candidates(mart, 1)
    assert all(c.season_ppg != c.season_ppg for c in pool)  # NaN != NaN, all of them

    by_ppg = greedy_by_season_ppg(pool, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    by_value = greedy_by_value(pool, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    assert sorted(c.player_id for c in by_ppg) == sorted(c.player_id for c in by_value)

    # ...and the same two policies do NOT agree once the signals are defined and distinct.
    later = build_candidates(mart, 6)
    assert sorted(c.player_id for c in greedy_by_season_ppg(later, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))) != sorted(
        c.player_id for c in greedy_by_value(later, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    )


# ---------------------------------------------------------------------------
# End to end, on synthetic data
# ---------------------------------------------------------------------------


def test_evaluate_assembles_all_four_frames_at_the_right_grains(mart: pd.DataFrame) -> None:
    result = evaluate(mart)
    gameweeks = sorted(qualifying_gameweeks(mart))

    assert len(result.squads) == len(POLICIES) * len(gameweeks) * SQUAD_SIZE
    assert len(result.squad_weeks) == len(POLICIES) * len(gameweeks)
    assert len(result.selection_regret) == len(POLICIES) * len(gameweeks)
    assert len(result.construction_regret) == len(POLICIES) * (len(POLICIES) - 1) * len(gameweeks)
    assert set(result.squad_weeks["ranker"]) == {LOCAL_SEASON_PPG}


def test_evaluate_is_deterministic(mart: pd.DataFrame) -> None:
    first, second = evaluate(mart), evaluate(mart)
    pd.testing.assert_frame_equal(first.construction_regret, second.construction_regret)
    pd.testing.assert_frame_equal(first.selection_regret, second.selection_regret)
