"""DB entry point for weekly runs — GW resolution, freshness validation,
and staged-table selectors for pipeline consumers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.exceptions import DataFreshnessError
from dal.staging import (
    get_staged_events,
    get_staged_fixtures,
    get_staged_player_histories,
    get_staged_players,
)

_PIPELINE_REQUIRED_COLS = [
    "player_id",
    "player_name",
    "team_id",
    "position_code",
    "purchase_price",
    "total_points",
    "minutes",
    "status",
    "selected_by_percent",
    "transfers_in_event",
    "transfers_out_event",
]


def resolve_target_gw(db_path: Path) -> int:
    """Resolve the target GW from the events table.

    Resolution order:
    1. Row where is_live == True → return its gw
    2. Row where is_next == True → return its gw
    3. Minimum gw where finished == False → return it
    4. Raise ValueError if none of the above apply.
    """
    df = get_staged_events(db_path)

    current = df[df["is_live"] == 1]
    if not current.empty:
        return int(current.iloc[0]["gw"])

    nxt = df[df["is_next"] == 1]
    if not nxt.empty:
        return int(nxt.iloc[0]["gw"])

    unfinished = df[df["finished"] == 0]
    if not unfinished.empty:
        return int(unfinished["gw"].min())

    raise ValueError("Cannot resolve target GW — all events finished or no events found")


def validate_data_freshness(db_path: Path, gw: int) -> None:
    """Validate that the DB contains data for the target GW.

    Raises DataFreshnessError if:
    - GW not present in events table
    - gw > 1 and no player_histories rows exist for gw - 1
    """
    events = get_staged_events(db_path)

    if not (events["gw"] == gw).any():
        raise DataFreshnessError(f"GW {gw} not found in events")

    if gw > 1:
        hist = get_staged_player_histories(db_path)
        if not (hist["gw"] == gw - 1).any():
            raise DataFreshnessError(
                f"No player_histories rows found for GW {gw - 1} — DB may be stale"
            )


def get_players_for_pipeline(db_path: Path) -> pd.DataFrame:
    """Return staged players excluding unavailable (status == 'u') rows.

    Guaranteed non-nullable on exit: player_id, player_name, team_id, position_code,
    purchase_price, total_points, minutes, status, selected_by_percent,
    transfers_in_event, transfers_out_event.
    """
    df = get_staged_players(db_path)
    df = df[df["status"] != "u"].reset_index(drop=True)
    null_cols = [c for c in _PIPELINE_REQUIRED_COLS if df[c].isna().any()]
    if null_cols:
        raise ValueError(
            f"get_players_for_pipeline: null values found in required columns: {null_cols}"
        )
    return df


def get_fixtures_for_pipeline(db_path: Path, gw: int) -> pd.DataFrame:
    """Return staged fixtures filtered to the given gameweek.

    Raises ValueError if no fixtures exist for the requested GW.
    """
    df = get_staged_fixtures(db_path)
    result = df[df["gw"] == gw].reset_index(drop=True)
    if result.empty:
        raise ValueError(f"No fixtures found for GW {gw}")
    return result


def get_player_histories_for_pipeline(
    db_path: Path, gw_from: int, gw_to: int
) -> pd.DataFrame:
    """Return staged player_histories filtered to gw_from <= gw <= gw_to."""
    df = get_staged_player_histories(db_path)
    return df[(df["gw"] >= gw_from) & (df["gw"] <= gw_to)].reset_index(drop=True)
