"""Stage 5's evaluation panel and rank bands (`decisions/starting_xi/evaluation_panel.py`).

Hand-built frames pin the rules: every number here is chosen to sit on a boundary, not read from a
run. The end-to-end test reads the real sampled manager under `warehouse/fixtures/40289379567/` and
constructed points, so no test compares D2 with a manager on real results.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import evaluation_panel as ep
from decisions.starting_xi import manager_comparison, verdict
from warehouse import served

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "warehouse" / "fixtures"
RUN_ID = "40289379567"
SEASON = "2026-27"
MANAGER = 7254


def _weeks(entry_id: int, gameweeks: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"entry_id": entry_id, "gw": gameweeks})


def _ranks(entry_id: int, ranks: dict[int, int | None]) -> pd.DataFrame:
    frame = pd.DataFrame({"entry_id": entry_id, "gw": list(ranks), "overall_rank": list(ranks.values())})
    return frame.astype({"overall_rank": "Int64"})


def _counts(counts: dict[int, int | None]) -> pd.DataFrame:
    return pd.DataFrame({"gw": list(counts), "ranked_count": list(counts.values())}).astype({"ranked_count": "Int64"})


def _band_at_gw4(rank: int | None, count: int | None) -> object:
    bands = ep.rank_bands(_weeks(1, [3, 4]), _ranks(1, {3: rank, 4: 1}), _counts({3: count}))
    return bands.set_index("gw")["band"].loc[4]


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
@pytest.mark.parametrize("count", [9, 10])
@pytest.mark.parametrize(("rank", "band"), [(3, "top"), (4, "middle"), (6, "middle"), (7, "bottom")])
def test_a_rank_on_a_boundary_takes_the_better_band(count: int, rank: int, band: str) -> None:
    assert _band_at_gw4(rank, count) == band


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_the_cut_is_exact_where_a_float_would_round() -> None:
    # 2**53 + 1 has no float form, so r/N rounds onto the third; 3r > N puts it in the middle band.
    rank = 2**53 + 1
    assert _band_at_gw4(rank, 3 * rank - 1) == "middle"
    assert _band_at_gw4(rank, 3 * rank) == "top"


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_the_scored_gameweeks_own_rank_never_moves_its_band() -> None:
    weeks = _weeks(1, [3, 4])
    best = ep.rank_bands(weeks, _ranks(1, {3: 8, 4: 1}), _counts({3: 9}))
    worst = ep.rank_bands(weeks, _ranks(1, {3: 8, 4: 9}), _counts({3: 9}))
    assert best.set_index("gw")["band"].loc[4] == worst.set_index("gw")["band"].loc[4] == "bottom"


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_the_ranked_count_is_the_previous_gameweeks_like_the_rank() -> None:
    bands = ep.rank_bands(_weeks(1, [3, 4]), _ranks(1, {3: 4, 4: 1}), _counts({3: 9, 4: 90}))
    assert bands.set_index("gw")["band"].loc[4] == "middle"


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_a_rank_above_the_ranked_count_raises_and_names_the_manager_week() -> None:
    with pytest.raises(ValueError, match=r"greater than ranked_count.*\(1, 4\)"):
        _band_at_gw4(10, 9)


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_a_null_ranked_count_for_a_real_rank_raises_and_names_the_manager_week() -> None:
    with pytest.raises(ValueError, match=r"null or missing ranked_count.*\(1, 4\)"):
        _band_at_gw4(3, None)


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_a_gameweek_absent_from_the_ranked_counts_raises_for_a_real_rank() -> None:
    with pytest.raises(ValueError, match=r"null or missing ranked_count.*\(1, 4\)"):
        ep.rank_bands(_weeks(1, [3, 4]), _ranks(1, {3: 3, 4: 1}), _counts({4: 9}))


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
@pytest.mark.covers("#70 AC4")
@pytest.mark.parametrize("rank", [None, 0])
@pytest.mark.parametrize(
    "counts",
    [{3: None}, {3: 9}, {}],
    ids=["null_count", "real_count", "absent_count"],
)
def test_a_null_or_0_rank_gives_a_null_band_without_reading_the_ranked_count(
    rank: int | None, counts: dict[int, int | None]
) -> None:
    bands = ep.rank_bands(_weeks(1, [3, 4]), _ranks(1, {3: rank, 4: 1}), _counts(counts))
    assert pd.isna(bands.set_index("gw")["band"].loc[4])


@pytest.mark.unit
@pytest.mark.covers("#70 AC4")
def test_a_new_team_has_no_band_in_its_first_gameweek() -> None:
    bands = ep.rank_bands(_weeks(1, [5, 6]), _ranks(1, {5: 3, 6: 3}), _counts({5: 9}))
    by_gw = bands.set_index("gw")["band"]
    assert pd.isna(by_gw.loc[5])
    assert by_gw.loc[6] == "top"


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_a_missing_gameweek_row_in_mid_history_raises_and_is_not_a_null_rank() -> None:
    with pytest.raises(ValueError, match=r"no fct_manager_gameweek row.*\(1, 3\)"):
        ep.rank_bands(_weeks(1, [2, 3, 4]), _ranks(1, {2: 3, 4: 3}), _counts({2: 9, 3: 9}))


@pytest.mark.unit
@pytest.mark.covers("#70 AC3")
def test_a_lost_first_gameweek_row_raises_and_does_not_make_the_next_week_a_new_team() -> None:
    with pytest.raises(ValueError, match=r"no fct_manager_gameweek row.*\(1, 1\)"):
        ep.rank_bands(_weeks(1, [1, 2]), _ranks(1, {2: 3}), _counts({1: 9}))


def _manager(
    entry_id: int,
    last_gw: int,
    *,
    first_gw: int = 1,
    changed_in: tuple[int, ...] = (),
    cohort: str = "random",
    rank: int | None = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One manager's `picks` and `gameweeks` in the loader's shape: the same team every week, but
    one transfer in each `changed_in` week, which stays."""
    weeks = range(first_gw, last_gw + 1)
    gameweeks = pd.DataFrame(
        {
            "entry_id": entry_id,
            "gw": weeks,
            "active_chip": None,
            "cohort": cohort,
            "event_transfers": [int(g in changed_in) for g in weeks],
            "overall_rank": pd.array([rank] * len(weeks), dtype="Int64"),
        }
    )
    rows = []
    for g in weeks:
        made = sum(w in changed_in for w in range(first_gw, g + 1))
        rows += [(entry_id, g, s, 200 + made if s == 1 else 100 + s, False, False, s == 2) for s in range(1, 16)]
    columns = ["entry_id", "gw", "slot", "player_id", "is_auto_sub_in", "is_auto_sub_out", "is_captain"]
    return pd.DataFrame(rows, columns=columns), gameweeks


