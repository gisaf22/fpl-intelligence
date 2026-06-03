"""Fixture-coverage meta-test — the curated test DB must contain every hard case.

ADLC §5: "The fixture DB is a first-class test artifact." `tests/fixtures/test.db`
(built by `create_test_db.py`) must be *curated* to hold the edge cases that the DAL
contract has to survive: BGW, DGW, mid-season transfer, warm-up sub, zero-minute,
red card, multi-position. This module makes that coverage itself a tested contract —
if a refactor of the fixture builder silently drops a scenario, a meta-test fails
loudly instead of the gap going unnoticed until a real bug slips through.

Assertions read the **built fixture DB** (the conftest `db_path` fixture → raw FPL
tables). They NEVER touch the live `~/.fpl/fpl.db` — that non-determinism was the
original CI bug ADLC §5 calls out. Each scenario is verified by its honest signature
in the raw inputs (e.g. BGW = a played-round gap), not by re-deriving DAL logic.

Scenario labels (SC-*) match the docstring of `tests/fixtures/create_test_db.py`.
"""

import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _connect(db_path: Path) -> sqlite3.Connection:
    assert db_path.exists(), (
        f"Fixture DB missing at {db_path}. Build it first: `uv run python tests/fixtures/create_test_db.py`"
    )
    return sqlite3.connect(db_path)


def test_fixture_has_bgw(db_path: Path) -> None:
    """BGW present: a player has a played-round gap (active before AND after a missing GW).

    A blank gameweek leaves no history row, so the signature is a round strictly between
    a player's first and last appearance that has no row (e.g. P1/P4 active GW1-2 and
    GW4-5 with no GW3 row — T1 has no GW3 fixture).
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT element_id, round FROM player_histories").fetchall()
    finally:
        conn.close()

    rounds_by_player: dict[int, set[int]] = {}
    for player_id, rnd in rows:
        rounds_by_player.setdefault(player_id, set()).add(rnd)

    players_with_gap = [
        player_id for player_id, rs in rounds_by_player.items() if set(range(min(rs), max(rs) + 1)) - rs
    ]
    assert players_with_gap, (
        "BGW scenario missing: no player has a played-round gap (a blank GW between two "
        "appearances). Expected at least P1/P4 with no GW3 row (SC-2)."
    )


def test_fixture_has_dgw(db_path: Path) -> None:
    """DGW present: a player has more than one history row in a single round (SC-3)."""
    conn = _connect(db_path)
    try:
        dgw = conn.execute(
            "SELECT element_id, round, COUNT(*) c FROM player_histories GROUP BY element_id, round HAVING c > 1"
        ).fetchall()
    finally:
        conn.close()
    assert dgw, (
        "DGW scenario missing: no (player, round) has >1 history row. Expected P2/P3 "
        "with two rows in GW4 (T2 double gameweek, SC-3)."
    )


def test_fixture_has_midseason_transfer(db_path: Path) -> None:
    """Mid-season transfer present: a player's derived team changes across rounds (SC-2).

    A player's team in a given round is the side they appeared for in that fixture
    (home team if was_home else away team). A transfer shows up as more than one
    distinct derived team across a player's history (e.g. P3: T1 in GW1-2, T2 in GW4-5).
    """
    conn = _connect(db_path)
    try:
        transferred = conn.execute(
            "SELECT ph.element_id, "
            "COUNT(DISTINCT CASE WHEN ph.was_home = 1 THEN f.team_h ELSE f.team_a END) nt "
            "FROM player_histories ph JOIN fixtures f ON ph.fixture = f.id "
            "GROUP BY ph.element_id HAVING nt > 1"
        ).fetchall()
    finally:
        conn.close()
    assert transferred, (
        "Mid-season transfer scenario missing: no player appears for more than one team "
        "across their history. Expected P3 (T1 → T2, SC-2)."
    )


def test_fixture_has_zero_minute(db_path: Path) -> None:
    """Zero-minute appearance present: a history row with minutes=0 and a fixture (SC-5).

    Distinct from a BGW (which has NO row): an unused sub gets a real row with a real 0.
    """
    conn = _connect(db_path)
    try:
        zero = conn.execute("SELECT element_id, round FROM player_histories WHERE minutes = 0").fetchall()
    finally:
        conn.close()
    assert zero, (
        "Zero-minute scenario missing: no history row has minutes=0. Expected P4 in GW1 "
        "(unused sub — a real 0, not a BGW NULL, SC-5)."
    )


def test_fixture_has_warmup_sub(db_path: Path) -> None:
    """Warm-up sub present: a history row with starts=0 AND minutes>0 (SC-6).

    The signature of a player who began on the bench and came on — distinct from a
    zero-minute unused sub (starts=0, minutes=0) and a starter (starts=1).
    """
    conn = _connect(db_path)
    try:
        subs = conn.execute(
            "SELECT element_id, round, minutes FROM player_histories WHERE starts = 0 AND minutes > 0"
        ).fetchall()
    finally:
        conn.close()
    assert subs, (
        "Warm-up sub scenario missing: no history row has starts=0 AND minutes>0. "
        "Expected P4 in GW2 (came off the bench, SC-6)."
    )


def test_fixture_has_red_card(db_path: Path) -> None:
    """Red card present: a history row with red_cards>0 (SC-7).

    Guards the red_cards column against staying at its DEFAULT 0 for every row.
    """
    conn = _connect(db_path)
    try:
        reds = conn.execute("SELECT element_id, round FROM player_histories WHERE red_cards > 0").fetchall()
    finally:
        conn.close()
    assert reds, "Red card scenario missing: no history row has red_cards>0. Expected P4 in GW4 (sent off, SC-7)."


def test_fixture_has_multiple_positions(db_path: Path) -> None:
    """Multi-position present: at least three distinct element_type values among players.

    The fixture spans GK + MID + DEF (P1/P2 GK, P3 MID, P4 DEF) so position-mapping logic
    is exercised across more than one position family.
    """
    conn = _connect(db_path)
    try:
        (n_positions,) = conn.execute("SELECT COUNT(DISTINCT element_type) FROM players").fetchone()
    finally:
        conn.close()
    assert n_positions >= 3, (
        f"Multi-position scenario too thin: only {n_positions} distinct element_type(s) "
        f"among players. Expected >= 3 (GK + MID + DEF)."
    )
