"""Player-level variance decomposition.

ANOVA-style split of a season-pooled target into between-player and
within-player components. Used in foundation EDA to characterise whether a
target's spread is mostly persistent player quality or week-to-week
variation.

``DEFAULT_MIN_APPEARANCES = 10`` excludes players whose own mean/variance
would be unreliable on too few observations. It is an operational choice, not
a statistical derivation.
"""

from __future__ import annotations

import pandas as pd

# Minimum player-gameweek rows a player needs to be included in the decomposition.
DEFAULT_MIN_APPEARANCES = 10


def decompose_variance(
    df: pd.DataFrame,
    value_col: str = "total_points",
    group_col: str = "player_id",
    min_appearances: int = DEFAULT_MIN_APPEARANCES,
) -> dict[str, float]:
    """ANOVA-style decomposition of total variance into between/within components.

    SS_total is split as SS_total = SS_between + SS_within, where SS_between
    measures dispersion of group means around the grand mean and SS_within
    measures dispersion of observations around their own group's mean.

    Args:
        df:              Analytical dataset with `group_col` and `value_col` columns.
        value_col:       Numeric column to decompose (e.g. 'total_points').
        group_col:       Grouping column identifying the unit of repetition (e.g. 'player_id').
        min_appearances: Groups with fewer than this many observations are excluded
                          before decomposing, since their own mean is unreliable.

    Returns:
        Dict with keys: n_players, n_obs, grand_mean, ss_total, ss_between,
        ss_within, pct_between, pct_within. pct_between and pct_within sum to
        100 (or are both NaN if ss_total is 0 or no groups qualify).

    Raises:
        ValueError: if `group_col` or `value_col` is missing from df.
    """
    if group_col not in df.columns:
        raise ValueError(f"df missing required column: '{group_col}'")
    if value_col not in df.columns:
        raise ValueError(f"df missing required column: '{value_col}'")

    data = df[[group_col, value_col]].dropna()
    counts = data.groupby(group_col)[value_col].transform("count")
    data = data[counts >= min_appearances]

    n_obs = len(data)
    n_players = data[group_col].nunique()
    if n_obs == 0:
        return {
            "n_players": 0,
            "n_obs": 0,
            "grand_mean": float("nan"),
            "ss_total": float("nan"),
            "ss_between": float("nan"),
            "ss_within": float("nan"),
            "pct_between": float("nan"),
            "pct_within": float("nan"),
        }

    grand_mean = float(data[value_col].mean())
    ss_total = float(((data[value_col] - grand_mean) ** 2).sum())

    group_means = data.groupby(group_col)[value_col].transform("mean")
    ss_within = float(((data[value_col] - group_means) ** 2).sum())
    ss_between = ss_total - ss_within

    if ss_total == 0:
        pct_between = float("nan")
        pct_within = float("nan")
    else:
        pct_between = ss_between / ss_total * 100
        pct_within = ss_within / ss_total * 100

    return {
        "n_players": n_players,
        "n_obs": n_obs,
        "grand_mean": grand_mean,
        "ss_total": ss_total,
        "ss_between": ss_between,
        "ss_within": ss_within,
        "pct_between": pct_between,
        "pct_within": pct_within,
    }
