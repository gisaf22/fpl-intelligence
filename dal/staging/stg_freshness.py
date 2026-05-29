"""Staging-layer data freshness validation — pre-flight check before any pipeline run."""

from __future__ import annotations

from pathlib import Path

from dal.exceptions import DataFreshnessError
from dal.staging.stg_entities import get_staged_events, get_staged_player_histories


def validate_data_freshness(db_path: Path, gw: int) -> None:
    """Validate that the DB contains data for the target GW.

    Raises DataFreshnessError if:
    - GW not present in events table
    - gw > 1 and no player_histories rows exist for gw - 1
    """
    events = get_staged_events(db_path)
    if not (events["gw"] == gw).any():
        raise DataFreshnessError(f"GW {gw} not found in events", gw=gw)
    if gw > 1:
        hist = get_staged_player_histories(db_path)
        if not (hist["gw"] == gw - 1).any():
            raise DataFreshnessError(
                f"No player_histories rows found for GW {gw - 1} — DB may be stale",
                gw=gw - 1,
            )
