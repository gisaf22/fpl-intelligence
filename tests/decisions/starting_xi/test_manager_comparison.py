"""Acceptance tests for Stage 5's real-squad path (#69).

The sampled manager is the real one under `warehouse/fixtures/40289379567/`: `entry_id` 7254, with
auto-subs in GW5 and GW6. The picks frame carries no points, so the leak test attaches some. Nothing
here reads a real player outcome: the gameweek frame in the equivalence test is constructed, and no
test compares D2 with a manager on real results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import harness, manager_comparison, orderings, verdict
from domain.fpl_squad import POSITION_BY_ID
from warehouse import served

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "warehouse" / "fixtures"
RUN_ID = "40289379567"
SEASON = "2026-27"
MANAGER = 7254
AUTO_SUB_GW = 5
SCORED_GW = 5
REBUILT = manager_comparison.SOURCE_REBUILT
CAPTURED = manager_comparison.SOURCE_CAPTURED


@pytest.fixture
def picks() -> pd.DataFrame:
    pin = served.pin_of(FIXTURE_ROOT / RUN_ID)
    return served.load_managers(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT).picks


def _eleven_of(table: pd.DataFrame, entry_id: int, gw: int) -> set[int]:
    rows = table[(table["entry_id"] == entry_id) & (table["gw"] == gw)]
    return set(rows["player_id"].astype(int))


def _hand_built_week() -> pd.DataFrame:
    """Slots 1-15 hold players 101-115. Player 104 (a starter) played 0 minutes, so FPL put 112 in his
    slot and moved him to the bench: the lineup after auto-subs."""
    players = [*range(101, 116)]
    players[3], players[11] = 112, 104
    return pd.DataFrame(
        {
            "season": SEASON,
            "entry_id": 1,
            "gw": 5,
            "slot": range(1, 16),
            "player_id": players,
            "is_auto_sub_in": [player == 112 for player in players],
            "is_auto_sub_out": [player == 104 for player in players],
        }
    )


def _eleven_table(players: range | list[int], source: str, *, entry_id: int = 1, gw: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"entry_id": entry_id, "gw": gw, "player_id": list(players), "source": source})


# --- AC1: the eleven does not depend on any points column ---


@pytest.mark.unit
@pytest.mark.covers("#69 AC1")
@pytest.mark.parametrize("column", ["total_points", "points", "event_points"])
def test_scrambling_attached_points_leaves_the_chosen_eleven_unchanged(picks: pd.DataFrame, column: str) -> None:
    rng = np.random.default_rng(0)
    scored = picks.assign(**{column: rng.integers(0, 20, len(picks))})
    scrambled = scored.assign(**{column: rng.permutation(scored[column].to_numpy())})
    assert not scored[column].equals(scrambled[column])
    pd.testing.assert_frame_equal(manager_comparison.chosen_eleven(scored), manager_comparison.chosen_eleven(scrambled))


# --- AC2: the two scoring paths give identical points ---


@dataclass(frozen=True)
class _Ranker:
    """A stand-in for `RankerOutput`, satisfying the protocol structurally."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _frames_for(squad: pd.DataFrame, *, null_points_player: int | None = None) -> served.Frames:
    """A constructed gameweek frame for one real squad: legal positions by slot, made-up points."""
    position_ids = dict(enumerate([1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]))
    assert set(position_ids.values()) == set(POSITION_BY_ID)
    players = squad.sort_values("slot")["player_id"].astype(int).tolist()
    gameweek = pd.DataFrame(
        {
            "player_id": players,
            "gw": SCORED_GW,
            "position_id": [position_ids[index] for index in range(len(players))],
            "deadline_fixture_count": 1,
            "deadline_count_is_realised": False,
            "minutes": 90.0,
            "total_points": [float(index + 2) for index in range(len(players))],
            "entry_gw": 1,
        }
    )
    gameweek["total_points"] = gameweek["total_points"].astype("Float64")
    if null_points_player is not None:
        gameweek.loc[gameweek["player_id"] == null_points_player, "total_points"] = pd.NA
    return served.Frames(fixture=pd.DataFrame(), gameweek=gameweek, pin=served.Pin(run_id="constructed", sha256={}))


def _rule_week(squad: pd.DataFrame, frames: served.Frames) -> pd.DataFrame:
    players = squad["player_id"].astype(int).tolist()
    scores = pd.DataFrame({"player_id": players, "gw": SCORED_GW, "score": [float(p) for p in players]})
    ranker = _Ranker("constructed", (1, 38), scores)
    result = harness.run(
        manager_comparison.real_squads(squad),
        lambda _: ranker,
        orderings.PRE_REGISTERED_ORDERINGS,
        frames,
        (SCORED_GW, SCORED_GW),
    )
    return result.squad_weeks


