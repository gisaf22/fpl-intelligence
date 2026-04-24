import sqlite3
import json
import tempfile
from pathlib import Path
import shutil
import pytest

from fpl_intelligence.pipeline.runner import run_gw


# ----------------------------
# DB builder
# ----------------------------
def make_db(players, histories, db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            web_name TEXT,
            team INTEGER,
            element_type INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE player_histories (
            element_id  INTEGER,
            round       INTEGER,
            total_points REAL,
            starts      REAL,
            selected    REAL,
            fixture     INTEGER,
            was_home    INTEGER,
            ingested_at TEXT NOT NULL DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE fixtures (
            id INTEGER PRIMARY KEY,
            team_h INTEGER,
            team_a INTEGER,
            event INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            deadline_time TEXT,
            is_current INTEGER
        )
    """)

    cur.executemany("INSERT INTO players VALUES (?, ?, ?, ?)", players)
    cur.executemany("INSERT INTO player_histories VALUES (?, ?, ?, ?, ?, ?, ?, '')", histories)

    # Pad to 60 players so validate_pipeline_output's eligibility check passes (>= 50).
    # Layout: 15 GK pts 1-15, 15 DEF pts 1-15, 13 MID pts 1-8 (below test player pts
    # so test players remain above the MID median), 15 FWD pts 1-15.
    # All padding players are on team=1 (home), starts=6 (eligible), selected=500.
    existing_ids = {p[0] for p in players}
    pad_id = max(existing_ids) + 100
    gw = histories[0][1]  # all test histories use the same GW

    schedule = (
        [(1, pts) for pts in range(1, 16)]   # 15 GK
        + [(2, pts) for pts in range(1, 16)] # 15 DEF
        + [(3, (i % 8) + 1) for i in range(13)]  # 13 MID, pts cycling 1-8
        + [(4, pts) for pts in range(1, 16)] # 15 FWD
    )
    for etype, pts in schedule:
        cur.execute("INSERT INTO players VALUES (?, ?, ?, ?)", (pad_id, f"Pad{pad_id}", 1, etype))
        cur.execute(
            "INSERT INTO player_histories VALUES (?, ?, ?, ?, ?, ?, ?, '')",
            (pad_id, gw, float(pts), 6.0, 500, 1, 1),
        )
        pad_id += 1

    # Set ingested_at to 1 hour ago so the freshness check passes.
    cur.execute(
        "UPDATE player_histories SET ingested_at = strftime('%Y-%m-%dT%H:%M:%S+00:00', datetime('now', '-1 hour'))"
    )
    cur.execute("INSERT INTO fixtures VALUES (1, 1, 2, 1)")
    cur.execute("INSERT INTO events VALUES (1, '2000-01-01T00:00:00Z', 1)")

    cur.execute("""
        CREATE TABLE _metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute(
        "INSERT INTO _metadata VALUES ('current_gameweek', ?)", (str(gw),)
    )

    conn.commit()
    conn.close()


# ----------------------------
# IO helpers
# ----------------------------
def read_briefing(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_signal_items(briefing):
    ovr = briefing["signals"]["ownership_vs_returns"]
    return ovr.get("undervalued", []) + ovr.get("overvalued", [])


def get_top_k(items, k=3):
    return [item["entity_id"] for item in items[:k]]


# ----------------------------
# fixture
# ----------------------------
@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


def run_and_get_briefing(gw, db_path, tmpdir):
    out_dir = tmpdir / "briefs"
    log_dir = tmpdir / "logs"

    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    run_gw(gw, db_path, out_dir, log_dir / "run.log")

    return read_briefing(out_dir / f"gw_{gw}_briefing.json")


# =========================================================
# TEST 1 — Input perturbation changes signal output
# =========================================================
def test_input_perturbation_changes_signal(tmpdir):
    players = [
        (1, "A", 1, 3),
        (2, "B", 1, 3),
    ]

    base_histories = [
        (1, 1, 10, 6, 100, 1, 1),
        (2, 1, 10, 6, 100, 1, 1),
    ]

    perturbed_histories = [
        (1, 1, 30, 6, 100, 1, 1),  # stronger performance
        (2, 1, 10, 6, 100, 1, 1),
    ]

    db_a = tmpdir / "a.db"
    db_b = tmpdir / "b.db"

    make_db(players, base_histories, db_a)
    make_db(players, perturbed_histories, db_b)

    briefing_a = run_and_get_briefing(1, db_a, tmpdir)
    briefing_b = run_and_get_briefing(1, db_b, tmpdir)

    items_a = get_signal_items(briefing_a)
    items_b = get_signal_items(briefing_b)

    # signal must respond
    assert items_a != items_b, (
        f"Signal should change when inputs change.\nA: {items_a}\nB: {items_b}"
    )

    # magnitude should change somewhere in system
    diff_a = sum(abs(i["value"]) for i in items_a)
    diff_b = sum(abs(i["value"]) for i in items_b)

    assert diff_a != diff_b, "Total signal magnitude should change under perturbation"


# =========================================================
# TEST 2 — Determinism
# =========================================================
def test_deterministic_runs(tmpdir):
    players = [
        (1, "A", 1, 3),
        (2, "B", 1, 3),
    ]

    histories = [
        (1, 1, 10, 6, 100, 1, 1),
        (2, 1, 20, 6, 100, 1, 1),
    ]

    db = tmpdir / "c.db"
    make_db(players, histories, db)

    b1 = run_and_get_briefing(1, db, tmpdir)
    b2 = run_and_get_briefing(1, db, tmpdir)

    items1 = get_signal_items(b1)
    items2 = get_signal_items(b2)

    assert items1 == items2, "Identical inputs must produce identical outputs"


# =========================================================
# TEST 3 — Signal responsiveness (no monotonicity assumption)
# =========================================================
def test_signal_responsiveness(tmpdir):
    players = [
        (1, "X", 1, 3),
        (2, "Y", 1, 3),
    ]

    base = [
        (1, 1, 10, 6, 100, 1, 1),
        (2, 1, 30, 6, 100, 1, 1),
    ]

    boosted = [
        (1, 1, 50, 6, 100, 1, 1),  # X improves strongly
        (2, 1, 30, 6, 100, 1, 1),
    ]

    db_base = tmpdir / "base.db"
    db_boost = tmpdir / "boost.db"

    make_db(players, base, db_base)
    make_db(players, boosted, db_boost)

    briefing_base = run_and_get_briefing(1, db_base, tmpdir)
    briefing_boost = run_and_get_briefing(1, db_boost, tmpdir)

    items_base = get_signal_items(briefing_base)
    items_boost = get_signal_items(briefing_boost)

    x_base = next(i for i in items_base if i["entity_id"] == 1)
    x_boost = next(i for i in items_boost if i["entity_id"] == 1)

    assert x_base["value"] != x_boost["value"], (
        f"Signal must respond to input change\nBase: {x_base}\nBoost: {x_boost}"
    )