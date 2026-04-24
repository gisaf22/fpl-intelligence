"""
Data Access Layer — player and fixture queries.

BOUNDARY RULE: This is the only file in the analysis layer permitted to contain SQL
or open database connections. No notebook or analysis script may call sqlite3 directly.

All functions accept a db_path and return a pandas DataFrame.
Each function opens and closes its own connection.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from analysis.source.fixtures import fetch_fixtures_raw
from analysis.source.player_histories import fetch_player_histories_raw
from analysis.source.players import fetch_players_raw


def get_players(db_path: Path) -> pd.DataFrame:
    """
    Returns all rows from the players table.

    Columns: id, web_name, element_type, team
    """
    return fetch_players_raw(db_path)


def get_fixtures(db_path: Path, gw: int | None = None) -> pd.DataFrame:
    """
    Returns rows from the fixtures table.

    Columns: id, event, team_h, team_a
    If gw is provided, filters to fixtures.event = gw.
    """
    with sqlite3.connect(db_path) as conn:
        if gw is not None:
            return pd.read_sql_query(
                "SELECT id, event, team_h, team_a FROM fixtures WHERE event = :gw",
                conn,
                params={"gw": gw},
            )
        return pd.read_sql_query(
            "SELECT id, event, team_h, team_a FROM fixtures",
            conn,
        )


def get_all_player_histories(db_path: Path) -> pd.DataFrame:
    """
    Returns all rows from the player_histories table.

    No GW filter. Use for structural and schema-level inspection only.
    Column list mirrors the full schema; no aggregation is applied.
    """
    return fetch_player_histories_raw(db_path)


def get_fixtures_full(db_path: Path, gw: int | None = None) -> pd.DataFrame:
    """
    Returns all 17 columns from the fixtures table.

    Use for structural/schema audits only (e.g. 00_overview).
    Pipeline notebooks must use get_fixtures(), which returns only the
    pipeline-contracted columns (id, event, team_h, team_a).
    """
    fixtures = fetch_fixtures_raw(db_path)
    if gw is not None:
        return fixtures.loc[fixtures["event"] == gw].reset_index(drop=True)
    return fixtures
