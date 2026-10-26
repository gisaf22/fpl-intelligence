"""Acceptance tests for D2's fixture count as scheduled at the deadline (#59).

D2 multiplies its rate by gameweek N's coming fixture count. That count must be the one scheduled
at N's deadline (`fct_player_gameweek.fixture_count_at_deadline`, gisaf22/fpl-warehouse#221), not
the realised count, while both elevens are still scored on realised points. Each test writes a
constructed 2026-27 publish in the served schema and reads it through `warehouse.served.load`, so
the loader, the rule and the harness's selection are all on the path a run takes.

The squad is one legal 15 (2 GK, 5 DEF, 5 MID, 3 FWD), one club each except `MARGINAL` and
`TEAMMATE`, who share `SHARED_CLUB`. Every past gameweek is a single fixture at a fixed
points-per-fixture, so D2's rate is that number:

- nine outfielders at 6 and three at 3, so the XI's tenth outfielder is the best of the three 3s
  or `MARGINAL`;
- `MARGINAL` (MID) at 2: in the XI on a double (2 x 2 = 4 > 3), out of it on a single (2 < 3);
- `TEAMMATE` (MID) at 6: always in the XI while his club has a fixture, so a change to the shared
  club's realised fixtures always moves the eleven's realised points.

GW1-2 have no capture before their deadline, so their `fixture_count_at_deadline` is NULL for
every player, as on the live publish.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from decisions.starting_xi import harness, orderings, rankers
from warehouse import served

pytestmark = pytest.mark.unit

SEASON = "2026-27"
RUN_ID = "synthetic-59"
SEED = 0
SCORED_GW = 5
UNCAPTURED_GWS = (1, 2)
D2 = "ppg_fixture_season"

MARGINAL = 12
TEAMMATE = 10
SHARED_CLUB = 12

# player_id -> (position_id, club, points per fixture)
PLAYERS: Mapping[int, tuple[int, int, int]] = {
    1: (1, 1, 6),
    2: (1, 2, 1),
    3: (2, 3, 6),
    4: (2, 4, 6),
    5: (2, 5, 6),
    6: (2, 6, 6),
    7: (2, 7, 3),
    8: (3, 8, 6),
    9: (3, 9, 6),
    TEAMMATE: (3, SHARED_CLUB, 6),
    11: (3, 11, 3),
    MARGINAL: (3, SHARED_CLUB, 2),
    13: (4, 13, 6),
    14: (4, 14, 6),
    15: (4, 15, 3),
}


@dataclass(frozen=True)
class ClubWeek:
    """One club-gameweek: the count scheduled at the deadline, and the fixtures actually played."""

    at_deadline: int | None
    played: int


@dataclass(frozen=True)
class Publish:
    """A constructed publish: every club-gameweek is a single fixture, scheduled and played, except
    the overrides. GW1-2 carry no at-deadline count. `null_at_deadline` blanks one player's count."""

    overrides: Mapping[tuple[int, int], ClubWeek] = field(default_factory=dict)
    null_at_deadline: frozenset[tuple[int, int]] = frozenset()

    def club_week(self, club: int, gw: int) -> ClubWeek:
        default = ClubWeek(at_deadline=None if gw in UNCAPTURED_GWS else 1, played=1)
        return self.overrides.get((club, gw), default)


def _int32(*names: str) -> list[tuple[str, pa.DataType]]:
    return [(name, pa.int32()) for name in names]


