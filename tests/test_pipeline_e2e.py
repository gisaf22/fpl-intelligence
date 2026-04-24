"""
End-to-end pipeline test: run_gw() against a fully-seeded in-file SQLite DB.

Constraints:
- sqlite3.connect(":memory:") cannot be used here because run_gw() and its
  sub-steps each open their own connections by db_path. All connections use
  the same file via tmp_path.
- 60 players (15 per position) with varied total_points ensure:
    Check 1: 60 eligible players >= 50 threshold
    Check 2: score range >= 0.5 (varied returns_z across positions)
    Check 3: no DGW players — check skipped
    Check 4: all 4 positions represented in top 15 (one top scorer per position)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fpl_intelligence.pipeline.runner import run_gw


# ---------------------------------------------------------------------------
# DB seed
# ---------------------------------------------------------------------------

GW = 6
LOOKBACK = 6
TEAM_H = 1
TEAM_A = 2
FIXTURE_ID = 1

# element_type → position label
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# 15 players per position, 60 total.
# Points rotate through each position so the top scorer in every position
# group is the player with the highest total_points in that group, ensuring
# all 4 positions appear in the top-15 ranked signal items.
#
# Player index i (0-59):
#   element_type = (i % 4) + 1   → GK/DEF/MID/FWD cycling
#   pts_per_round = (i // 4) + 1 → 1..15 within each position group
N_PLAYERS = 60


def _recent_ts() -> str:
    return (datetime.utcnow() - timedelta(hours=1)).isoformat() + "+00:00"


def _seed_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))

    conn.execute(
        """
        CREATE TABLE events (
            id         INTEGER PRIMARY KEY,
            is_current INTEGER NOT NULL DEFAULT 0
        )
        """
    )
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
    conn.execute(
        """
        CREATE TABLE player_histories (
            element_id   INTEGER NOT NULL,
            round        INTEGER NOT NULL,
            ingested_at  TEXT    NOT NULL,
            total_points REAL    NOT NULL DEFAULT 0,
            starts       INTEGER NOT NULL DEFAULT 0,
            selected     INTEGER,
            fixture      INTEGER NOT NULL,
            was_home     INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE _metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO _metadata VALUES ('current_gameweek', ?)", (str(GW),)
    )

    # Current GW event.
    conn.execute("INSERT INTO events VALUES (?, 1)", (GW,))

    # Single fixture for GW (all players are home team).
    conn.execute("INSERT INTO fixtures VALUES (?, ?, ?, ?)", (FIXTURE_ID, GW, TEAM_H, TEAM_A))

    recent = _recent_ts()
    old_ts = "2020-01-01T00:00:00+00:00"

    for i in range(N_PLAYERS):
        pid = i + 1
        etype = (i % 4) + 1
        pts_per_round = float((i // 4) + 1)

        conn.execute(
            "INSERT INTO players VALUES (?, ?, ?, ?)",
            (pid, f"Player{pid}", etype, TEAM_H),
        )

        # Six rounds of history (rounds 1-6). Round GW gets selected and
        # a recent ingested_at for the freshness check.
        for rnd in range(1, LOOKBACK + 1):
            is_current = rnd == GW
            conn.execute(
                "INSERT INTO player_histories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    rnd,
                    recent if is_current else old_ts,
                    pts_per_round,
                    1,             # starts = 1 per round → starts_last_n = 6 → eligible
                    1000,          # selected (non-NULL for all rows; HAVING checks round=GW)
                    FIXTURE_ID,
                    1,             # was_home = 1 → team_id = team_h = TEAM_H
                ),
            )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_gw_completes(tmp_path: Path) -> None:
    db_path = tmp_path / "fpl.db"
    output_dir = tmp_path / "output"
    log_path = tmp_path / "run.log"

    _seed_db(db_path)

    result = run_gw(GW, db_path, output_dir, log_path)

    assert result.status == "complete"
    assert result.gw == GW
    assert len(result.failures) == 0


def test_run_gw_produces_briefing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "fpl.db"
    output_dir = tmp_path / "output"

    _seed_db(db_path)
    run_gw(GW, db_path, output_dir, tmp_path / "run.log")

    briefing_file = output_dir / f"gw_{GW}_briefing.json"
    assert briefing_file.exists()
    assert briefing_file.stat().st_size > 0


def test_run_gw_rankings_non_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "fpl.db"
    output_dir = tmp_path / "output"

    _seed_db(db_path)
    run_gw(GW, db_path, output_dir, tmp_path / "run.log")

    import json
    briefing = json.loads((output_dir / f"gw_{GW}_briefing.json").read_text())

    ovr = briefing["signals"]["ownership_vs_returns"]
    assert len(ovr["undervalued"]) > 0
    assert len(ovr["overvalued"]) > 0


def test_run_gw_is_deterministic(tmp_path: Path) -> None:
    """Same DB inputs must produce identical briefing JSON on two runs."""
    db_path = tmp_path / "fpl.db"
    output_dir_a = tmp_path / "output_a"
    output_dir_b = tmp_path / "output_b"

    _seed_db(db_path)

    run_gw(GW, db_path, output_dir_a, tmp_path / "run_a.log")
    run_gw(GW, db_path, output_dir_b, tmp_path / "run_b.log")

    import json
    briefing_a = json.loads((output_dir_a / f"gw_{GW}_briefing.json").read_text())
    briefing_b = json.loads((output_dir_b / f"gw_{GW}_briefing.json").read_text())

    # generated_at will differ between runs — exclude from comparison.
    for b in (briefing_a, briefing_b):
        del b["meta"]["generated_at"]

    assert briefing_a == briefing_b
