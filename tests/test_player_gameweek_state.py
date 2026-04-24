from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from analysis.curated.player_gameweek_spine import build_player_gameweek_spine
from analysis.state.player_gameweek_state import build_player_gameweek_state


def _seed_player_gameweek_spine_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))

    conn.execute(
        """
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            web_name TEXT NOT NULL,
            element_type INTEGER NOT NULL,
            team INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE fixtures (
            id INTEGER PRIMARY KEY,
            event INTEGER NOT NULL,
            team_h INTEGER NOT NULL,
            team_a INTEGER NOT NULL,
            kickoff_time TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE player_histories (
            element_id INTEGER NOT NULL,
            round INTEGER NOT NULL,
            fixture INTEGER NOT NULL,
            minutes INTEGER NOT NULL,
            goals_scored INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            clean_sheets INTEGER NOT NULL DEFAULT 0,
            goals_conceded INTEGER NOT NULL DEFAULT 0,
            own_goals INTEGER NOT NULL DEFAULT 0,
            penalties_saved INTEGER NOT NULL DEFAULT 0,
            penalties_missed INTEGER NOT NULL DEFAULT 0,
            yellow_cards INTEGER NOT NULL DEFAULT 0,
            red_cards INTEGER NOT NULL DEFAULT 0,
            saves INTEGER NOT NULL DEFAULT 0,
            bonus INTEGER NOT NULL DEFAULT 0,
            bps INTEGER NOT NULL DEFAULT 0,
            total_points REAL NOT NULL DEFAULT 0,
            influence REAL NOT NULL DEFAULT 0,
            creativity REAL NOT NULL DEFAULT 0,
            threat REAL NOT NULL DEFAULT 0,
            ict_index REAL NOT NULL DEFAULT 0,
            expected_goals REAL NOT NULL DEFAULT 0,
            expected_assists REAL NOT NULL DEFAULT 0,
            expected_goal_involvements REAL NOT NULL DEFAULT 0,
            expected_goals_conceded REAL NOT NULL DEFAULT 0,
            starts INTEGER NOT NULL DEFAULT 0,
            in_dreamteam INTEGER NOT NULL DEFAULT 0,
            tackles INTEGER NOT NULL DEFAULT 0,
            clearances_blocks_interceptions INTEGER NOT NULL DEFAULT 0,
            recoveries INTEGER NOT NULL DEFAULT 0,
            defensive_contribution INTEGER NOT NULL DEFAULT 0,
            opponent_team INTEGER NOT NULL DEFAULT 0,
            was_home INTEGER NOT NULL DEFAULT 1,
            kickoff_time TEXT,
            team_h_score INTEGER,
            team_a_score INTEGER,
            value INTEGER NOT NULL DEFAULT 0,
            selected INTEGER,
            transfers_in INTEGER NOT NULL DEFAULT 0,
            transfers_out INTEGER NOT NULL DEFAULT 0,
            transfers_balance INTEGER NOT NULL DEFAULT 0,
            ingested_at TEXT NOT NULL
        )
        """
    )

    conn.executemany(
        "INSERT INTO players VALUES (?, ?, ?, ?)",
        [
            (1, "Alpha", 3, 10),
            (2, "Bravo", 2, 20),
            (3, "Charlie", 4, 30),
        ],
    )
    conn.executemany(
        "INSERT INTO fixtures VALUES (?, ?, ?, ?, ?)",
        [
            (100, 1, 10, 20, "2026-04-01T18:00:00Z"),
            (101, 2, 10, 30, "2026-04-08T12:00:00Z"),
            (102, 2, 40, 10, "2026-04-08T17:30:00Z"),
            (103, 2, 20, 50, None),
        ],
    )
    conn.executemany(
        """
        INSERT INTO player_histories (
            element_id, round, fixture, minutes, starts, total_points, opponent_team, was_home, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, 100, 90, 1, 6.0, 20, 1, "2026-04-20T00:00:00+00:00"),
            (1, 2, 102, 45, 0, 2.0, 40, 0, "2026-04-21T00:00:00+00:00"),
            (1, 2, 101, 90, 1, 8.0, 30, 1, "2026-04-21T00:00:00+00:00"),
            (2, 2, 103, 60, 1, 5.0, 50, 1, "2026-04-21T00:00:00+00:00"),
        ],
    )

    conn.commit()
    conn.close()


def test_build_player_gameweek_state_derives_allowed_state_only(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek_spine.db"
    _seed_player_gameweek_spine_db(db_path)
    spine = build_player_gameweek_spine(db_path)

    state = build_player_gameweek_state(spine)

    assert state.columns.tolist() == [
        "player_id",
        "gameweek",
        "fixture_count",
        "fixture_context",
        "home_away_profile",
        "minutes",
        "starts",
    ]
    assert len(state) == len(spine)

    gw1 = state[(state["player_id"] == 1) & (state["gameweek"] == 1)].iloc[0]
    assert gw1["fixture_count"] == 1
    assert gw1["fixture_context"] == "SGW"
    assert gw1["home_away_profile"] == "HOME"
    assert gw1["minutes"] == 90
    assert gw1["starts"] == 1

    gw2 = state[(state["player_id"] == 1) & (state["gameweek"] == 2)].iloc[0]
    assert gw2["fixture_count"] == 2
    assert gw2["fixture_context"] == "DGW"
    assert gw2["home_away_profile"] == "MIXED"
    assert gw2["minutes"] == 135
    assert gw2["starts"] == 1


def test_build_player_gameweek_state_does_not_modify_input_dataframe(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek_spine.db"
    _seed_player_gameweek_spine_db(db_path)
    spine = build_player_gameweek_spine(db_path)
    original = spine.copy(deep=True)

    _ = build_player_gameweek_state(spine)

    assert_frame_equal(spine, original, check_dtype=True, check_like=False)


def test_build_player_gameweek_state_rejects_non_list_was_home_flags() -> None:
    spine = pd.DataFrame(
        {
            "player_id": [1],
            "gameweek": [1],
            "player_name": ["Alpha"],
            "element_type": [3],
            "team_id": [10],
            "minutes": [90],
            "starts": [1],
            "total_points": [6.0],
            "fixture_ids": [[100]],
            "opponent_team_ids": [[20]],
            "was_home_flags": ["not-a-list"],
            "latest_ingested_at": ["2026-04-20T00:00:00+00:00"],
        }
    )

    with pytest.raises(TypeError, match="was_home_flags to be list-valued"):
        build_player_gameweek_state(spine)
