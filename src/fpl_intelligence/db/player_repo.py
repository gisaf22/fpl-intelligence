from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fpl_intelligence.exceptions import DataFreshnessError


def fetch_current_gw(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM _metadata WHERE key = 'current_gameweek'"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise DataFreshnessError("current_gameweek not found in _metadata")
    return int(row[0])


def validate_data_freshness(
    conn: sqlite3.Connection,
    gw: int,
    max_age_hours: int = 6,
) -> None:
    # column name is 'round' in this schema; spec says 'event' — using actual column
    cursor = conn.execute(
        "SELECT COUNT(*) FROM player_histories WHERE round = ?", (gw,)
    )
    count = cursor.fetchone()[0]
    if count == 0:
        raise ValueError(
            f"No data in player_histories for GW {gw}. Run ingest before pipeline."
        )

    # freshness column: ingested_at on player_histories
    cursor = conn.execute(
        "SELECT MAX(ingested_at) FROM player_histories WHERE round = ?", (gw,)
    )
    raw_value = cursor.fetchone()[0]
    parsed = datetime.fromisoformat(raw_value)
    # ingested_at contains timezone-aware ISO strings (+00:00 suffix confirmed);
    # strip tzinfo before subtracting against datetime.utcnow() (UTC-naive).
    last_update = parsed.replace(tzinfo=None)

    age = datetime.utcnow() - last_update
    if age > timedelta(hours=max_age_hours):
        raise ValueError(
            f"GW {gw} data is {age.total_seconds() / 3600:.1f}h old. "
            f"Maximum allowed age is {max_age_hours}h. Re-run ingest first."
        )


def fetch_player_metrics(
    db_path: Path,
    gw: int,
    lookback: int,
) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.id,
                p.web_name,
                MAX(CASE WHEN ph.round = :gw THEN
                    CASE WHEN ph.was_home = 1 THEN f.team_h ELSE f.team_a END
                END) AS team_id,
                p.element_type,
                COALESCE(SUM(
                    CASE WHEN ph.round > :gw - :lookback AND ph.round <= :gw
                         THEN ph.total_points ELSE 0 END
                ), 0),
                COALESCE(SUM(
                    CASE WHEN ph.round > :gw - :lookback AND ph.round <= :gw
                         THEN ph.starts ELSE 0 END
                ), 0),
                MAX(CASE WHEN ph.round = :gw THEN ph.selected END)
            FROM players p
            JOIN player_histories ph ON ph.element_id = p.id
            JOIN fixtures f ON f.id = ph.fixture
            GROUP BY p.id, p.web_name, p.element_type
            HAVING MAX(CASE WHEN ph.round = :gw THEN ph.selected END) IS NOT NULL
            """,
            {"gw": gw, "lookback": lookback},
        )
        return sorted(cur.fetchall(), key=lambda r: int(r[0]))
    except sqlite3.Error:
        return []
    finally:
        conn.close()
