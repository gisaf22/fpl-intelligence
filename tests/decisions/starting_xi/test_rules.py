"""Acceptance tests for the Stage 3 rule grid (#30).

Definitions: `CARD.md` §3 and #30's Design decisions. Every rule is called as
`rankers.rules(seed)[name](frames)` on the pinned warehouse frames (`warehouse.served.Frames`).

Real sample: `warehouse/fixtures/39064033745`, season 2025-26 (described in `tests/warehouse/test_served.py`).

- `fpl_id` 691, MID, enters GW2. Doubles in GW33 (8 points, 2 appearances, 2 starts) and blanks in GW34.
  No appearance in GW2 or GW26.
- `fpl_id` 149, DEF, enters GW1. Doubles in GW33 and blanks in GW34. Appears only in GW6, 10, 11 and 12,
  and starts only in GW12 (3 points).

The hand values below were worked out from those rows by plain sums, not by the code under test.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from decisions.starting_xi import rankers
from decisions.starting_xi.harness import BenchPlayer, rank_squad, select_xi
from domain.fpl_squad import POSITIONS, SQUAD_SELECT
from warehouse import served

pytestmark = pytest.mark.unit

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "warehouse" / "fixtures"
RUN_ID = "39064033745"
SEASON = "2025-26"
SEED = 20261017
LATE_ENTRANT = 691
FRINGE_DEFENDER = 149

DETERMINISTIC_RULES = (
    "ppg_gameweek_season",
    "ppg_gameweek_last3",
    "ppg_fixture_season",
    "ppg_fixture_last3",
    "ppg_appearance_season",
    "ppg_appearance_last3",
    "ppg_start_season",
    "ppg_start_last3",
    "starts_rate_x_points_per_appearance",
)


@pytest.fixture(scope="module")
def frames() -> served.Frames:
    return served.load(SEASON, pin=served.pin_of(FIXTURE_ROOT / RUN_ID), snapshot_root=FIXTURE_ROOT)


def _score(name: str, frames: served.Frames, player_id: int, gw: int, seed: int = SEED) -> float | None:
    scores = rankers.rules(seed)[name](frames).scores
    row = scores[(scores["player_id"] == player_id) & (scores["gw"] == gw)]
    assert len(row) == 1, f"{name} emits {len(row)} rows for player {player_id} gw {gw}"
    value = row["score"].iloc[0]
    return None if pd.isna(value) else float(value)


def _synthetic(players: dict[int, tuple[int, dict[int, list[tuple[int, int, int]]]]]) -> served.Frames:
    """Frames from `{player_id: (position_id, {gw: [(minutes, starts, points) per fixture]})}`.

    An empty fixture list is a blank. The gameweek frame carries the per-gameweek sums, the
    same way `fct_player_gameweek` does.
    """
    fixture_rows, gameweek_rows = [], []
    fixture_id = 0
    for player_id, (position_id, weeks) in players.items():
        entry = min(gw for gw, fixtures in weeks.items() if fixtures)
        for gw, fixtures in sorted(weeks.items()):
            for minutes, starts, points in fixtures:
                fixture_id += 1
                fixture_rows.append(
                    {
                        "season": SEASON,
                        "player_id": player_id,
                        "gw": gw,
                        "fixture_id": fixture_id,
                        "team_id": 1,
                        "minutes": minutes,
                        "starts": starts,
                        "total_points": points,
                    }
                )
            gameweek_rows.append(
                {
                    "season": SEASON,
                    "player_id": player_id,
                    "gw": gw,
                    "fixture_count": len(fixtures),
                    "team_id": 1,
                    "position_id": position_id,
                    "price": 5.0,
                    "ownership": 1000,
                    "entry_gw": entry,
                    "minutes": sum(f[0] for f in fixtures) if fixtures else None,
                    "starts": sum(f[1] for f in fixtures) if fixtures else None,
                    "total_points": sum(f[2] for f in fixtures) if fixtures else None,
                }
            )
    return served.Frames(
        fixture=pd.DataFrame(fixture_rows),
        gameweek=pd.DataFrame(gameweek_rows),
        pin=served.Pin(run_id="synthetic", sha256={}),
    )


# --- AC1: every rule matches its hand value ---


@pytest.mark.covers("#30 AC1")
@pytest.mark.parametrize(
    ("name", "player_id", "expected"),
    [
        # 691 scored at GW35 (one fixture). History GW2-34: 120 points over 33 gameweeks elapsed,
        # 33 team fixtures, 31 appearances and 26 starts.
        ("ppg_gameweek_season", LATE_ENTRANT, 120 / 33),
        ("ppg_gameweek_last3", LATE_ENTRANT, (2 + 8 + 0) / 3),  # GW32, 33, 34 (blank counts as 0)
        ("ppg_fixture_season", LATE_ENTRANT, 120 / 33),
        ("ppg_fixture_last3", LATE_ENTRANT, (2 + 2 + 8) / (1 + 1 + 2)),  # GW31-33, skipping the blank
        ("ppg_appearance_season", LATE_ENTRANT, 120 / 31),
        ("ppg_appearance_last3", LATE_ENTRANT, (2 + 2 + 8) / (1 + 1 + 2)),
        ("ppg_start_season", LATE_ENTRANT, 109 / 26),
        ("ppg_start_last3", LATE_ENTRANT, (2 + 2 + 8) / (1 + 1 + 2)),
        # Starts rate over GW31-33 = 4 starts / 4 fixtures = 1; season points per appearance 120/31.
        ("starts_rate_x_points_per_appearance", LATE_ENTRANT, 1 * 120 / 31),
        # 149 scored at GW35: appearances in GW6, 10, 11, 12 (1+1+1+3 points); one start (GW12, 3 points).
        ("ppg_gameweek_season", FRINGE_DEFENDER, 6 / 34),
        ("ppg_fixture_season", FRINGE_DEFENDER, 6 / 34),
        ("ppg_appearance_season", FRINGE_DEFENDER, 6 / 4),
        ("ppg_appearance_last3", FRINGE_DEFENDER, (1 + 1 + 3) / 3),  # GW10, 11, 12
        ("ppg_start_season", FRINGE_DEFENDER, 3 / 1),
        ("starts_rate_x_points_per_appearance", FRINGE_DEFENDER, 0 * 6 / 4),
    ],
)
def test_each_rule_scores_the_real_sample_at_its_hand_value(
    frames: served.Frames, name: str, player_id: int, expected: float
) -> None:
    assert _score(name, frames, player_id, 35) == pytest.approx(expected)


@pytest.mark.covers("#30 AC1")
def test_an_appearance_counts_per_fixture_played_in_a_double_gameweek() -> None:
    # GW1-3 single fixtures, each played (2 points). GW4 is a double: played one fixture (6 points),
    # unused in the other. Scored at GW5: 12 points over 4 appearances, not 5 (summed minutes > 0
    # would count the double as one appearance either way, so the fixture rows decide).
    weeks = {1: [(90, 1, 2)], 2: [(90, 1, 2)], 3: [(90, 1, 2)], 4: [(90, 1, 6), (0, 0, 0)], 5: [(90, 1, 2)]}
    frames = _synthetic({7: (3, weeks)})
    assert _score("ppg_appearance_season", frames, 7, 5) == pytest.approx(12 / 4)
    assert _score("ppg_appearance_last3", frames, 7, 5) == pytest.approx((2 + 2 + 6) / 3)


# --- AC2: a coming double scales D2-D4 by 2 and leaves D1 unscaled ---


@pytest.mark.covers("#30 AC2")
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # 691 scored at GW33, a double. History GW2-32: 112 points over 31 gameweeks, 31 fixtures,
        # 29 appearances, 24 starts; GW30-32 hold 0+2+2 points over one fixture each.
        ("ppg_gameweek_season", 112 / 31),
        ("ppg_gameweek_last3", 4 / 3),
        ("ppg_fixture_season", 2 * 112 / 31),
        ("ppg_fixture_last3", 2 * 4 / 3),
        ("ppg_appearance_season", 2 * 112 / 29),
        ("ppg_appearance_last3", 2 * 4 / 3),
        ("ppg_start_season", 2 * 101 / 24),
        ("ppg_start_last3", 2 * 4 / 3),
        ("starts_rate_x_points_per_appearance", 2 * 1 * 112 / 29),
    ],
)
def test_a_coming_double_scales_per_fixture_rules_by_two_and_not_plain_ppg(
    frames: served.Frames, name: str, expected: float
) -> None:
    assert _score(name, frames, LATE_ENTRANT, 33) == pytest.approx(expected)


# --- AC3: a past double is one gameweek elapsed; a past blank is 0 points ---


@pytest.mark.covers("#30 AC3")
def test_plain_ppg_counts_a_past_double_once_and_a_past_blank_as_zero(frames: served.Frames) -> None:
    # 691 at GW35: GW2-34 is 33 gameweeks elapsed. Counting the GW33 double twice would give
    # 120/34; skipping the GW34 blank would give 120/32.
    assert _score("ppg_gameweek_season", frames, LATE_ENTRANT, 35) == pytest.approx(120 / 33)
    assert _score("ppg_gameweek_last3", frames, LATE_ENTRANT, 35) == pytest.approx(10 / 3)


# --- AC4: nothing at or after the scored gameweek moves a score ---


def _tampered(frames: served.Frames, from_gw: int) -> served.Frames:
    """Outcomes at gw >= `from_gw` changed. `fixture_count` stays: it is known before the deadline."""
    fixture, gameweek = frames.fixture.copy(), frames.gameweek.copy()
    for frame in (fixture, gameweek):
        late = frame["gw"] >= from_gw
        frame.loc[late, "total_points"] = frame.loc[late, "total_points"] + 50
        frame.loc[late, "minutes"] = 90
        frame.loc[late, "starts"] = 1
    return served.Frames(fixture=fixture, gameweek=gameweek, pin=frames.pin)


@pytest.mark.covers("#30 AC4")
@pytest.mark.parametrize("name", [*DETERMINISTIC_RULES, "random"])
@pytest.mark.parametrize("gw", [5, 33, 35])
def test_changing_data_from_the_scored_gameweek_on_leaves_the_score_unchanged(
    frames: served.Frames, name: str, gw: int
) -> None:
    before = rankers.rules(SEED)[name](frames).scores
    after = rankers.rules(SEED)[name](_tampered(frames, gw)).scores
    pd.testing.assert_frame_equal(
        before[before["gw"] == gw].reset_index(drop=True), after[after["gw"] == gw].reset_index(drop=True)
    )


# --- AC5: no history in the window, or fewer than 3 qualifying past games for last-3, is NULL ---


@pytest.mark.covers("#30 AC5")
@pytest.mark.parametrize(
    ("name", "player_id", "gw"),
    [
        # 149 at GW5: no appearance or start in GW1-4.
        ("ppg_appearance_season", FRINGE_DEFENDER, 5),
        ("ppg_appearance_last3", FRINGE_DEFENDER, 5),
        ("ppg_start_season", FRINGE_DEFENDER, 5),
        ("ppg_start_last3", FRINGE_DEFENDER, 5),
        ("starts_rate_x_points_per_appearance", FRINGE_DEFENDER, 5),
        # 149 at GW35: one start in GW1-34, so fewer than 3 for last-3.
        ("ppg_start_last3", FRINGE_DEFENDER, 35),
        # 691 at GW4: two gameweeks elapsed (GW2, 3), so fewer than 3 for last-3.
        ("ppg_gameweek_last3", LATE_ENTRANT, 4),
        ("ppg_fixture_last3", LATE_ENTRANT, 4),
        ("ppg_appearance_last3", LATE_ENTRANT, 4),
        ("ppg_start_last3", LATE_ENTRANT, 4),
        ("starts_rate_x_points_per_appearance", LATE_ENTRANT, 4),
    ],
)
def test_a_rule_with_too_little_history_emits_null(frames: served.Frames, name: str, player_id: int, gw: int) -> None:
    assert _score(name, frames, player_id, gw) is None


@pytest.mark.covers("#30 AC5")
@pytest.mark.parametrize("name", DETERMINISTIC_RULES)
def test_every_rule_is_null_at_a_players_entry_gameweek(name: str) -> None:
    weeks = {gw: [(90, 1, 2)] for gw in range(10, 15)}
    frames = _synthetic({7: (3, weeks)})
    assert _score(name, frames, 7, 10) is None


@pytest.mark.covers("#30 AC5")
def test_last3_needs_three_past_gameweeks_that_hold_the_unit() -> None:
    # Appearances only in GW1 and GW3; GW2 and GW4 unused. Scored at GW5: two qualifying
    # gameweeks for the appearance rule, though four gameweeks have elapsed.
    weeks = {1: [(90, 1, 4)], 2: [(0, 0, 0)], 3: [(90, 1, 4)], 4: [(0, 0, 0)], 5: [(90, 1, 2)]}
    frames = _synthetic({7: (3, weeks)})
    assert _score("ppg_appearance_last3", frames, 7, 5) is None
    assert _score("ppg_gameweek_last3", frames, 7, 5) == pytest.approx((0 + 4 + 0) / 3)


# --- AC6: the random rule is reproducible under a seed and moves with it ---


def _full_squad_frames() -> served.Frames:
    players: dict[int, tuple[int, dict[int, list[tuple[int, int, int]]]]] = {}
    player_id = 100
    for position_id, position in enumerate(POSITIONS, start=1):
        for _ in range(SQUAD_SELECT[position]):
            player_id += 1
            players[player_id] = (position_id, {gw: [(90, 1, 2)] for gw in range(1, 39)})
    return _synthetic(players)


def _random_xis(frames: served.Frames, seed: int) -> dict[int, frozenset[int]]:
    scores = rankers.rules(seed)["random"](frames).scores
    positions = {
        int(row.player_id): POSITIONS[int(row.position_id) - 1]
        for row in frames.gameweek.drop_duplicates("player_id").itertuples()
    }
    xis = {}
    for gw, block in scores.groupby("gw"):
        players = [
            BenchPlayer(player_id=int(p), position=positions[int(p)], score=float(s), no_fixture=False)
            for p, s in zip(block["player_id"], block["score"], strict=True)
        ]
        xis[int(gw)] = select_xi(rank_squad(players), positions)
    return xis


@pytest.mark.covers("#30 AC6")
def test_the_same_seed_picks_the_same_random_xis() -> None:
    frames = _full_squad_frames()
    pd.testing.assert_frame_equal(
        rankers.rules(SEED)["random"](frames).scores, rankers.rules(SEED)["random"](frames).scores
    )
    assert _random_xis(frames, SEED) == _random_xis(frames, SEED)


@pytest.mark.covers("#30 AC6")
def test_a_different_seed_picks_different_random_xis() -> None:
    frames = _full_squad_frames()
    assert _random_xis(frames, SEED) != _random_xis(frames, SEED + 1)