def _harness_eleven(week: pd.Series) -> pd.DataFrame:
    return _eleven_table([int(p) for p in str(week["chosen_xi"]).split(",")], REBUILT, entry_id=MANAGER, gw=SCORED_GW)


@pytest.mark.integration
@pytest.mark.covers("#69 AC2")
def test_one_eleven_scores_the_same_through_the_harness_and_the_manager_scorer(picks: pd.DataFrame) -> None:
    squad = picks[picks["gw"] == SCORED_GW]
    frames = _frames_for(squad)
    week = _rule_week(squad, frames).iloc[0]
    scored = manager_comparison.score_elevens(_harness_eleven(week), frames.gameweek)
    assert scored["points"].tolist() == [week["no_subs_xi_points"]]


@pytest.mark.integration
@pytest.mark.covers("#69 AC2")
def test_a_null_points_player_scores_zero_on_both_paths(picks: pd.DataFrame) -> None:
    squad = picks[picks["gw"] == SCORED_GW]
    first_look = _rule_week(squad, _frames_for(squad)).iloc[0]
    in_eleven = int(str(first_look["chosen_xi"]).split(",")[0])
    frames = _frames_for(squad, null_points_player=in_eleven)
    week = _rule_week(squad, frames).iloc[0]
    assert week["no_subs_xi_points"] < first_look["no_subs_xi_points"]
    scored = manager_comparison.score_elevens(_harness_eleven(week), frames.gameweek)
    assert scored["points"].tolist() == [week["no_subs_xi_points"]]


@pytest.mark.unit
@pytest.mark.covers("#69 AC2")
def test_a_player_absent_from_the_gameweek_frame_raises(picks: pd.DataFrame) -> None:
    squad = picks[picks["gw"] == SCORED_GW]
    frames = _frames_for(squad)
    eleven = _eleven_table([999_999, *squad["player_id"].astype(int).head(10)], REBUILT, entry_id=MANAGER)
    with pytest.raises(ValueError, match="999999"):
        manager_comparison.score_elevens(eleven, frames.gameweek)


# --- AC3: FPL's substitution is not credited to the manager ---


@pytest.mark.unit
@pytest.mark.covers("#69 AC3")
def test_a_hand_built_auto_sub_is_undone() -> None:
    eleven = manager_comparison.chosen_eleven(_hand_built_week())
    assert _eleven_of(eleven, 1, 5) == set(range(101, 112))
    assert set(eleven["source"]) == {REBUILT}


@pytest.mark.unit
@pytest.mark.covers("#69 AC3")
def test_a_real_auto_sub_week_is_undone(picks: pd.DataFrame) -> None:
    week = picks[picks["gw"] == AUTO_SUB_GW]
    subbed_on = set(week.loc[week["is_auto_sub_in"], "player_id"].astype(int))
    subbed_off = set(week.loc[week["is_auto_sub_out"], "player_id"].astype(int))
    assert subbed_on and subbed_off
    eleven = _eleven_of(manager_comparison.chosen_eleven(picks), MANAGER, AUTO_SUB_GW)
    assert len(eleven) == 11
    assert subbed_off <= eleven
    assert not subbed_on & eleven


@pytest.mark.unit
@pytest.mark.covers("#69 AC3")
def test_a_week_that_does_not_rebuild_to_eleven_players_raises() -> None:
    week = _hand_built_week()
    week.loc[week["player_id"] == 112, "is_auto_sub_in"] = False
    with pytest.raises(ValueError, match=r"\(1, 5\)"):
        manager_comparison.chosen_eleven(week)


# --- AC4: two sources must agree as sets; one is never silently preferred ---


@pytest.mark.unit
@pytest.mark.covers("#69 AC4")
def test_two_sources_that_agree_as_sets_pass_as_one_eleven() -> None:
    rebuilt = _eleven_table(range(101, 112), REBUILT)
    captured = _eleven_table(list(reversed(range(101, 112))), CAPTURED)
    merged = manager_comparison.reconcile_sources(rebuilt, captured)
    assert _eleven_of(merged, 1, 5) == set(range(101, 112))
    assert len(merged) == 11


@pytest.mark.unit
@pytest.mark.covers("#69 AC4")
def test_two_sources_that_disagree_raise_and_name_the_manager_week() -> None:
    rebuilt = _eleven_table(range(101, 112), REBUILT)
    captured = _eleven_table([*range(101, 111), 999], CAPTURED)
    with pytest.raises(ValueError, match=r"\(1, 5\)"):
        manager_comparison.reconcile_sources(rebuilt, captured)


@pytest.mark.unit
@pytest.mark.covers("#69 AC4")
def test_a_manager_week_with_one_source_uses_it_and_says_which() -> None:
    rebuilt = _eleven_table(range(101, 112), REBUILT, gw=5)
    captured = _eleven_table(range(201, 212), CAPTURED, gw=6)
    merged = manager_comparison.reconcile_sources(rebuilt, captured)
    assert merged.groupby("gw")["source"].agg(set).to_dict() == {5: {REBUILT}, 6: {CAPTURED}}


