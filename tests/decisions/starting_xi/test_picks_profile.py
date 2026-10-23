"""Manager picks data profile (`decisions/starting_xi/picks_profile.py`).

Two kinds of input. Hand-built frames pin the arithmetic: decile edges, the chi-square, transfer
buckets. The real sample (`fixtures/manager_picks_sample/`, 13 panel managers, GW1-7, IDs only)
pins the semantics the captured data forces: an unranked team reported as 0 as well as null, and
a `slot` that is the lineup after auto-subs. `fixtures/manager_picks_scored_week/` adds one more
panel manager, kept apart so the sample's counts stay put: nothing changes in GW1-6, one transfer
in GW7. Every expectation on the sample was read off the raw entry-picks payloads, not off this
module's output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import picks_profile as pp

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).parent / "fixtures" / "manager_picks_sample"
SCORED_WEEK = Path(__file__).parent / "fixtures" / "manager_picks_scored_week"

ALWAYS_UNRANKED = 1471061  # overall_rank 0 in all seven gameweeks
NULL_RANK = 1276382  # ranked at GW1, null at GW4, 0 in every other week
DROPPED_OUT = 2656519  # ranked GW1-5, 0 at GW6-7
JOINED_GW3 = 9955594
JOINED_GW5 = 10712305
SUBBED_ONLY = 340315  # no transfer, chip or lineup change; one auto-sub at GW6
MOVED_BENCH = 65461  # swapped 260 and 115 between XI and bench GW5 -> GW6, nothing else
CAPTAIN_ONLY = 6024858  # GW5's only change is the captain; XI changed at GW3-4, nothing after GW5
SELF = 8450051
CHANGED_ONLY_GW7 = 4008439  # in SCORED_WEEK: one transfer at GW7, auto-subs only before it


@pytest.fixture(scope="module")
def gameweeks() -> pd.DataFrame:
    return pd.DataFrame(json.loads((SAMPLE / "gameweeks.json").read_text()))


@pytest.fixture(scope="module")
def picks() -> pd.DataFrame:
    return pd.read_csv(SAMPLE / "picks.csv")


@pytest.fixture(scope="module")
def ranks() -> pd.DataFrame:
    frame = pd.read_csv(SAMPLE / "ranks.csv")
    frame["overall_rank"] = frame["overall_rank"].astype("Int64")
    return frame


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _payload(root: Path, gw: int, entry: int, run: str, history: dict[str, object] | None) -> None:
    path = root / str(gw) / str(entry) / run.split("T")[0] / run / "payload.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"entry_history": history, "picks": []}))


def test_read_raw_ranks_keeps_nulls_and_takes_the_latest_capture(tmp_path: Path) -> None:
    _payload(tmp_path, 1, 11, "20261001T000000Z-a", {"overall_rank": 500})
    _payload(tmp_path, 1, 11, "20261002T000000Z-b", {"overall_rank": 400})
    _payload(tmp_path, 2, 11, "20261009T000000Z-c", {"overall_rank": None})
    _payload(tmp_path, 2, 12, "20261009T000000Z-c", None)
    frame = pp.read_raw_ranks(tmp_path)
    assert frame[["gameweek", "entry_id"]].values.tolist() == [[1, 11], [2, 11], [2, 12]]
    assert frame["overall_rank"].tolist()[0] == 400
    assert frame["overall_rank"].isna().tolist() == [False, True, True]


def test_read_ranked_counts_skips_unranked_gameweeks(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    events = [{"id": 1, "ranked_count": 90}, {"id": 2, "ranked_count": 0}]
    path.write_text(json.dumps({"events": events}))
    assert pp.read_ranked_counts(path) == {1: 90}


def test_import_closure_reaches_no_platform_layer() -> None:
    program = (
        "import sys, decisions.starting_xi.picks_profile\n"
        "print(sorted({m.split('.')[0] for m in sys.modules} & {'dal', 'model', 'research', 'serve', 'warehouse'}))"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    assert child.stdout.strip() == "[]"


# ---------------------------------------------------------------------------
# Coverage, auto-subs, chips, transfers
# ---------------------------------------------------------------------------


def test_coverage_counts_late_joiners_in_their_first_week(gameweeks: pd.DataFrame) -> None:
    out = pp.coverage(gameweeks)
    assert out["manager_weeks"].tolist() == [11, 11, 12, 12, 13, 13, 13]
    assert out["manager_weeks_self"].tolist() == [1] * 7
    assert out["new_managers"].tolist() == [11, 0, 1, 0, 1, 0, 0]
    assert out["managers_to_date"].tolist() == [11, 11, 12, 12, 13, 13, 13]
    assert pp.gaps(gameweeks).empty


def test_gaps_lists_a_missing_middle_week() -> None:
    frame = pd.DataFrame({"entry_id": [1, 1, 1, 2], "gameweek": [1, 2, 4, 3]})
    assert pp.gaps(frame).to_dict("records") == [{"entry_id": 1, "missing": [3]}]


def test_auto_sub_share_at_gw7(gameweeks: pd.DataFrame) -> None:
    gw7 = pp.auto_sub_share(gameweeks).loc[7]
    assert (gw7["manager_weeks"], gw7["with_auto_sub"]) == (13, 6)
    assert gw7["share"] == pytest.approx(6 / 13)


def test_chip_share_rows_sum_to_one_and_reject_an_unknown_chip(gameweeks: pd.DataFrame) -> None:
    share = pp.chip_share(gameweeks)
    np.testing.assert_allclose(share.sum(axis=1), 1.0)
    assert share.loc[7, "3xc"] == pytest.approx(1 / 13)
    assert share.loc[2, "bboost"] == pytest.approx(1 / 11)
    with pytest.raises(ValueError, match="unknown chips"):
        pp.chip_share(pd.DataFrame({"gameweek": [1], "active_chip": ["triple"]}))


def test_transfers_distribution_buckets_caps_and_sets_aside_unlimited_weeks(gameweeks: pd.DataFrame) -> None:
    out = pp.transfers_distribution(gameweeks)
    assert out.loc[7].to_dict() == {"0": 10, "1": 1, "2": 0, "3": 1, "4+": 1, "wildcard/free hit": 0, "took_hit": 2}
    # GW5: 323566's Wildcard is set aside; 8450051's Bench Boost week stays in its bucket (4+).
    assert out.loc[5, "wildcard/free hit"] == 1
    assert out.drop(columns="took_hit").sum(axis=1).tolist() == pp.coverage(gameweeks)["manager_weeks"].tolist()


def test_transfers_summary_excludes_unlimited_weeks() -> None:
    frame = pd.DataFrame(
        {
            "gameweek": [2, 2, 2, 2],
            "active_chip": [None, None, "wildcard", "3xc"],
            "event_transfers": [0, 2, 15, 1],
        }
    )
    row = pp.transfers_summary(frame).loc[2]
    assert row["manager_weeks"] == 3
    assert row["mean"] == pytest.approx(1.0)
    assert row["max"] == 2
    assert row["share_any"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Ranks
# ---------------------------------------------------------------------------


def test_unranked_counts_zero_as_well_as_null(ranks: pd.DataFrame) -> None:
    out = pp.unranked(ranks)
    by_entry = out.groupby("entry_id")["gameweek"].apply(list).to_dict()
    assert by_entry == {
        NULL_RANK: [2, 3, 4, 5, 6, 7],
        ALWAYS_UNRANKED: [1, 2, 3, 4, 5, 6, 7],
        DROPPED_OUT: [6, 7],
    }
    assert out.loc[out["kind"] == "null", ["entry_id", "gameweek"]].values.tolist() == [[NULL_RANK, 4]]


def test_latest_ranks_never_carry_an_older_rank_forward(ranks: pd.DataFrame) -> None:
    latest = pp.latest_ranks(ranks).set_index("entry_id")
    assert (latest["gameweek"] == 7).all()
    assert set(latest.index[~latest["ranked"]]) == {ALWAYS_UNRANKED, NULL_RANK, DROPPED_OUT}


def test_rank_deciles_edges() -> None:
    deciles = pp.rank_deciles(pd.Series([1, 10, 11, 50, 51, 91, 100]), ranked_count=100)
    assert deciles.tolist() == [1, 1, 2, 5, 6, 10, 10]


@pytest.mark.parametrize("rank", [0, 101])
def test_rank_deciles_refuses_a_rank_outside_the_population(rank: int) -> None:
    with pytest.raises(ValueError, match="outside"):
        pp.rank_deciles(pd.Series([rank]), ranked_count=100)


def test_decile_uniformity_matches_the_formula() -> None:
    flat = pp.decile_uniformity(pd.Series(np.repeat(np.arange(1, 11), 5)))
    assert (flat.statistic, flat.p_value, flat.dof) == (0.0, 1.0, 9)

    observed = np.array([20, 10, 10, 10, 10, 10, 10, 10, 10, 0])
    deciles = pd.Series(np.repeat(np.arange(1, 11), observed))
    result = pp.decile_uniformity(deciles)
    assert result.counts.tolist() == observed.tolist()
    assert result.statistic == pytest.approx(((observed - 10) ** 2 / 10).sum())


def test_rank_screen_counts_only_ranked_managers() -> None:
    latest = pd.DataFrame(
        {"overall_rank": pd.array([5, 50, 500, 0], dtype="Int64"), "ranked": [True, True, True, False]}
    )
    assert pp.rank_screen_counts(latest, (10, 100, 1000)).to_dict() == {10: 1, 100: 2, 1000: 3}


# ---------------------------------------------------------------------------
# Activity screen
# ---------------------------------------------------------------------------


def test_picked_xi_undoes_auto_subs() -> None:
    picks = pd.DataFrame(
        {
            "entry_id": 1,
            "gameweek": 1,
            "slot": range(1, 16),
            "fpl_id": range(101, 116),
            "is_auto_sub_in": [s == 4 for s in range(1, 16)],
            "is_auto_sub_out": [s == 13 for s in range(1, 16)],
        }
    )
    assert pp.picked_xi(picks)[(1, 1)] == frozenset(set(range(101, 112)) - {104} | {113})


def test_an_auto_sub_alone_is_not_an_xi_change(picks: pd.DataFrame, gameweeks: pd.DataFrame) -> None:
    # The lineup as served changes GW5 -> GW6 only because of the auto-sub, which is what the
    # screen must not count.
    served = picks[(picks["entry_id"] == SUBBED_ONLY) & (picks["slot"] <= 11)].groupby("gameweek")["fpl_id"]
    assert set(served.get_group(5)) != set(served.get_group(6))

    screen = pp.activity_screen(gameweeks, picks, scored_gw=7).set_index("entry_id")
    assert screen.loc[SUBBED_ONLY, ["evaluable", "passes", "changed_xi"]].tolist() == [True, False, False]


def test_activity_screen_components(picks: pd.DataFrame, gameweeks: pd.DataFrame) -> None:
    # Scoring GW7 looks at the changes made in GW4-6.
    screen = pp.activity_screen(gameweeks, picks, scored_gw=7).set_index("entry_id")
    flags = ["changed_xi", "changed_captain", "transferred", "chip"]
    assert screen.loc[MOVED_BENCH, flags].tolist() == [True, False, False, False]
    assert screen.loc[CAPTAIN_ONLY, flags].tolist() == [True, True, False, False]
    assert screen.loc[SELF, "passes"]
    assert screen.loc[JOINED_GW3, "evaluable"]
    assert not screen.loc[JOINED_GW5, ["evaluable", "passes"]].any()


def test_a_change_only_in_the_scored_week_is_not_counted(picks: pd.DataFrame, gameweeks: pd.DataFrame) -> None:
    extra_gw = pd.DataFrame(json.loads((SCORED_WEEK / "gameweeks.json").read_text()))
    extra_picks = pd.read_csv(SCORED_WEEK / "picks.csv")
    gameweeks = pd.concat([gameweeks, extra_gw], ignore_index=True)
    picks = pd.concat([picks, extra_picks], ignore_index=True)
    assert extra_gw.set_index("gameweek")["event_transfers"].gt(0).tolist() == [False] * 6 + [True]

    screen = pp.activity_screen(gameweeks, picks, scored_gw=7).set_index("entry_id")
    row = screen.loc[CHANGED_ONLY_GW7]
    assert (row["screened"], row["evaluable"], row["passes"], row["transferred"]) == (True, True, False, False)


def test_gameweeks_one_to_four_are_not_screened(picks: pd.DataFrame, gameweeks: pd.DataFrame) -> None:
    # GW1 has no measurable change, so GW2-4 is the first full window of three and it scores GW5.
    assert pp.FIRST_SCREENED_GW == 5
    for gw in range(1, 5):
        screen = pp.activity_screen(gameweeks, picks, scored_gw=gw)
        captured = set(gameweeks.loc[gameweeks["gameweek"] == gw, "entry_id"])
        assert set(screen["entry_id"]) == captured
        assert not screen["screened"].any()
        assert screen["passes"].all()
    gw5 = pp.activity_screen(gameweeks, picks, scored_gw=5).set_index("entry_id")
    assert gw5["screened"].all()
    assert not gw5.loc[[SUBBED_ONLY, ALWAYS_UNRANKED], "passes"].any()
    # GW5 needs a capture in GW1-4; GW3 is too late.
    assert not gw5.loc[[JOINED_GW3, JOINED_GW5], "evaluable"].any()


def test_activity_counts_add_up(picks: pd.DataFrame, gameweeks: pd.DataFrame) -> None:
    counts = pp.activity_counts(pp.activity_screen(gameweeks, picks, scored_gw=7))
    assert (counts["managers"], counts["evaluable"]) == (13, 12)
    assert counts["passes"] + counts["fails"] == counts["evaluable"]
    assert counts["passes"] <= counts[["changed_xi", "changed_captain", "transferred", "chip"]].sum()
