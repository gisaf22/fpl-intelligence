"""Tests for the three pre-registered floor rankers -- `DESIGN.md` §0.12, §6.1, §6.3, §6.4, §8.3.

The design supplies four references this suite executes rather than describes:

* **`METRIC.md` Appendix A.3's degeneracy is reproduced, not cited.** F2 and F3 are asserted
  identical for every player at GW2, GW3 and GW4 and asserted to diverge at GW5 -- the measurement
  §0.12 requires reported rather than designed away, and the property §8.3 explains (two windows
  over one population).
* **§6.4's `min_periods` selection is separated from its rejected alternative by running both.**
  The `min_periods = k` statistic is computed beside F3 on the same frame and asserted null exactly
  where F3 is a partial-window mean, so the test knows which convention it is pinning.
* **§8.3's silent-wrong-answer risk is computed alongside the right answer.** The
  appearance-denominated statistic -- the one a null left in place would produce -- is derived
  independently and asserted to differ from the gameweek-denominated one.
* **§8.3's coupling claim is checked across the module boundary §5.1 forces.** `rankers.py` may not
  import `harness.py`, so §0.9's population is built twice; F2 is asserted equal to
  `harness.as_of_points` wherever both are defined, and the one row where they deliberately differ
  is pinned rather than smoothed over.

Where a claim could pass by being blind -- the lag-1 property, the registration predicate, the
declared windows -- the wrong version is computed alongside the right one and asserted to differ.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi.harness import RankerOutput as HarnessRankerOutput
from decisions.starting_xi.harness import as_of_points
from decisions.starting_xi.harness import registration_gw as harness_registration_gw
from decisions.starting_xi.rankers import (
    DECLARED_WINDOWS,
    F1_P_PLAY,
    F2_SEASON_PPG,
    F3_FORM_ROLL3,
    FLOOR_RANKERS,
    P_PLAY_FIRST_GW,
    RECENT_FORM_WINDOW,
    STUDY_FIRST_GW,
    STUDY_LAST_GW,
    _assert_lag_safe,
    _assert_points_complete,
    population,
    rank_p_play,
    rank_recent_form,
    rank_season_ppg,
    registration_gw,
)
from decisions.starting_xi.sampler import _registration_gw
from model.eval.walkforward import WARMUP_GW

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# The PPG rankers read four columns (§8.3); F1 reads eight (`INVENTORY.md` §2.6). The narrow
# fixture is used wherever the wider one would only add noise.
_PPG_COLUMNS = ["player_id", "gw", "position", "minutes", "total_points"]


def _mart(rows: Sequence[tuple[int, int, str, float | None, float | None]]) -> pd.DataFrame:
    """A minimal mart at the PPG rankers' column set. `None` in either measure is a NULL row."""
    return pd.DataFrame(rows, columns=_PPG_COLUMNS).astype({"minutes": "Float64", "total_points": "Float64"})


def _p_play_mart(
    *,
    players_per_position: int = 30,
    last_gw: int = 9,
    late_debut_every: int = 11,
    dgw_at: int | None = None,
    blank_at: int | None = None,
    seed: int = 7,
) -> pd.DataFrame:
    """A mart wide enough for `PlayModel` to fit: the eight columns `INVENTORY.md` §2.6 measures.

    Sized against the model's own guards rather than by eye -- `min_train_rows = 50` per position
    and `_fit_predict`'s `dropna` over the lagged design, which removes each player's first row. At
    30 players a position the first predicted gameweek (GW4, `WARMUP_GW = 3`) trains on 60 rows.
    """
    rng = np.random.default_rng(seed)
    rows: list[tuple[int, int, str, float | None, float | None, float | None, bool]] = []
    player_id = 0
    for position in ("GK", "DEF", "MID", "FWD"):
        for _ in range(players_per_position):
            player_id += 1
            debut = 3 if player_id % late_debut_every == 0 else 1
            for gw in range(1, last_gw + 1):
                is_dgw = dgw_at is not None and gw == dgw_at
                if gw < debut or (blank_at is not None and gw == blank_at and player_id % 3 == 0):
                    rows.append((player_id, gw, position, None, None, None, is_dgw))
                    continue
                played = bool(rng.random() < 0.7)
                rows.append(
                    (
                        player_id,
                        gw,
                        position,
                        90.0 if played else 0.0,
                        float(rng.integers(0, 10)) if played else 0.0,
                        1.0 if played else 0.0,
                        is_dgw,
                    )
                )

    mart = pd.DataFrame(
        rows, columns=["player_id", "gw", "position", "minutes", "total_points", "starts", "is_dgw"]
    ).astype({"minutes": "Float64", "total_points": "Float64", "starts": "Float64"})
    minutes = mart.groupby("player_id")["minutes"]
    mart["minutes_roll3"] = minutes.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    mart["minutes_roll5"] = minutes.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    return mart


