"""Naive baseline strategies for evaluation comparison.

Baselines are the mandatory comparison floor: an operational heuristic is
only meaningful if it outperforms these deterministic, transparent alternatives.

All baselines are:
- Deterministic: fixed seed for random, stable sort for ties
- Transparent: single-signal ranking, no composite weights
- Reproducible: same features + same GW = same ranking always

Usage: pair each baseline against the corresponding intelligence output to
compute lift. If the heuristic cannot beat baseline_recent_points on mean
captain return, the static weights provide no marginal value.
"""

from __future__ import annotations

import pandas as pd


def _eligible_at_gw(
    features: pd.DataFrame,
    target_gw: int,
    minutes_col: str,
    threshold: float,
) -> pd.DataFrame:
    """Filter to eligible players at target_gw by minutes threshold."""
    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        return gw_df
    return gw_df[gw_df[minutes_col].fillna(0) >= threshold]


def baseline_recent_points(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    min_minutes_roll3: float = 45.0,
) -> pd.DataFrame:
    """Rank players by points_roll3 only (naive recent-form baseline).

    The simplest plausible heuristic: just pick whoever scored most recently.
    Used as primary captain and transfer comparison baseline.
    """
    eligible = _eligible_at_gw(features, target_gw, "minutes_roll3", min_minutes_roll3)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label", "points_roll3"])
    return (
        eligible[["player_id", "player_name", "position_label", "points_roll3"]]
        .sort_values("points_roll3", ascending=False, kind="stable")
        .head(n)
        .reset_index(drop=True)
    )


def baseline_highest_xgi(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    min_minutes_roll3: float = 45.0,
) -> pd.DataFrame:
    """Rank players by xgi_roll3 only (naive involvement baseline).

    Selects players with highest expected goal involvement average regardless
    of fixture difficulty or consistency signals.
    """
    eligible = _eligible_at_gw(features, target_gw, "minutes_roll3", min_minutes_roll3)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label", "xgi_roll3"])
    return (
        eligible[["player_id", "player_name", "position_label", "xgi_roll3"]]
        .sort_values("xgi_roll3", ascending=False, kind="stable")
        .head(n)
        .reset_index(drop=True)
    )


def baseline_fixture_only(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    min_minutes_roll5: float = 30.0,
) -> pd.DataFrame:
    """Rank players by fixture difficulty only (pure schedule baseline).

    Inverts fdr_avg so easy fixtures (low FDR) yield high scores. Tests
    whether schedule alone is a sufficient selection signal.
    """
    eligible = _eligible_at_gw(features, target_gw, "minutes_roll5", min_minutes_roll5)
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


def baseline_random_top_n(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    seed: int = 42,
    min_minutes_roll5: float = 30.0,
) -> pd.DataFrame:
    """Random eligible player selection with fixed seed (stochastic floor baseline).

    Reproducible via fixed seed. Tests whether any structured ranking does better
    than random selection from the eligible pool.
    """
    eligible = _eligible_at_gw(features, target_gw, "minutes_roll5", min_minutes_roll5)
    if eligible.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position_label"])
    sample_size = min(n, len(eligible))
    return (
        eligible[["player_id", "player_name", "position_label"]]
        .sample(n=sample_size, random_state=seed)
        .reset_index(drop=True)
    )
