"""A constructed warehouse publish for the Stage 5 runner's tests (#73), with hand-computable outcomes.

Fifteen players, each at his own club, score a fixed number of points every gameweek, so D2's
season rate ranks them by those points and its eleven is the best legal one: `D2_ELEVEN`, 82
points. In `SURPRISE_GW` three bench players score `SURPRISE_POINTS` each, after the deadline, so D2
cannot see it coming.

Every manager holds the same fifteen and picks an eleven with no auto-subs:

- `TIED` picks D2's eleven: a tie every gameweek.
- `BEATEN` swaps one starter for a bench player: D2 wins, except in `SURPRISE_GW`.
- `BEATEN_MORE` swaps three: D2 wins, except in `SURPRISE_GW`.
- `SELF` is the self cohort: never in the panel.
- `INACTIVE` never transfers, never changes his eleven or captain: screened out from tenure 4.

So the panel is `PANEL` in every scored gameweek, and its bands are top, middle and bottom. The
manager ids are large and distinctive, so a whole-token scan cannot match an ordinary number.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pyarrow as pa
import pyarrow.parquet as pq

from warehouse import served

SEASON: Final = "2026-27"
BUILT_AT: Final = "2026-11-01T08:05:01+00:00"
GIT_SHA: Final = "0123456789abcdef0123456789abcdef01234567"
UNCAPTURED_GWS: Final = (1, 2)
SURPRISE_GW: Final = 8
SURPRISE_POINTS: Final = 30
RANKED_COUNT: Final = 300

# player_id -> (position_id, points every gameweek)
PLAYERS: Final[Mapping[int, tuple[int, int]]] = {
    1: (1, 6),
    2: (1, 1),
    3: (2, 9),
    4: (2, 8),
    5: (2, 7),
    6: (2, 5),
    7: (2, 2),
    8: (3, 10),
    9: (3, 9),
    10: (3, 8),
    11: (3, 4),
    12: (3, 1),
    13: (4, 9),
    14: (4, 7),
    15: (4, 3),
}
SURPRISE_PLAYERS: Final = frozenset({7, 12, 15})
D2_ELEVEN: Final = frozenset({1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14})
BENCH: Final = sorted(set(PLAYERS) - D2_ELEVEN)  # [2, 7, 12, 15]

TIED: Final = 900_001
BEATEN: Final = 900_002
BEATEN_MORE: Final = 900_003
SELF: Final = 900_004
INACTIVE: Final = 900_005
MANAGERS: Final = (TIED, BEATEN, BEATEN_MORE, SELF, INACTIVE)
PANEL: Final = (TIED, BEATEN, BEATEN_MORE)

# entry_id -> (eleven, cohort, overall_rank every gameweek, transfers every gameweek)
_ELEVENS: Final[Mapping[int, frozenset[int]]] = {
    TIED: D2_ELEVEN,
    BEATEN: (D2_ELEVEN - {6}) | {7},
    BEATEN_MORE: (D2_ELEVEN - {6, 11, 14}) | {7, 12, 15},
    SELF: D2_ELEVEN,
    INACTIVE: (D2_ELEVEN - {6}) | {7},
}
_MANAGER_ROWS: Final[Mapping[int, tuple[str, int, int]]] = {
    TIED: ("random", 10, 1),
    BEATEN: ("random", 150, 1),
    BEATEN_MORE: ("random", 290, 1),
    SELF: ("self", 20, 1),
    INACTIVE: ("random", 160, 0),
}


def points(player_id: int, gw: int) -> int:
    """A player's points in a gameweek of this publish."""
    if gw == SURPRISE_GW and player_id in SURPRISE_PLAYERS:
        return SURPRISE_POINTS
    return PLAYERS[player_id][1]


def eleven_points(entry_id: int, gw: int) -> int:
    return sum(points(p, gw) for p in _ELEVENS[entry_id])


def d2_points(gw: int) -> int:
    """D2's points in a gameweek up to `SURPRISE_GW`: its eleven is `D2_ELEVEN` until the surprise
    moves the season rates, after which it is not hand-computed here."""
    assert gw <= SURPRISE_GW
    return sum(points(p, gw) for p in D2_ELEVEN)