def _random_ppg_mart(*, players: int = 8, last_gw: int = 12, seed: int = 5) -> pd.DataFrame:
    """Late debuts and post-registration blanks, which is where the population rules bite."""
    rng = np.random.default_rng(seed)
    rows: list[tuple[int, int, str, float | None, float | None]] = []
    for player_id in range(1, players + 1):
        debut = int(rng.integers(1, 5))
        for gw in range(1, last_gw + 1):
            if gw < debut or rng.random() < 0.25:
                rows.append((player_id, gw, "MID", None, None))
            else:
                rows.append((player_id, gw, "MID", 90.0, float(rng.integers(0, 12))))
    return _mart(rows)


# ---------------------------------------------------------------------------
# §0.12 / §6.1 / §6.3 -- the set, the interface, the declared windows
# ---------------------------------------------------------------------------


def test_the_pre_registered_set_is_exactly_the_three_floor_rankers() -> None:
    """§0.12 selects F1, F2 and F3 unconditionally and excludes F4 from the set, so the floor is
    not half-populated by one family. A fourth entry here would be a design change."""
    assert list(FLOOR_RANKERS) == [F1_P_PLAY, F2_SEASON_PPG, F3_FORM_ROLL3]
    assert set(DECLARED_WINDOWS) == set(FLOOR_RANKERS)
    assert not any("roll5" in name for name in FLOOR_RANKERS)


def test_the_declared_windows_are_the_three_6_3_states() -> None:
    """§6.3: F1 GW4-38, F2 GW2-38, F3 GW2-38, and the intersection F1 binds is GW4-38."""
    assert DECLARED_WINDOWS[F1_P_PLAY] == (4, 38)
    assert DECLARED_WINDOWS[F2_SEASON_PPG] == (2, 38)
    assert DECLARED_WINDOWS[F3_FORM_ROLL3] == (2, 38)

    first = max(window[0] for window in DECLARED_WINDOWS.values())
    last = min(window[1] for window in DECLARED_WINDOWS.values())
    assert (max(first, STUDY_FIRST_GW), min(last, STUDY_LAST_GW)) == (4, 38)


def test_f1s_declared_first_gameweek_still_tracks_the_constant_it_was_derived_from() -> None:
    """§0.7 makes the window a *declaration*, so §6.3's GW4 is written as a literal rather than as
    `WARMUP_GW + 1` -- §7.4 freezes it in the pre-registration and it must not silently follow an
    upstream constant. This is the drift test that makes the literal safe: `INVENTORY.md` §2.6
    records `WARMUP_GW = 3` with predictions beginning at GW4, and if that moves, the declaration
    is stale rather than automatically correct."""
    assert WARMUP_GW + 1 == P_PLAY_FIRST_GW


def test_the_recent_form_window_is_three() -> None:
    """§0.12 selects F3 rather than F4 on `METRIC.md` §5.1's argument for the 3-gameweek length."""
    assert RECENT_FORM_WINDOW == 3


