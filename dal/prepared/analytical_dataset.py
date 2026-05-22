"""Prepared analytical dataset — spine + state, filtered and reshaped for analysis.

This is the EDA and modeling dataset. It is NOT the registry population
builder in registry/builder.py (_build_registry_population).

How this file differs from registry/builder.py
-----------------------------------------------
  This file (dal/prepared/analytical_dataset.py):
    - Does NOT filter by minutes — retains the full player-gameweek grain so
      EDA can observe low-minute rows and model training can choose its own
      population cuts.
    - Derives GOVERNED_SIGNAL_COLUMNS dynamically from the state layer
      (_ROLL_COLS) so the signal list stays in sync with the DAL automatically.
    - Intended caller: research/, EDA notebooks, and modeling pipelines.

  registry/builder.py (_build_registry_population):
    - Applies MINUTES_THRESHOLD = 60 to restrict to meaningful playing time.
    - Uses a hardcoded signal list fixed at authoring time.
    - Intended caller: registry/ pipeline only (registry assembly, model scoring).

Downstream EDA, lenses, and modeling must use this module rather than:
  - querying staging tables directly
  - calling build_player_gameweek_state and rebuilding grain semantics themselves
  - reimplementing position code mapping
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.state.player_gameweek_state import _ROLL_COLS, build_player_gameweek_state

POSITION_CODE_MAP: dict[int, str] = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# Canonical governed signal columns — state rolling windows and trend.
# Built from _ROLL_COLS so this list stays in sync with the state layer.
GOVERNED_SIGNAL_COLUMNS: tuple[str, ...] = tuple(
    col
    for base in _ROLL_COLS
    for col in (
        f"{'points' if base == 'total_points' else base}_roll3",
        f"{'points' if base == 'total_points' else base}_roll5",
    )
) + ("minutes_trend",)


def build_prepared_dataset(
    spine: pd.DataFrame,
    data_cutoff_gw: int,
) -> pd.DataFrame:
    """Build the governed analytical dataset from the curated spine.

    Steps:
      1. Derive state features via build_player_gameweek_state.
      2. Filter to gw <= data_cutoff_gw.
      3. Add string `position` column mapped from position_code.

    Grain: (player_id, gw) — unchanged from spine.
    All GOVERNED_SIGNAL_COLUMNS are present on exit (may be NaN in warmup GWs).
    """
    if data_cutoff_gw <= 0:
        raise ValueError(f"data_cutoff_gw must be positive, got {data_cutoff_gw}")

    state = build_player_gameweek_state(spine)
    filtered = state[state["gw"] <= data_cutoff_gw].copy()
    filtered["position"] = filtered["position_code"].map(POSITION_CODE_MAP)
    return filtered.reset_index(drop=True)