def _int32(*names: str) -> list[tuple[str, pa.DataType]]:
    return [(name, pa.int32()) for name in names]


def _table(rows: list[dict[str, object]], schema: pa.Schema, path: Path) -> None:
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


def write(
    root: Path,
    last_gw: int,
    *,
    run_id: str = "synthetic-73",
    built_at: str | None = BUILT_AT,
    git_sha: str | None = GIT_SHA,
) -> served.Pin:
    """Write the publish for GW1-`last_gw` into `root/run_id` and return its pin.

    `built_at` or `git_sha` None leaves that field out of the manifest.
    """
    target = root / run_id
    target.mkdir(parents=True)
    gws = range(1, last_gw + 1)

    _table(
        [
            {
                "season": SEASON,
                "fpl_id": p,
                "gameweek": g,
                "fixture_id": g * 100 + p,
                "team_fpl_id": p,
                "minutes": 90,
                "starts": 1,
                "total_points": points(p, g),
            }
            for g in gws
            for p in PLAYERS
        ],
        pa.schema(
            [
                ("season", pa.string()),
                *_int32("fpl_id", "gameweek", "fixture_id", "team_fpl_id", "minutes", "starts", "total_points"),
            ]
        ),
        target / "fct_player_fixture.parquet",
    )
    _table(
        [
            {
                "season": SEASON,
                "fpl_id": p,
                "gameweek": g,
                "fixture_count": 1,
                "total_points": points(p, g),
                "minutes": 90,
                "starts": 1,
                "value": 45,
                "selected": 1000,
                "fixture_count_at_deadline": None if g in UNCAPTURED_GWS else 1,
            }
            for g in gws
            for p in PLAYERS
        ],
        pa.schema(
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
        ),
        target / "fct_player_gameweek.parquet",
    )
    _table(
        [{"season": SEASON, "fpl_id": p, "position_id": position} for p, (position, _) in PLAYERS.items()],
        pa.schema([("season", pa.string()), *_int32("fpl_id", "position_id")]),
        target / "dim_player.parquet",
    )

    pick_rows: list[dict[str, object]] = []
    for entry_id in MANAGERS:
        eleven = sorted(_ELEVENS[entry_id])
        lineup = [*eleven, *sorted(set(PLAYERS) - set(eleven))]
        for g in gws:
            for slot, p in enumerate(lineup, start=1):
                pick_rows.append(
                    {
                        "season": SEASON,
                        "entry_id": entry_id,
                        "gameweek": g,
                        "slot": slot,
                        "fpl_id": p,
                        "is_auto_sub_in": False,
                        "is_auto_sub_out": False,
                        "is_captain": slot == 1,
                    }
                )
    _table(
        pick_rows,
        pa.schema(
            [
                ("season", pa.string()),
                *_int32("entry_id", "gameweek", "slot", "fpl_id"),
                ("is_auto_sub_in", pa.bool_()),
                ("is_auto_sub_out", pa.bool_()),
                ("is_captain", pa.bool_()),
            ]
        ),
        target / "fct_manager_pick.parquet",
    )
    _table(
        [
            {
                "season": SEASON,
                "entry_id": entry_id,
                "gameweek": g,
                "active_chip": None,
                "cohort": cohort,
                "event_transfers": transfers,
                "overall_rank": rank,
            }
            for entry_id, (cohort, rank, transfers) in _MANAGER_ROWS.items()
            for g in gws
        ],
        pa.schema(
            [
                ("season", pa.string()),
                *_int32("entry_id", "gameweek"),
                ("active_chip", pa.string()),
                ("cohort", pa.string()),
                *_int32("event_transfers", "overall_rank"),
            ]
        ),
        target / "fct_manager_gameweek.parquet",
    )
    _table(
        [{"season": SEASON, "gameweek": g, "ranked_count": RANKED_COUNT} for g in gws],
        pa.schema([("season", pa.string()), *_int32("gameweek", "ranked_count")]),
        target / "dim_gameweek.parquet",
    )

    manifest: dict[str, object] = {"run_id": run_id, "contract_version": served.CONTRACT_VERSION, "seasons": [SEASON]}
    if built_at is not None:
        manifest["built_at"] = built_at
    if git_sha is not None:
        manifest["git_sha"] = git_sha
    (target / served.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return served.pin_of(target)
