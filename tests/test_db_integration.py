"""
DB integration tests using sqlite3 in-memory databases.

No mocking. All inserts are deterministic.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from fpl_intelligence.db import player_repo


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _create_player_histories(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE player_histories (
            element_id  INTEGER NOT NULL,
            round       INTEGER NOT NULL,
            ingested_at TEXT    NOT NULL,
            total_points REAL   NOT NULL DEFAULT 0,
            starts      INTEGER NOT NULL DEFAULT 0,
            selected    INTEGER,
            fixture     INTEGER NOT NULL,
            was_home    INTEGER NOT NULL DEFAULT 1
        )
        """
    )


def _create_players(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE players (
            id           INTEGER PRIMARY KEY,
            web_name     TEXT    NOT NULL,
            element_type INTEGER NOT NULL,
            team         INTEGER NOT NULL
        )
        """
    )


def _create_fixtures(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE fixtures (
            id     INTEGER PRIMARY KEY,
            event  INTEGER NOT NULL,
            team_h INTEGER NOT NULL,
            team_a INTEGER NOT NULL
        )
        """
    )


def _recent_ts(hours_ago: float = 1.0) -> str:
    return (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + "+00:00"


# ---------------------------------------------------------------------------
# Test 1 — validate_data_freshness
# ---------------------------------------------------------------------------

class TestValidateDataFreshness:
    def test_passes_when_rows_exist_and_recent(self) -> None:
        conn = sqlite3.connect(":memory:")
        _create_player_histories(conn)
        conn.execute(
            "INSERT INTO player_histories VALUES (1, 1, ?, 5.0, 1, 1000, 1, 1)",
            (_recent_ts(hours_ago=1),),
        )
        conn.commit()

        # Must not raise.
        player_repo.validate_data_freshness(conn, gw=1)

    def test_raises_when_no_rows_for_gw(self) -> None:
        conn = sqlite3.connect(":memory:")
        _create_player_histories(conn)
        # No rows inserted.

        with pytest.raises(ValueError, match="No data in player_histories for GW 1"):
            player_repo.validate_data_freshness(conn, gw=1)

    def test_raises_when_data_too_old(self) -> None:
        conn = sqlite3.connect(":memory:")
        _create_player_histories(conn)
        # Insert a row that is 12 hours old.
        conn.execute(
            "INSERT INTO player_histories VALUES (1, 1, ?, 5.0, 1, 1000, 1, 1)",
            (_recent_ts(hours_ago=12),),
        )
        conn.commit()

        with pytest.raises(ValueError, match="12.0h old"):
            player_repo.validate_data_freshness(conn, gw=1, max_age_hours=6)


# ---------------------------------------------------------------------------
# Test 2 — fetch_player_metrics
# ---------------------------------------------------------------------------

class TestFetchPlayerMetrics:
    def _seed(self, tmp_path) -> str:
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))

        _create_players(conn)
        _create_fixtures(conn)
        _create_player_histories(conn)

        # Two teams, one fixture for GW 6.
        conn.execute("INSERT INTO fixtures VALUES (1, 6, 10, 20)")

        # Two players: GK on team 10 (home), DEF on team 10 (home).
        conn.execute("INSERT INTO players VALUES (1, 'GKPlayer', 1, 10)")
        conn.execute("INSERT INTO players VALUES (2, 'DEFPlayer', 2, 10)")

        # Six rounds of history (rounds 1-6) for each player.
        # Player 1 scores 10 pts/round, player 2 scores 5 pts/round.
        # Both start every round. Selected only set for round 6 (current GW).
        for pid, pts in [(1, 10.0), (2, 5.0)]:
            for rnd in range(1, 7):
                selected = 1000 if rnd == 6 else None
                conn.execute(
                    "INSERT INTO player_histories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, rnd, "2020-01-01T00:00:00+00:00", pts, 1, selected, 1, 1),
                )

        conn.commit()
        conn.close()
        return db_file

    def test_correct_points_aggregation(self, tmp_path) -> None:
        db_file = self._seed(tmp_path)
        rows = player_repo.fetch_player_metrics(db_file, gw=6, lookback=6)

        assert len(rows) == 2

        by_id = {r[0]: r for r in rows}

        # Player 1: 10 pts × 6 rounds = 60 pts, 6 starts.
        assert by_id[1][4] == 60.0
        assert by_id[1][5] == 6.0

        # Player 2: 5 pts × 6 rounds = 30 pts, 6 starts.
        assert by_id[2][4] == 30.0
        assert by_id[2][5] == 6.0

    def test_team_id_resolution_home(self, tmp_path) -> None:
        db_file = self._seed(tmp_path)
        rows = player_repo.fetch_player_metrics(db_file, gw=6, lookback=6)

        by_id = {r[0]: r for r in rows}
        # was_home=1 → team_id = team_h = 10 for both players.
        assert by_id[1][2] == 10
        assert by_id[2][2] == 10

    def test_player_without_current_gw_row_excluded(self, tmp_path) -> None:
        """Player with no round=6 history row (selected IS NULL) is filtered out."""
        db_file = self._seed(tmp_path)

        # Add a third player with history only for rounds 1-5 (no round-6 row).
        conn = sqlite3.connect(str(db_file))
        conn.execute("INSERT INTO players VALUES (3, 'NoGWPlayer', 3, 10)")
        for rnd in range(1, 6):
            conn.execute(
                "INSERT INTO player_histories VALUES (3, ?, ?, 8.0, 1, NULL, 1, 1)",
                (rnd, "2020-01-01T00:00:00+00:00"),
            )
        conn.commit()
        conn.close()

        rows = player_repo.fetch_player_metrics(db_file, gw=6, lookback=6)
        ids = {r[0] for r in rows}
        assert 3 not in ids

    def test_rows_sorted_by_player_id(self, tmp_path) -> None:
        db_file = self._seed(tmp_path)
        rows = player_repo.fetch_player_metrics(db_file, gw=6, lookback=6)
        ids = [r[0] for r in rows]
        assert ids == sorted(ids)