@pytest.mark.skip(reason="the capture schema belongs to gisaf22/fpl-ingest#128, parked until its own grill")
@pytest.mark.unit
@pytest.mark.covers("#69 AC4")
def test_the_captured_backend_returns_the_chosen_eleven_table() -> None:
    table = manager_comparison.captured_pre_autosub_eleven(pd.DataFrame())
    assert list(table.columns) == ["entry_id", "gw", "player_id", "source"]
    assert set(table["source"]) == {CAPTURED}


# --- AC5: outcome comes from no_subs_xi_points, never chosen_xi_points ---


def _rule_weeks(no_subs: float = 50.0, chosen: float = 60.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "squad_id": [manager_comparison.squad_id(1, 5), manager_comparison.squad_id(1, 6)],
            "gw": [5, 6],
            "no_subs_xi_points": [no_subs, 40.0],
            "chosen_xi_points": [chosen, 40.0],
        }
    )


def _manager_points() -> pd.DataFrame:
    return pd.DataFrame({"entry_id": [1, 1], "gw": [5, 6], "source": REBUILT, "points": [55.0, 40.0]})


def _chips(chip: str | None = None) -> pd.DataFrame:
    return pd.DataFrame({"entry_id": [1, 1], "gw": [5, 6], "active_chip": [chip, None]})


def _panel() -> pd.DataFrame:
    return pd.DataFrame({"entry_id": [1, 1], "gw": [5, 6], "band": ["top", None]})


def _feed(rule_weeks: pd.DataFrame | None = None, chips: pd.DataFrame | None = None) -> pd.DataFrame:
    return manager_comparison.paired_feed(
        _rule_weeks() if rule_weeks is None else rule_weeks,
        _manager_points(),
        _chips() if chips is None else chips,
        _panel(),
    )


@pytest.mark.unit
@pytest.mark.covers("#69 AC5")
def test_the_feed_is_the_table_verdict_reads_with_ties_as_half() -> None:
    table = _feed()
    assert tuple(table.columns) == verdict.COLUMNS
    assert table.set_index("gameweek")["outcome"].to_dict() == {5: 0.0, 6: 0.5}
    assert table["manager_id"].tolist() == [1, 1]
    assert table.set_index("gameweek")["band"].loc[5] == "top"
    assert table.set_index("gameweek")["band"].isna().loc[6]
    verdict.raw_p_values(table, n_resamples=10, seed=0)


@pytest.mark.unit
@pytest.mark.covers("#69 AC5")
def test_changing_chosen_xi_points_does_not_move_the_outcome() -> None:
    pd.testing.assert_frame_equal(_feed(_rule_weeks(chosen=0.0)), _feed(_rule_weeks(chosen=99.0)))


@pytest.mark.unit
@pytest.mark.covers("#69 AC5")
def test_changing_no_subs_xi_points_moves_the_outcome() -> None:
    assert _feed(_rule_weeks(no_subs=99.0)).set_index("gameweek")["outcome"].loc[5] == 1.0


# --- AC9 (proposed): Free Hit and Bench Boost weeks never reach the verdict ---


@pytest.mark.unit
@pytest.mark.covers("#69 AC9")
@pytest.mark.parametrize("chip", ["freehit", "bboost"])
def test_free_hit_and_bench_boost_weeks_are_excluded(chip: str) -> None:
    assert _feed(chips=_chips(chip))["gameweek"].tolist() == [6]


@pytest.mark.unit
@pytest.mark.covers("#69 AC9")
@pytest.mark.parametrize("chip", ["wildcard", "3xc"])
def test_other_chip_weeks_are_kept(chip: str) -> None:
    assert _feed(chips=_chips(chip))["gameweek"].tolist() == [5, 6]


# --- AC10 (proposed): a panel manager-week missing a side raises rather than dropping out ---


@pytest.mark.unit
@pytest.mark.covers("#69 AC10")
@pytest.mark.parametrize("side", ["rule", "manager", "chips"])
def test_a_panel_manager_week_with_a_side_missing_raises(side: str) -> None:
    rule_weeks = _rule_weeks()
    manager_points = _manager_points()
    chips = _chips()
    if side == "rule":
        rule_weeks = rule_weeks[rule_weeks["gw"] == 5]
    elif side == "manager":
        manager_points = manager_points[manager_points["gw"] == 5]
    else:
        chips = chips[chips["gw"] == 5]
    with pytest.raises(ValueError, match=r"\(1, 6\)"):
        manager_comparison.paired_feed(rule_weeks, manager_points, chips, _panel())
