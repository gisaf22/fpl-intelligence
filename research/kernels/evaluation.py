"""Shared evaluation kernels — reusable, deterministic primitives for usefulness assessment.

These are consumed by BOTH the research form studies (``research/families/form/explore``) and the
decision backtest (``model/eval/decision``). ``research/kernels`` is the single home both may import:
research reaches it intra-layer, and ``model→research.kernels`` is the one research dependency the
import-linter permits (``no_model_to_research_analysis`` exempts kernels). They previously lived in
``tests/helpers`` — production code must not import from tests, so they are hoisted here.

Deterministic and None-safe by construction (a reproducibility contract of the research layer).
"""

from __future__ import annotations

import pandas as pd

_REQUIRED_ROLLING_COLS: frozenset[str] = frozenset({"points_roll3", "minutes_roll3", "xgi_roll3"})


def evaluation_gameweeks(features: pd.DataFrame, min_gw: int, max_gw: int) -> list[int]:
    """Sorted gameweeks present in ``features`` within [min_gw, max_gw].

    Use this to build an evaluation window rather than constructing GW ranges manually — it avoids
    evaluating against gameweeks absent from the feature table.
    """
    available = sorted(int(g) for g in features["gw"].unique())
    return [gw for gw in available if min_gw <= gw <= max_gw]


def assert_no_future_leakage(features: pd.DataFrame, eval_gw: int) -> None:
    """Assert the state-layer lag-1 contract is structurally in place for ``eval_gw``.

    Checks that the rolling columns the state layer produces via ``shift(1)`` are present. If they are
    absent, the features frame was not produced by ``dal.pipeline.load()`` and temporal integrity is
    unverified.

    Raises
    ------
    ValueError
        If ``eval_gw`` has no rows, or if rolling columns are missing.
    """
    gw_rows = features[features["gw"] == eval_gw]
    if gw_rows.empty:
        raise ValueError(f"assert_no_future_leakage: no rows for gw={eval_gw} in features")
    missing = _REQUIRED_ROLLING_COLS - set(features.columns)
    if missing:
        raise ValueError(
            f"assert_no_future_leakage: missing rolling columns {sorted(missing)} for "
            f"gw={eval_gw}. Features must come from dal.pipeline.load().mart to guarantee "
            "temporal integrity (lag-1 rolling windows)."
        )


def rank_correlation(predicted_values: pd.Series, actual_returns: pd.Series) -> float | None:
    """Spearman rank correlation between predicted values and actual returns.

    Both series must share the same index (player_id). Returns None if fewer than 2 overlapping
    observations. Interpretation: positive = higher-ranked players tended to score more.
    """
    common = predicted_values.index.intersection(actual_returns.index)
    if len(common) < 2:
        return None
    pred = predicted_values.loc[common].dropna()
    actual = actual_returns.loc[common].dropna()
    common2 = pred.index.intersection(actual.index)
    if len(common2) < 2:
        return None
    pred, actual = pred.loc[common2], actual.loc[common2]

    n = len(pred)
    pred_ranks = pred.rank()
    actual_ranks = actual.rank()
    d_sq = float(((pred_ranks - actual_ranks) ** 2).sum())
    denominator = n * (n**2 - 1)
    if denominator == 0:
        return None
    return float(1.0 - (6.0 * d_sq) / denominator)


def downside_rate(returns: pd.Series, threshold: float = 4.0) -> float | None:
    """Fraction of returns below ``threshold`` (catastrophic-miss rate). None if empty.

    FPL context: a captain returning < 4 points is typically a damaging outcome; downside rate answers
    how often a strategy produces such outcomes.
    """
    clean = returns.dropna()
    if clean.empty:
        return None
    return float((clean < threshold).mean())
