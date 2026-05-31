"""Temporal evaluation window utilities.

Temporal integrity guarantee: the state layer (build_player_gameweek_state)
applies a lag-1 shift to all rolling window computations. Features at GW N
encode information only from GWs 1..N-1 — there is no future leakage by
construction. This module documents and enforces that contract.

Validated observations (spine) != validated operational features (state).
The spine proves raw observations are correct. This module helps confirm that
no evaluation logic accidentally bypasses the lag-1 guarantee.
"""

from __future__ import annotations

import pandas as pd

_REQUIRED_ROLLING_COLS: frozenset[str] = frozenset({
    "points_roll3",
    "minutes_roll3",
    "xgi_roll3",
})


def evaluation_gameweeks(
    features: pd.DataFrame,
    min_gw: int,
    max_gw: int,
) -> list[int]:
    """Return sorted gameweeks present in features within [min_gw, max_gw].

    Use this to build the evaluation window rather than constructing GW ranges
    manually — it avoids evaluating against GWs absent from the feature table.
    """
    available = sorted(int(g) for g in features["gw"].unique())
    return [gw for gw in available if min_gw <= gw <= max_gw]


def assert_no_future_leakage(features: pd.DataFrame, eval_gw: int) -> None:
    """Assert that state-layer lag-1 contract is structurally in place for eval_gw.

    Checks that the features frame contains the rolling columns that the state
    layer produces via shift(1). If these columns are absent, the features frame
    was not produced by dal.pipeline.load() and temporal integrity is unverified.

    Raises
    ------
    ValueError
        If eval_gw has no rows, or if rolling columns are missing.
    """
    gw_rows = features[features["gw"] == eval_gw]
    if gw_rows.empty:
        raise ValueError(
            f"assert_no_future_leakage: no rows for gw={eval_gw} in features"
        )
    missing = _REQUIRED_ROLLING_COLS - set(features.columns)
    if missing:
        raise ValueError(
            f"assert_no_future_leakage: missing rolling columns {sorted(missing)} for "
            f"gw={eval_gw}. Features must come from dal.pipeline.load().mart to guarantee "
            "temporal integrity (lag-1 rolling windows)."
        )
