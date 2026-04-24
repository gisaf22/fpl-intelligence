from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from analysis.contracts.schemas import player_gameweek_spine_schema
from analysis.contracts.validation import validate_player_gameweek_spine
from analysis.curated.player_gameweek_spine import build_player_gameweek_spine as build_new_player_gameweek_spine
from analysis.dal.player_repo import get_all_player_histories, get_fixtures_full, get_players


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


def _legacy_build_player_gameweek_spine(db_path: Path) -> pd.DataFrame:
    final_columns = [
        "player_id",
        "gameweek",
        "player_name",
        "element_type",
        "team_id",
        "minutes",
        "starts",
        "total_points",
        "fixture_ids",
        "opponent_team_ids",
        "was_home_flags",
        "latest_ingested_at",
    ]

    players = (
        get_players(db_path)
        .copy()[["id", "web_name", "element_type", "team"]]
        .rename(
            columns={
                "id": "player_id",
                "web_name": "player_name",
                "team": "team_id",
            }
        )
    )

    histories = (
        get_all_player_histories(db_path)
        .copy()[
            [
                "element_id",
                "round",
                "fixture",
                "minutes",
                "starts",
                "total_points",
                "opponent_team",
                "was_home",
                "ingested_at",
            ]
        ]
        .rename(
            columns={
                "element_id": "player_id",
                "round": "gameweek",
                "fixture": "fixture_id",
            }
        )
    )

    fixtures = get_fixtures_full(db_path).copy()
    fixture_columns = ["id"]
    if "kickoff_time" in fixtures.columns:
        fixture_columns.append("kickoff_time")
    fixtures = fixtures[fixture_columns].rename(columns={"id": "fixture_id"})

    spine_rows = histories.merge(
        players,
        on="player_id",
        how="left",
        validate="many_to_one",
    ).merge(
        fixtures,
        on="fixture_id",
        how="left",
        validate="many_to_one",
    )

    if "kickoff_time" in spine_rows.columns:
        kickoff_ts = pd.to_datetime(spine_rows["kickoff_time"], errors="coerce", utc=True)
        spine_rows = spine_rows.assign(
            _kickoff_missing=kickoff_ts.isna(),
            _kickoff_sort=kickoff_ts,
        )
    else:
        spine_rows = spine_rows.assign(
            _kickoff_missing=True,
            _kickoff_sort=pd.NaT,
        )

    spine_rows = spine_rows.sort_values(
        by=["player_id", "gameweek", "_kickoff_missing", "_kickoff_sort", "fixture_id"],
        kind="stable",
    ).reset_index(drop=True)

    return (
        spine_rows.groupby(["player_id", "gameweek"], as_index=False, sort=False)
        .agg(
            player_name=("player_name", "first"),
            element_type=("element_type", "first"),
            team_id=("team_id", "first"),
            minutes=("minutes", "sum"),
            starts=("starts", "sum"),
            total_points=("total_points", "sum"),
            fixture_ids=("fixture_id", list),
            opponent_team_ids=("opponent_team", list),
            was_home_flags=("was_home", list),
            latest_ingested_at=("ingested_at", "max"),
        )
        .loc[:, final_columns]
        .reset_index(drop=True)
    )


def test_build_player_gameweek_spine_refactor_preserves_exact_output(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek_spine.db"
    _seed_player_gameweek_spine_db(db_path)

    legacy = _legacy_build_player_gameweek_spine(db_path)
    refactored = build_new_player_gameweek_spine(db_path)

    assert_frame_equal(refactored, legacy, check_dtype=True, check_like=False)


def test_player_gameweek_spine_schema_definition_is_explicit() -> None:
    assert list(player_gameweek_spine_schema.keys()) == [
        "player_id",
        "gameweek",
        "player_name",
        "element_type",
        "team_id",
        "minutes",
        "starts",
        "total_points",
        "fixture_ids",
        "opponent_team_ids",
        "was_home_flags",
        "latest_ingested_at",
    ]
    assert player_gameweek_spine_schema["fixture_ids"].dtype == "list[int64]"
    assert player_gameweek_spine_schema["fixture_ids"].nullable is True
    assert player_gameweek_spine_schema["player_id"].nullable is False
    assert player_gameweek_spine_schema["gameweek"].nullable is False


def test_validate_player_gameweek_spine_rejects_misaligned_list_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek_spine.db"
    _seed_player_gameweek_spine_db(db_path)
    spine = build_new_player_gameweek_spine(db_path)
    spine.at[0, "was_home_flags"] = [1, 0]

    with pytest.raises(ValueError, match="list field length mismatch"):
        validate_player_gameweek_spine(spine)