def test_every_output_satisfies_the_protocol_the_harness_consumes() -> None:
    """§5.1 forbids `harness.py` importing this module, so the two meet structurally at the
    composition root and nowhere else. If they drifted apart, nothing else would notice."""
    mart = _p_play_mart()
    for rank in FLOOR_RANKERS.values():
        output = rank(mart)
        assert isinstance(output, HarnessRankerOutput)


def test_every_ranker_emits_the_panel_shape_and_nothing_outside_its_window() -> None:
    """§6.1's frame is exactly (`player_id`, `gw`, `score`) at one row per player-gameweek, and
    §0.7 has the harness refuse a comparison window the ranker did not declare -- so a row outside
    the declared window is coverage the ranker never claimed."""
    mart = _p_play_mart()
    for name, rank in FLOOR_RANKERS.items():
        output = rank(mart)
        assert output.name == name
        assert output.window == DECLARED_WINDOWS[name]
        assert list(output.scores.columns) == ["player_id", "gw", "score"]
        assert not output.scores.duplicated(subset=["player_id", "gw"]).any()
        assert output.scores["gw"].between(*output.window).all()
        assert output.scores["score"].dtype == float
        assert output.scores.equals(
            output.scores.sort_values(["player_id", "gw"], kind="stable").reset_index(drop=True)
        )


def test_each_ranker_is_deterministic() -> None:
    """§6.8 rules out a live random choice anywhere in the slice, and §7.3 makes `run_id` a hash of
    the identifying fields -- a ranker that drew at run time would break reproducibility from
    inside, while every field the manifest records stayed identical."""
    mart = _p_play_mart()
    for rank in FLOOR_RANKERS.values():
        first, second = rank(mart), rank(mart)
        pd.testing.assert_frame_equal(first.scores, second.scores)


def test_no_ranker_mutates_the_mart_it_is_given() -> None:
    """§6.2: the same frame is handed to every ranker in a paired comparison, so an in-place edit
    would silently change what a later ranker sees."""
    mart = _p_play_mart()
    before = mart.copy(deep=True)
    for rank in FLOOR_RANKERS.values():
        rank(mart)
    pd.testing.assert_frame_equal(mart, before)


# ---------------------------------------------------------------------------
# §0.9 / §8.3 -- the population the two PPG rankers share
# ---------------------------------------------------------------------------


def test_the_population_is_the_post_registration_spine_with_blanks_at_zero() -> None:
    """§8.3's frame, and §0.9's three sub-choices: blanked weeks at 0, no-fixture weeks at 0,
    pre-registration weeks excluded entirely. `INVENTORY.md` §2.5 records why the last one matters
    -- the DAL spine is a cartesian product, so a late entrant *has* rows before he existed."""
    mart = _mart(
        [
            (1, 1, "MID", None, None),  # pre-registration: not a row at all
            (1, 2, "MID", None, None),  # pre-registration
            (1, 3, "MID", 90.0, 6.0),  # registration
            (1, 4, "MID", None, None),  # a post-registration blank: a row, at 0
            (1, 5, "MID", 0.0, 0.0),  # named, did not feature
        ]
    )
    pop = population(mart)
    assert list(pop.columns) == ["player_id", "gw", "total_points"]
    assert pop["gw"].tolist() == [3, 4, 5]
    assert pop["total_points"].tolist() == [6.0, 0.0, 0.0]
    assert not pop["total_points"].isna().any()


def test_the_registration_predicate_agrees_with_the_harnesss_and_the_samplers() -> None:
    """§5.1 forbids this module every Tier A sibling, so §2.1's predicate is written three times.
    §8.3's coupling claim -- the conditioning statistic and the squad universe read one population,
    not two that happen to look alike -- is only true while the three agree."""
    mart = _random_ppg_mart()
    mine = registration_gw(mart)
    pd.testing.assert_series_equal(mine, harness_registration_gw(mart))
    pd.testing.assert_series_equal(mine, _registration_gw(mart))


