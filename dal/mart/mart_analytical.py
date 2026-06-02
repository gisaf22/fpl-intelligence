"""Analytical mart — spine + state, filtered and reshaped for analysis.

This is the EDA and modeling dataset. It is NOT the registry population
builder in registry/builder.py (_build_registry_population).

How this file differs from registry/builder.py
-----------------------------------------------
  This file (dal/mart/mart_analytical.py):
    - Does NOT filter by minutes — retains the full player-gameweek grain so
      EDA can observe low-minute rows and model training can choose its own
      population cuts.
    - Derives GOVERNED_SIGNAL_COLUMNS dynamically from the feat layer
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

import pandas as pd

from dal.feat.feat_schema import FEATURE_REGISTRY
from dal.mart.mart_schema import validate_mart

POSITION_CODE_MAP: dict[int, str] = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# Canonical governed signal columns — derived from FEATURE_REGISTRY so this list
# stays in sync automatically when columns are added or removed from the feat layer.
GOVERNED_SIGNAL_COLUMNS: tuple[str, ...] = tuple(FEATURE_REGISTRY.keys())


def build_prepared_dataset(
    features: pd.DataFrame,
    data_cutoff_gw: int,
    *,
    validate: bool = True,
) -> pd.DataFrame:
    """Build the governed analytical dataset from the pre-built features frame.

    Filters to gw <= data_cutoff_gw and adds a string position column mapped from
    position_code. Does not call feat — caller must pass an already-built features frame
    from build_player_gameweek_state().

    Grain: (player_id, gw) — unchanged from features input.
    All GOVERNED_SIGNAL_COLUMNS are present on exit (may be NaN in warmup GWs).

    Args:
        validate: when True (default) the output is checked against MART_SCHEMA and the
            (player_id, gw) grain — the serving boundary is fail-closed (raises
            DALContractViolation). Pass validate=False only for isolation/unit tests that
            exercise the transform mechanics on a deliberately partial frame.
    """
    if data_cutoff_gw <= 0:
        raise ValueError(f"data_cutoff_gw must be positive, got {data_cutoff_gw}")

    filtered = features[features["gw"] <= data_cutoff_gw].copy()
    filtered["position"] = filtered["position_code"].map(POSITION_CODE_MAP)
    filtered = filtered.reset_index(drop=True)

    if validate:
        validate_mart(filtered)
    return filtered
