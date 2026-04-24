from __future__ import annotations

import sqlite3
from pathlib import Path

from analysis.player_gameweek_v1 import (
    build_player_gameweek_v1,
    define_initial_state_variables,
    get_curated_schema_spec,
    get_state_definitions,
    validate_source_tables,
)


def _seed_player_gameweek_db(db_path: Path) -> None:
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
            team_a INTEGER NOT NULL
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
        "INSERT INTO fixtures VALUES (?, ?, ?, ?)",
        [
            (100, 1, 10, 20),
            (101, 2, 10, 30),
            (102, 2, 40, 10),
            (103, 2, 20, 50),
        ],
    )

    rows = [
        (1, 1, 100, 90, 1, 6.0, 1000, 1, "2026-04-20T00:00:00+00:00"),
        (1, 2, 101, 90, 1, 8.0, 1100, 1, "2026-04-21T00:00:00+00:00"),
        (1, 2, 102, 45, 0, 2.0, 1100, 0, "2026-04-21T00:00:00+00:00"),
        (2, 2, 103, 60, 1, 5.0, 900, 1, "2026-04-21T00:00:00+00:00"),
    ]
    conn.executemany(
        """
        INSERT INTO player_histories (
            element_id, round, fixture, minutes, starts, total_points, selected, was_home, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    conn.commit()
    conn.close()


def test_build_player_gameweek_v1_enforces_player_gameweek_grain(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek.db"
    _seed_player_gameweek_db(db_path)

    curated = build_player_gameweek_v1(db_path)

    assert curated.columns.tolist() == get_curated_schema_spec()["columns"]
    assert not curated.duplicated(subset=["player_id", "gameweek"]).any()
    assert len(curated) == 3

    dgw_row = curated[(curated["player_id"] == 1) & (curated["gameweek"] == 2)].iloc[0]
    assert dgw_row["minutes"] == 135
    assert dgw_row["starts"] == 1
    assert dgw_row["total_points"] == 10.0
    assert dgw_row["selected_count"] == 1100
    assert dgw_row["fixture_count"] == 2
    assert dgw_row["home_fixture_count"] == 1
    assert dgw_row["away_fixture_count"] == 1


def test_validate_source_tables_reports_pass_for_valid_source_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek.db"
    _seed_player_gameweek_db(db_path)

    report = validate_source_tables(db_path)

    assert report["final_status"] == "PASS"
    assert report["schema_checks"]["players"]["status"] == "PASS"
    assert report["schema_checks"]["fixtures"]["status"] == "PASS"
    assert report["schema_checks"]["player_histories"]["status"] == "PASS"
    assert report["key_constraints"]["player_histories_primary_key"]["status"] == "PASS"
    assert report["coverage"]["source_row_coverage"]["status"] == "PASS"
    assert report["referential_integrity"]["player_histories_element_id_to_players_id"]["status"] == "PASS"
    assert report["referential_integrity"]["player_histories_fixture_to_fixtures_id"]["status"] == "PASS"


def test_define_initial_state_variables_returns_expected_flags_and_windows(tmp_path: Path) -> None:
    db_path = tmp_path / "player_gameweek.db"
    _seed_player_gameweek_db(db_path)

    curated = build_player_gameweek_v1(db_path)
    states = define_initial_state_variables(curated)

    gw1 = states[(states["player_id"] == 1) & (states["gameweek"] == 1)].iloc[0]
    assert gw1["recent_starts"] == 1
    assert gw1["minutes_trend"] == 0
    assert gw1["home_away_flag"] == "HOME"
    assert gw1["fixture_context"] == "SGW"

    gw2 = states[(states["player_id"] == 1) & (states["gameweek"] == 2)].iloc[0]
    assert gw2["recent_starts"] == 2
    assert gw2["minutes_trend"] == 45
    assert gw2["home_away_flag"] == "MIXED"
    assert gw2["fixture_context"] == "DGW"


def test_state_definitions_cover_required_initial_features() -> None:
    state_names = [item["feature_name"] for item in get_state_definitions()]
    assert state_names == [
        "recent_starts",
        "minutes_trend",
        "home_away_flag",
        "fixture_context",
    ]