def test_the_no_nulls_assertion_fires_on_a_frame_that_carries_them() -> None:
    """§8.3's assertion. It sits at the call site because the precondition is invisible there: a
    pandas rolling mean skips NaN rather than treating it as 0."""
    complete = population(_random_ppg_mart())
    _assert_points_complete(complete)  # the fill makes this the normal case

    leaky = complete.copy()
    leaky.loc[0, "total_points"] = np.nan
    with pytest.raises(AssertionError, match="appearances rather than gameweeks elapsed"):
        _assert_points_complete(leaky)


def test_an_appearance_denominated_statistic_would_differ() -> None:
    """§8.3 names this as the silent-wrong-answer risk, and §0.9 rejects the quantity outright:
    `METRIC.md` §3.2 records that it orders an 8-per-appearance player who features a third of the
    time above a nailed 4-per-week one. Computed here so the tests above are known to be pinning
    the other quantity."""
    mart = _mart(
        [
            (1, 1, "MID", 90.0, 12.0),
            (1, 2, "MID", None, None),  # a blank -- a gameweek elapsed, at 0
            (1, 3, "MID", None, None),  # another
            (1, 4, "MID", 90.0, 2.0),
        ]
    )
    gameweek_denominated = rank_season_ppg(mart).scores.set_index("gw")["score"]

    appearances = mart.loc[mart["total_points"].notna(), ["gw", "total_points"]].astype({"total_points": float})
    appearance_denominated = appearances["total_points"].shift(1).expanding().mean()

    assert gameweek_denominated[4] == pytest.approx(12.0 / 3)
    assert float(appearance_denominated.iloc[-1]) == pytest.approx(12.0)
    assert gameweek_denominated[4] != pytest.approx(float(appearance_denominated.iloc[-1]))


# ---------------------------------------------------------------------------
# F2 -- §8.1's reuse on §8.3's population
# ---------------------------------------------------------------------------


def test_f2_matches_an_independent_expanding_reference() -> None:
    """§0.9's statistic, re-derived the slow way from the raw rows rather than by calling the same
    helper twice: points banked since registration over gameweeks elapsed, strictly before `gw`."""
    mart = _random_ppg_mart()
    got = rank_season_ppg(mart).scores.set_index(["player_id", "gw"])["score"].to_dict()

    for player_id, own in mart.groupby("player_id"):
        own = own.sort_values("gw")
        debut = int(own.loc[own["minutes"].notna(), "gw"].min())
        for gw in own["gw"]:
            if gw < max(debut, STUDY_FIRST_GW):
                assert (player_id, gw) not in got
                continue
            prior = own.loc[(own["gw"] >= debut) & (own["gw"] < gw), "total_points"].fillna(0).astype(float)
            expected = float(prior.mean()) if len(prior) else float("nan")
            actual = got[(player_id, gw)]
            if np.isnan(expected):
                assert np.isnan(actual), (player_id, gw)
            else:
                assert actual == pytest.approx(expected), (player_id, gw)


def test_f2_reproduces_the_harnesss_as_of_statistic_except_at_the_registration_row() -> None:
    """§8.3's claim is that the conditioning statistic and the PPG rankers read **one** population.
    §5.1 forbids sharing the code, so the agreement is asserted across the boundary instead.

    The one row where they differ is pinned rather than smoothed over. `harness.as_of_points`
    resolves the empty denominator -- a player whose registration gameweek *is* the squad-week -- to
    **0**, and records that as a §0.9 question it answers locally because the comparison cannot
    proceed without a number. A ranker has §6.5 available instead and takes it: the row is emitted
    as unrankable, which keeps all three floor rankers' coverage identical there (F1's lagged design
    columns are NaN on the same row) rather than giving two of them a value the third cannot have.
    """
    mart = _random_ppg_mart()
    reference = as_of_points(mart).set_index(["player_id", "gw"])["as_of_points"]
    scores = rank_season_ppg(mart).scores.set_index(["player_id", "gw"])["score"]
    debut = registration_gw(mart)

    for (player_id, gw), score in scores.items():
        if gw == debut[player_id]:
            assert np.isnan(score), (player_id, gw)
            assert reference[(player_id, gw)] == 0.0
        else:
            assert score == pytest.approx(float(reference[(player_id, gw)])), (player_id, gw)


