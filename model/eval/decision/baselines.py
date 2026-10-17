"""Naive decision baselines — the mandatory comparison floor (promoted from tests/helpers; ADR-012 §5).

Deterministic single-signal rankers with a stable-sort tie-break. A decision heuristic is only
meaningful if it beats these; the backtest reports each heuristic *relative to* them.
"""

from __future__ import annotations

import pandas as pd


def _eligible_at_gw(features: pd.DataFrame, gw: int, minutes_col: str, threshold: float) -> pd.DataFrame:
    """Rows at ``gw`` whose ``minutes_col`` clears ``threshold``."""
    gw_df = features[features["gw"] == gw].copy()
    if gw_df.empty:
        return gw_df
    return gw_df[gw_df[minutes_col].fillna(0) >= threshold]


def baseline_recent_points(
    features: pd.DataFrame, gw: int, n: int = 20, min_minutes_roll3: float = 45.0
) -> pd.DataFrame:
    """Rank by ``points_roll3`` only — the simplest recent-form floor."""
    eligible = _eligible_at_gw(features, gw, "minutes_roll3", min_minutes_roll3)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label", "points_roll3"])
    return (
        eligible[["player_id", "player_name", "position_label", "points_roll3"]]
        .sort_values("points_roll3", ascending=False, kind="stable")
        .head(n)
        .reset_index(drop=True)
    )


def baseline_highest_xgi(features: pd.DataFrame, gw: int, n: int = 20, min_minutes_roll3: float = 45.0) -> pd.DataFrame:
    """Rank by ``xgi_roll3`` only — the naive involvement floor."""
    eligible = _eligible_at_gw(features, gw, "minutes_roll3", min_minutes_roll3)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label", "xgi_roll3"])
    return (
        eligible[["player_id", "player_name", "position_label", "xgi_roll3"]]
        .sort_values("xgi_roll3", ascending=False, kind="stable")
        .head(n)
        .reset_index(drop=True)
    )


def baseline_fixture_only(
    features: pd.DataFrame, gw: int, n: int = 20, min_minutes_roll5: float = 30.0
) -> pd.DataFrame:
    """Rank by fixture difficulty only — inverts ``fdr_avg`` so easy fixtures score high (schedule floor)."""
    eligible = _eligible_at_gw(features, gw, "minutes_roll5", min_minutes_roll5)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label", "fdr_score"])
    eligible = eligible.copy()
    eligible["fdr_score"] = 6.0 - eligible["fdr_avg"].fillna(3.0)
    return (
        eligible[["player_id", "player_name", "position_label", "fdr_score"]]
        .sort_values("fdr_score", ascending=False, kind="stable")
        .head(n)
        .reset_index(drop=True)
    )
