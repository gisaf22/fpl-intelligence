"""Gameweek context — per-gameweek metadata enrichment at gw grain.

get_gameweek_context is a pure transform: accepts the staged events frame, no I/O.
resolve_target_gw is an operational helper that still takes db_path — it is not
part of the pipeline data flow and is called directly by intelligence modules.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.exceptions import DALContractViolation
from dal.fct.fct_contracts import GAMEWEEK_CONTEXT_COLS
from dal.staging import get_staged_events
from dal.validation.grain import validate_grain_uniqueness


def get_gameweek_context(events: pd.DataFrame) -> pd.DataFrame:
    """Return one row per gw with gameweek status, deadline, and scoring metadata."""
    events = events[GAMEWEEK_CONTEXT_COLS]
    validate_grain_uniqueness(events, "gameweek_context")
    _validate_gw_sequence(events)
    return events


def resolve_target_gw(db_path: Path) -> int:
    """Resolve the target GW from the events table.

    Resolution order:
    1. Row where is_live == True → return its gw
    2. Row where is_next == True → return its gw
    3. Minimum gw where finished == False → return it
    4. Raise ValueError if none of the above apply.
    """
    df = get_gameweek_context(get_staged_events(db_path))

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

            validation="get_gameweek_context",
            n_violations=len(missing),
            error_code="TIME_CONTINUITY",
        )