# ---------------------------------------------------------------------------
# F3 -- §6.4's `min_periods = 1` over §8.3's population
# ---------------------------------------------------------------------------


def test_f3_matches_an_independent_three_gameweek_reference() -> None:
    """The last three gameweeks elapsed, strictly before `gw`, over §0.9's population."""
    mart = _random_ppg_mart()
    got = rank_recent_form(mart).scores.set_index(["player_id", "gw"])["score"].to_dict()

    for player_id, own in mart.groupby("player_id"):
        own = own.sort_values("gw")
        debut = int(own.loc[own["minutes"].notna(), "gw"].min())
        for gw in own["gw"]:
            if gw < max(debut, STUDY_FIRST_GW):
                continue
            window = own.loc[(own["gw"] >= debut) & (own["gw"] < gw), "total_points"]
            prior = window.fillna(0).astype(float).tail(RECENT_FORM_WINDOW)
            expected = float(prior.mean()) if len(prior) else float("nan")
            actual = got[(player_id, gw)]
            if np.isnan(expected):
                assert np.isnan(actual), (player_id, gw)
            else:
                assert actual == pytest.approx(expected), (player_id, gw)


def test_f3_is_a_partial_window_mean_where_min_periods_k_would_be_null() -> None:
    """§6.4's selection, with the alternative computed beside it on the same frame.

    §6.4 states the cost plainly -- at GW2 the statistic is a one-gameweek mean and at GW3 a
    two-gameweek mean -- and the reason the cost is paid: `min_periods = k` makes availability a
    **per-player** property, NaN for any player with fewer than *k* prior observations, which no
    declared window can express honestly.
    """
    mart = _mart([(1, gw, "MID", 90.0, float(gw)) for gw in range(1, 6)])
    scores = rank_recent_form(mart).scores.set_index("gw")["score"]

    assert scores[2] == pytest.approx(1.0)  # GW1 alone
    assert scores[3] == pytest.approx(1.5)  # GW1-2
    assert scores[4] == pytest.approx(2.0)  # GW1-3, the first full window

    pop = population(mart)
    rejected = pop["total_points"].shift(1).rolling(RECENT_FORM_WINDOW, min_periods=RECENT_FORM_WINDOW).mean()
    rejected.index = pd.Index(pop["gw"])
    assert np.isnan(rejected[2]) and np.isnan(rejected[3])
    assert rejected[4] == pytest.approx(scores[4])


def test_f3_never_reads_the_gameweek_it_scores() -> None:
    """§6.2's lag-1 rule, tested by perturbation rather than by inspection: changing a gameweek's
    realised points must not move that gameweek's own score, and must move the next one's."""
    mart = _mart([(1, gw, "MID", 90.0, 2.0) for gw in range(1, 7)])
    baseline = rank_recent_form(mart).scores.set_index("gw")["score"]

    perturbed_mart = mart.copy()
    perturbed_mart.loc[perturbed_mart["gw"] == 4, "total_points"] = 40.0
    perturbed = rank_recent_form(perturbed_mart).scores.set_index("gw")["score"]

    assert perturbed[4] == pytest.approx(baseline[4])
    assert perturbed[5] != pytest.approx(baseline[5])


