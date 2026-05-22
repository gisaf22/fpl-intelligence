"""Canonical downstream access helpers — single entry points for spine and state.

Downstream modules must use these functions (or build_player_gameweek_spine /
build_player_gameweek_state directly) rather than touching staging or
intermediate layers.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.curated.gameweek_context import get_gameweek_context
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.exceptions import DataFreshnessError
from dal.staging import get_staged_player_histories
from dal.state.player_gameweek_state import build_player_gameweek_state


def get_curated_spine(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the curated player-gameweek spine.

    Canonical entry point for all downstream consumers that need historical
    player performance data at (player_id, gw) grain.
    """
    return build_player_gameweek_spine(db_path)


def get_state_features(spine: pd.DataFrame) -> pd.DataFrame:
    """Return the state feature table derived from the curated spine.

    Appends rolling windows, trends, and fixture context to the spine.
    All output columns are documented in dal/state/STATE_CONTRACT.md.
    """
    return build_player_gameweek_state(spine)


def validate_data_freshness(db_path: Path, gw: int) -> None:
    """Validate that the DB contains data for the target GW.

    Raises DataFreshnessError if:
    - GW not present in events table
    - gw > 1 and no player_histories rows exist for gw - 1
    """
    events = get_gameweek_context(db_path)
    if not (events["gw"] == gw).any():
        raise DataFreshnessError(f"GW {gw} not found in events")
    if gw > 1:
        hist = get_staged_player_histories(db_path)
        if not (hist["gw"] == gw - 1).any():
            raise DataFreshnessError(
                f"No player_histories rows found for GW {gw - 1} — DB may be stale"
            )