def _write(root: Path, publish: Publish, last_gw: int = SCORED_GW) -> served.Pin:
    target = root / RUN_ID
    target.mkdir(parents=True)
    fixture_rows: list[dict[str, object]] = []
    gameweek_rows: list[dict[str, object]] = []
    for gw in range(1, last_gw + 1):
        for player_id, (_, club, per_fixture) in PLAYERS.items():
            week = publish.club_week(club, gw)
            for leg in range(week.played):
                fixture_rows.append(
                    {
                        "season": SEASON,
                        "fpl_id": player_id,
                        "gameweek": gw,
                        "fixture_id": gw * 100 + club * 2 + leg,
                        "team_fpl_id": club,
                        "minutes": 90,
                        "starts": 1,
                        "total_points": per_fixture,
                    }
                )
            played = week.played > 0
            gameweek_rows.append(
                {
                    "season": SEASON,
                    "fpl_id": player_id,
                    "gameweek": gw,
                    "fixture_count": week.played,
                    "total_points": per_fixture * week.played if played else None,
                    "minutes": 90 * week.played if played else None,
                    "starts": week.played if played else None,
                    "value": 45,
                    "selected": 1000,
                    "fixture_count_at_deadline": (
                        None if (player_id, gw) in publish.null_at_deadline else week.at_deadline
                    ),
                }
            )
    fixture_schema = pa.schema(
        [
            ("season", pa.string()),
            *_int32("fpl_id", "gameweek", "fixture_id", "team_fpl_id", "minutes", "starts", "total_points"),
        ]
    )
    gameweek_schema = pa.schema(
        [
            ("season", pa.string()),
            *_int32(
                "fpl_id",
                "gameweek",
                "fixture_count",
                "total_points",
                "minutes",
                "starts",
                "value",
                "selected",
                "fixture_count_at_deadline",
            ),
        ]
    )
    pq.write_table(pa.Table.from_pylist(fixture_rows, schema=fixture_schema), target / "fct_player_fixture.parquet")
    pq.write_table(pa.Table.from_pylist(gameweek_rows, schema=gameweek_schema), target / "fct_player_gameweek.parquet")
    pq.write_table(
        pa.Table.from_pylist(
            [{"season": SEASON, "fpl_id": p, "position_id": position} for p, (position, _, _) in PLAYERS.items()],
            schema=pa.schema([("season", pa.string()), *_int32("fpl_id", "position_id")]),
        ),
        target / "dim_player.parquet",
    )
    manifest = {"run_id": RUN_ID, "contract_version": served.CONTRACT_VERSION, "seasons": [SEASON]}
    (target / served.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return served.pin_of(target)


def _load(tmp_path: Path, publish: Publish, name: str) -> served.Frames:
    root = tmp_path / name
    return served.load(SEASON, pin=_write(root, publish), snapshot_root=root)


def _squad(gw: int, squad_id: str = "manager-1") -> pd.DataFrame:
    return pd.DataFrame({"gw": gw, "squad_id": squad_id, "player_id": list(PLAYERS)})


def _d2_week(frames: served.Frames, gw: int = SCORED_GW) -> pd.Series:
    """D2's chosen eleven at `gw` for the squad, scored on realised points (T2's row)."""
    result = harness.run(_squad(gw), rankers.rules(SEED)[D2], orderings.PRE_REGISTERED_ORDERINGS, frames, (gw, gw))
    rows = result.squad_weeks
    assert len(rows) == 1
    return rows.iloc[0]


# --- AC1: a postponement observed after the deadline leaves D2's eleven unchanged ---

AFTER_DEADLINE = {
    # A double with one leg postponed after the deadline: still 2 at the deadline, 1 played.
    "double_leg_postponed": (ClubWeek(at_deadline=2, played=2), ClubWeek(at_deadline=2, played=1)),
    # A fixture rescheduled into N after the deadline: 1 at the deadline, 2 played.
    "fixture_added": (ClubWeek(at_deadline=1, played=1), ClubWeek(at_deadline=1, played=2)),
    # A single postponed after the deadline: 1 at the deadline, none played. Also reaches the
    # harness's no-fixture tier, which must read the deadline count too.
    "single_postponed": (ClubWeek(at_deadline=1, played=1), ClubWeek(at_deadline=1, played=0)),
}


@pytest.mark.covers("#59 AC1")
@pytest.mark.parametrize("case", list(AFTER_DEADLINE))
def test_a_postponement_after_the_deadline_leaves_d2s_eleven_unchanged_and_moves_its_points(
    tmp_path: Path, case: str
) -> None:
    as_scheduled, as_played = AFTER_DEADLINE[case]
    before = _d2_week(_load(tmp_path, Publish({(SHARED_CLUB, SCORED_GW): as_scheduled}), "before"))
    after = _d2_week(_load(tmp_path, Publish({(SHARED_CLUB, SCORED_GW): as_played}), "after"))

    assert after["chosen_xi"] == before["chosen_xi"]
    assert after["no_subs_xi_points"] != before["no_subs_xi_points"]


# --- AC2: a postponement known before the deadline changes D2's eleven (positive control) ---

BEFORE_DEADLINE = {
    # A blank known before the deadline: 0 at the deadline, none played.
    "blank_known": (ClubWeek(at_deadline=1, played=1), ClubWeek(at_deadline=0, played=0)),
    # A double cut to a single before the deadline.
    "double_cut_to_single": (ClubWeek(at_deadline=2, played=2), ClubWeek(at_deadline=1, played=1)),
}


@pytest.mark.covers("#59 AC2")
@pytest.mark.parametrize("case", list(BEFORE_DEADLINE))
def test_a_postponement_known_before_the_deadline_changes_d2s_eleven(tmp_path: Path, case: str) -> None:
    baseline, known = BEFORE_DEADLINE[case]
    before = _d2_week(_load(tmp_path, Publish({(SHARED_CLUB, SCORED_GW): baseline}), "before"))
    after = _d2_week(_load(tmp_path, Publish({(SHARED_CLUB, SCORED_GW): known}), "after"))

    assert after["chosen_xi"] != before["chosen_xi"]


# --- AC3: GW1-2 have no at-deadline count, so they use the realised count and are flagged ---


@pytest.mark.covers("#59 AC3")
def test_a_gameweek_with_no_count_at_the_deadline_uses_the_realised_count_and_is_flagged(tmp_path: Path) -> None:
    # GW2: the shared club played a double, with no capture before the deadline. GW4: the at-deadline
    # count (2) and the realised one (1) differ, so a fallback applied there would show.
    publish = Publish(
        {
            (SHARED_CLUB, 2): ClubWeek(at_deadline=None, played=2),
            (SHARED_CLUB, 4): ClubWeek(at_deadline=2, played=1),
        }
    )
    gameweek = _load(tmp_path, publish, "snapshot").gameweek.set_index(["player_id", "gw"])

    uncaptured = gameweek[gameweek.index.get_level_values("gw").isin(UNCAPTURED_GWS)]
    assert uncaptured["deadline_fixture_count"].notna().all(), "a NULL count reaches the rule"
    assert (uncaptured["deadline_fixture_count"] == uncaptured["fixture_count"]).all()
    assert gameweek.loc[(MARGINAL, 2), "deadline_fixture_count"] == 2
    assert uncaptured["deadline_count_is_realised"].all()

    captured = gameweek[~gameweek.index.get_level_values("gw").isin(UNCAPTURED_GWS)]
    assert not captured["deadline_count_is_realised"].any()
    assert gameweek.loc[(MARGINAL, 4), "deadline_fixture_count"] == 2


@dataclass(frozen=True)
class _EveryWeek:
    """A ranker that scores every gameweek, so the harness can select an eleven at GW1-2 (D2's
    declared window starts at GW4)."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _score_every_week(frames: served.Frames) -> _EveryWeek:
    scores = frames.gameweek.loc[:, ["player_id", "gw"]].assign(score=frames.gameweek["player_id"].astype(float))
    return _EveryWeek(name="every_week", window=(1, 38), scores=scores)


@pytest.mark.covers("#59 AC3")
@pytest.mark.parametrize(("gw", "flagged"), [(1, True), (2, True), (3, False), (SCORED_GW, False)])
def test_a_manager_week_with_no_count_at_the_deadline_is_flagged(tmp_path: Path, gw: int, flagged: bool) -> None:
    frames = _load(tmp_path, Publish(), "snapshot")
    result = harness.run(_squad(gw), _score_every_week, orderings.PRE_REGISTERED_ORDERINGS, frames, (gw, gw))

    assert result.squad_weeks["deadline_count_is_realised"].tolist() == [flagged]


# --- AC5: a squad player with no at-deadline count at GW3+ is a data defect ---


def _squads(gw: int) -> pd.DataFrame:
    return pd.concat([_squad(gw, "manager-1"), _squad(gw, "manager-2")], ignore_index=True)


@pytest.mark.covers("#59 AC5")
def test_a_squad_player_with_no_count_at_the_deadline_fails_and_names_the_manager_weeks(tmp_path: Path) -> None:
    frames = _load(tmp_path, Publish(null_at_deadline=frozenset({(MARGINAL, 4)})), "snapshot")
    squads = pd.concat([_squads(3), _squads(4)], ignore_index=True)

    with pytest.raises(served.ServedContractError) as raised:
        harness.assert_deadline_counts_known(squads, frames.gameweek)

    message = str(raised.value)
    assert "('manager-1', 4)" in message and "('manager-2', 4)" in message
    assert "', 3)" not in message, "a manager-week without the defect is listed"


@pytest.mark.covers("#59 AC5")
def test_a_null_count_for_a_player_in_no_squad_does_not_fail(tmp_path: Path) -> None:
    frames = _load(tmp_path, Publish(null_at_deadline=frozenset({(MARGINAL, 4)})), "snapshot")
    squads = _squad(4)
    squads = squads[squads["player_id"] != MARGINAL]

    harness.assert_deadline_counts_known(squads, frames.gameweek)


@pytest.mark.covers("#59 AC5")
@pytest.mark.parametrize("gw", UNCAPTURED_GWS)
def test_a_null_count_in_a_gameweek_with_no_capture_takes_the_fallback_not_this_check(tmp_path: Path, gw: int) -> None:
    frames = _load(tmp_path, Publish(), "snapshot")

    harness.assert_deadline_counts_known(_squads(gw), frames.gameweek)


@pytest.mark.covers("#59 AC5")
def test_the_load_path_runs_the_check(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    pin = _write(root, Publish(null_at_deadline=frozenset({(MARGINAL, SCORED_GW)})))

    with pytest.raises(served.ServedContractError, match=r"\('manager-1', 5\)"):
        harness.build(
            _squad(SCORED_GW),
            rankers.rules(SEED)[D2],
            orderings.PRE_REGISTERED_ORDERINGS,
            (SCORED_GW, SCORED_GW),
            season=SEASON,
            pin=pin,
            snapshot_root=root,
        )
