from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def fetch_players_raw(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT id, web_name, element_type, team FROM players",
            conn,
        )