def test_the_lag_safety_assertion_fires_on_a_leaking_column() -> None:
    """§6.2 asks for a leakage assertion written against the columns the ranker actually uses --
    `assert_no_future_leakage` is not adopted, because `INVENTORY.md` §3.7 records it requiring
    `points_roll3`, which the governed mart excludes, so it fails closed against this very mart."""
    frame = pd.DataFrame(
        {"player_id": [1, 1, 2, 2], "gw": [1, 2, 1, 2], "total_points_roll3": [np.nan, 1.0, np.nan, 3.0]}
    )
    _assert_lag_safe(frame, "total_points_roll3")

    leaking = frame.copy()
    leaking.loc[0, "total_points_roll3"] = 5.0
    with pytest.raises(AssertionError, match="first population row"):
        _assert_lag_safe(leaking, "total_points_roll3")


# ---------------------------------------------------------------------------
# `METRIC.md` §5.3 / Appendix A.3 -- the degeneracy §0.12 requires reported
# ---------------------------------------------------------------------------


def test_f2_and_f3_are_identical_through_gw4_and_diverge_at_gw5() -> None:
    """`METRIC.md` Appendix A.3, reproduced on a synthetic panel. §8.3 gives the reason: they are
    two windows over one population, and while a player has three or fewer prior in-game gameweeks
    the shorter window covers all of them. §0.12 requires it representable in the artefact rather
    than a caveat in prose, because under the GW4-38 common window one of those weeks sits inside
    the study and cannot discriminate between two floor rankers."""
    mart = _mart(
        [(player_id, gw, "MID", 90.0, float((player_id * gw) % 13)) for player_id in range(1, 9) for gw in range(1, 8)]
    )
    season = rank_season_ppg(mart).scores.set_index(["player_id", "gw"])["score"]
    form = rank_recent_form(mart).scores.set_index(["player_id", "gw"])["score"]
    assert season.index.equals(form.index)

    through_gw4 = season.index.get_level_values("gw") <= 4
    pd.testing.assert_series_equal(season[through_gw4], form[through_gw4], check_names=False)
    assert not season[~through_gw4].equals(form[~through_gw4])

    at_gw5 = season.index.get_level_values("gw") == 5
    assert (season[at_gw5].to_numpy() != form[at_gw5].to_numpy()).any()


# ---------------------------------------------------------------------------
# F1 -- `INVENTORY.md` §2.6's population, and the holes §6.5 and §0.4 govern
# ---------------------------------------------------------------------------


def test_f1_emits_a_score_panel_over_its_declared_window() -> None:
    """`INVENTORY.md` §2.6 measures the fit as an expanding walk-forward re-estimated per position
    per gameweek, so one call covers the panel (§6.1). The probabilities it returns are the whole
    of what F1 ranks on -- §0.12: `p_play` alone, scoring rate ignored entirely."""
    output = rank_p_play(_p_play_mart())
    scored = output.scores.dropna(subset=["score"])
    assert not scored.empty
    assert scored["score"].between(0.0, 1.0).all()
    assert scored["gw"].min() >= P_PLAY_FIRST_GW


def test_f1_emits_no_row_before_its_declared_window_where_the_ppg_rankers_do() -> None:
    """§6.3: F1 starts at GW4 and binds any comparison containing it to GW4-38, while F2 and F3
    declare GW2-38. `INVENTORY.md` §3.3 records the consequence -- two gameweeks of that baseline's
    window are simply unavailable."""
    mart = _p_play_mart()
    assert rank_p_play(mart).scores["gw"].min() >= 4
    assert rank_season_ppg(mart).scores["gw"].min() == 2
    assert rank_recent_form(mart).scores["gw"].min() == 2