def _table(*managers: tuple[pd.DataFrame, pd.DataFrame], count: int = 9) -> pd.DataFrame:
    picks = pd.concat([m[0] for m in managers], ignore_index=True)
    gameweeks = pd.concat([m[1] for m in managers], ignore_index=True)
    return ep.manager_weeks(picks, gameweeks, _counts(dict.fromkeys(range(1, 9), count)))


def _row(table: pd.DataFrame, entry_id: int, gw: int) -> pd.Series:
    return table.set_index(["entry_id", "gw"]).loc[(entry_id, gw)]


@pytest.mark.unit
@pytest.mark.covers("#70 AC1")
def test_a_manager_is_in_the_panel_only_in_the_weeks_they_pass_the_screen() -> None:
    table = _table(_manager(1, 7, changed_in=(6,)))
    # GW6's change is in the windows of GW6 and GW7, and outside GW5's, which ends before it.
    assert [bool(_row(table, 1, g)["in_panel"]) for g in (4, 5, 6, 7)] == [False, False, True, True]
    assert ep.evaluation_panel(table)["gw"].tolist() == [6, 7]


@pytest.mark.unit
@pytest.mark.covers("#70 AC1")
def test_a_change_before_the_window_does_not_keep_a_manager_in_the_panel() -> None:
    table = _table(_manager(1, 7, changed_in=(4,)))
    assert bool(_row(table, 1, 6)["in_panel"])
    assert not _row(table, 1, 7)["in_panel"]


@pytest.mark.unit
@pytest.mark.covers("#70 AC1")
def test_a_tenure_of_three_gameweeks_or_less_is_in_the_panel_unscreened() -> None:
    table = _table(_manager(1, 7, first_gw=5))
    assert [bool(_row(table, 1, g)["in_panel"]) for g in (5, 6, 7)] == [True, True, True]
    assert [bool(_row(table, 1, g)["screened"]) for g in (5, 6, 7)] == [False, False, False]


@pytest.mark.unit
@pytest.mark.covers("#70 AC2")
def test_no_manager_week_of_the_self_cohort_is_in_the_panel() -> None:
    table = _table(_manager(1, 7, changed_in=(5, 6, 7), cohort="self"), _manager(2, 7, changed_in=(5, 6, 7)))
    assert table.loc[table["entry_id"] == 1, "in_panel"].tolist() == [False] * 4
    assert set(ep.evaluation_panel(table)["entry_id"]) == {2}


@pytest.mark.unit
@pytest.mark.covers("#70 AC2")
def test_a_self_cohort_exempt_week_is_out_of_the_panel_too() -> None:
    table = _table(_manager(1, 7, first_gw=6, cohort="self"), _manager(2, 7, changed_in=(7,)))
    assert 1 not in set(ep.evaluation_panel(table)["entry_id"])


