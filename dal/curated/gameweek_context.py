"""Gameweek context — per-gameweek metadata enrichment at gw grain."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.staging import get_staged_events
from dal.curated.contracts import GAMEWEEK_CONTEXT_COLS
from dal.exceptions import DALContractViolation
from dal.validation.grain import validate_grain_uniqueness


def get_gameweek_context(db_path: Path) -> pd.DataFrame:
    """Return one row per gw with gameweek status, deadline, and scoring metadata."""
    events = get_staged_events(db_path)[GAMEWEEK_CONTEXT_COLS]
    validate_grain_uniqueness(events, "gameweek_context")
    _validate_gw_sequence(events)
    return events


def _validate_gw_sequence(events: pd.DataFrame) -> None:
    """Assert no gaps in the GW sequence within the events frame."""
    gws = sorted(events["gw"].tolist())
    if not gws:
        return
    expected = list(range(min(gws), max(gws) + 1))
    missing = sorted(set(expected) - set(gws))
    if missing:
        raise DALContractViolation(
            f"GW sequence gap in events table: GWs {missing} are missing. "
            f"The events table must have a contiguous sequence of GW rows.",
            layer="curated",
            validation="get_gameweek_context",
            n_violations=len(missing),
            error_code="TIME_GAP",
        )