def test_f1_leaves_double_gameweek_rows_unrankable() -> None:
    """§6.5's rule, and the row it was not written for. `INVENTORY.md` §2.6 records
    `PlayModel.population` filtering `~is_dgw`, so F1 produces no score for a double gameweek while
    F2 and F3 do. No constant can fill the hole -- P(play) in a double gameweek is not 0 and is not
    a fixed number -- so the row stays unrankable and the harness places it below every scored
    player. `INVENTORY.md` §3.4 records the materiality as a first-run measurement."""
    mart = _p_play_mart(dgw_at=6)
    scores = rank_p_play(mart).scores
    # Absent rather than null: §6.1 admits either and the harness reads them identically, so the
    # test pins which one this ranker emits rather than accepting both.
    assert scores.loc[scores["gw"] == 6].empty
    assert not scores.loc[scores["gw"] == 7, "score"].isna().any()

    # The two PPG rankers are unaffected: their population is the gameweek spine, not the fixtures
    # universe, so a double gameweek is an ordinary row to them.
    assert not rank_recent_form(mart).scores.loc[lambda f: f["gw"] == 6, "score"].isna().all()


def test_f1_leaves_no_fixture_rows_unscored_and_0_4_is_why_that_is_harmless() -> None:
    """`INVENTORY.md` §2.6 records `PlayModel.population` dropping null-`minutes` rows, which is
    the asymmetry §0.4 removes upstream: without it, the unrankable-last rule would bench every
    no-fixture player for F1 and only for F1, handing one floor ranker an implicit
    fixture-awareness the other two lack. The rows are asserted absent here; §0.4's rule lives in
    the harness, and `test_harness.py` owns it."""
    mart = _p_play_mart(blank_at=5)
    blanks = mart.loc[mart["minutes"].isna() & (mart["gw"] == 5), "player_id"]
    assert not blanks.empty

    scores = rank_p_play(mart).scores.set_index(["player_id", "gw"])
    for player_id in blanks:
        assert (player_id, 5) not in scores.index

    # The PPG rankers do score them, at a value the blank contributes 0 to (§0.9).
    form = rank_recent_form(mart).scores.set_index(["player_id", "gw"])["score"]
    assert not np.isnan(form[(int(blanks.iloc[0]), 5)])


def test_the_p_play_ranker_rejects_a_mart_missing_the_columns_it_reads() -> None:
    """A legible failure rather than a `KeyError` from inside a fitted GLM."""
    with pytest.raises(ValueError, match="missing columns the p_play ranker reads"):
        rank_p_play(_random_ppg_mart())


def test_the_population_rejects_a_mart_missing_the_columns_it_reads() -> None:
    mart = _random_ppg_mart().drop(columns=["total_points"])
    with pytest.raises(ValueError, match="missing columns the PPG population reads"):
        population(mart)


# ---------------------------------------------------------------------------
# §3.3 / §5.1 / §5.6 -- Tier B's import closure
# ---------------------------------------------------------------------------


def test_the_import_closure_is_tier_bs() -> None:
    """§5.1's row forbids every Tier A sibling; §3.3 leaves `research/`, `serve/` and
    `operational/` outside both tiers. §5.6 adds the positive half: importing this module **does**
    bring `model` into a clean interpreter -- the Tier B edge §3.4 says is unavoidable -- so the
    test fails loudly if the ranker edge ever moves, which would mean §3's two-tier split had
    quietly changed shape.

    Run as a subprocess for §5.6's reason: `pyproject.toml`'s `testpaths` imports `model` before
    any test here runs, so an in-process `sys.modules` check would pass against any module."""
    program = (
        "import sys;"
        "import decisions.starting_xi.rankers;"
        "banned = ('research', 'serve', 'operational',"
        " 'decisions.starting_xi.harness', 'decisions.starting_xi.sampler',"
        " 'decisions.starting_xi.formations', 'decisions.starting_xi.results',"
        " 'decisions.starting_xi.uncertainty');"
        "reached = sorted(m for m in sys.modules if m.startswith(banned));"
        "print(repr(reached));"
        "print('model.terms.p_play.p_play' in sys.modules);"
        "print('model.eval.baselines' in sys.modules);"
        "print('model.features.build' in sys.modules)"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    reached, p_play, baselines, build = child.stdout.splitlines()
    assert reached == "[]"
    assert [p_play, baselines, build] == ["True", "True", "True"]