@pytest.mark.unit
@pytest.mark.covers("#70 AC4")
@pytest.mark.parametrize("rank", [None, 0])
def test_a_manager_week_with_no_valid_rank_stays_in_the_panel_with_a_null_band(rank: int | None) -> None:
    panel = ep.evaluation_panel(_table(_manager(1, 5, changed_in=(5,), rank=rank)))
    assert panel["gw"].tolist() == [4, 5] or panel["gw"].tolist() == [5]
    assert panel["band"].isna().all()


@pytest.mark.unit
@pytest.mark.covers("#70 AC4")
def test_a_late_joiners_first_week_stays_in_the_panel_with_a_null_band() -> None:
    panel = ep.evaluation_panel(_table(_manager(1, 6, first_gw=5))).set_index("gw")
    assert pd.isna(panel.loc[5, "band"])
    assert panel.loc[6, "band"] == "top"


@pytest.mark.unit
@pytest.mark.covers("#70 AC5")
def test_the_panel_covers_only_the_gameweeks_d2_can_score() -> None:
    # The feed raises on a panel week with no D2 score, and D2 produces no eleven before GW4.
    table = _table(_manager(1, 5, changed_in=(2, 3, 4, 5)))
    assert table["gw"].tolist() == [4, 5]


def _feed(panel: pd.DataFrame, chips: pd.DataFrame) -> pd.DataFrame:
    """`paired_feed` on constructed scores: D2 wins even gameweeks, ties a week divisible by 5 and
    loses the rest, so nothing here is a real result."""
    squad_ids = [
        manager_comparison.squad_id(int(e), int(g)) for e, g in zip(panel["entry_id"], panel["gw"], strict=True)
    ]
    gw = panel["gw"].to_numpy()
    rule = np.where(gw % 2 == 0, 60.0, np.where(gw % 5 == 0, 50.0, 40.0))
    rule_weeks = pd.DataFrame({"squad_id": squad_ids, "gw": gw, "no_subs_xi_points": rule, "chosen_xi_points": 0.0})
    points = pd.DataFrame({"entry_id": panel["entry_id"], "gw": gw, "source": "rebuilt_from_flags", "points": 50.0})
    return manager_comparison.paired_feed(rule_weeks, points, chips, panel)


@pytest.mark.integration
@pytest.mark.covers("#70 AC5")
def test_the_panel_and_bands_of_every_label_reach_the_verdict_through_the_feed() -> None:
    managers = (
        _manager(1, 7, changed_in=(4, 5, 6, 7), rank=3),
        _manager(2, 7, changed_in=(4, 5, 6, 7), rank=5),
        _manager(3, 7, changed_in=(4, 5, 6, 7), rank=8),
        _manager(4, 7, changed_in=(4, 5, 6, 7), rank=None),
        _manager(5, 7, changed_in=(4, 5, 6, 7), cohort="self"),
    )
    panel = ep.evaluation_panel(_table(*managers))
    chips = pd.concat([m[1] for m in managers], ignore_index=True)
    table = _feed(panel, chips)
    assert list(table.columns) == list(verdict.COLUMNS)
    assert len(table) == 4 * 4
    assert set(table["manager_id"]) == {1, 2, 3, 4}
    assert set(table["band"].dropna()) == set(verdict.BANDS)
    assert table["band"].isna().sum() == 4
    assert verdict.primary_verdict(table, n_resamples=100, apply_rerun=False).groups == verdict.GROUPS


@pytest.mark.integration
@pytest.mark.covers("#70 AC5")
def test_the_verdict_would_refuse_a_band_outside_its_labels() -> None:
    # The fixture case that can fail: the labels above only pass because they are the verdict's own.
    managers = (_manager(1, 7, changed_in=(4, 5, 6, 7)),)
    panel = ep.evaluation_panel(_table(*managers)).assign(band="upper")
    with pytest.raises(ValueError, match="band must be one of"):
        verdict.primary_verdict(_feed(panel, managers[0][1]), n_resamples=100, apply_rerun=False)


@pytest.mark.integration
@pytest.mark.covers("#70 AC5")
def test_the_real_sampled_manager_reaches_the_verdict_through_the_loader_and_the_feed() -> None:
    pin = served.pin_of(FIXTURE_ROOT / RUN_ID)
    frames = served.load_managers(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)
    weeks = ep.manager_weeks(frames.picks, frames.gameweeks, frames.ranked_counts)
    assert set(weeks["gw"]) == {4, 5, 6, 7}
    assert weeks["band"].dropna().isin(verdict.BANDS).all()

    panel = ep.evaluation_panel(weeks)
    assert not panel.empty
    table = _feed(panel, frames.gameweeks)
    assert set(table["manager_id"]) == {MANAGER}
    assert verdict.primary_verdict(table, n_resamples=100, apply_rerun=False).groups == verdict.GROUPS
