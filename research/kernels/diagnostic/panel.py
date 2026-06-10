"""Panel-structure correlation kernel — domain-agnostic Spearman decomposition."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from domain.registry.association import PANEL_CLASS_THRESHOLDS as _DEFAULT_PANEL_CLASS_THRESHOLDS


def split_between_within_player_rho(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    player_col: str = "player_id",
    min_n_players: int = 20,
    min_n_shape: int = 100,
    panel_class_thresholds: list[tuple[float, str]] | None = None,
) -> dict[str, Any]:
    """Separate the pooled Spearman rho into between-player and within-player contributions.

    A high between-player share means the signal predicts which players are
    consistently better (identity effect). A high within-player share means it
    predicts when the same player outperforms their own baseline (state effect).
    The panel_class label summarises this split for governance decisions.

    Output fields:
      panel_class:        state_sensitive | mixed | identity_dominant | indeterminate
      decomposition_flag: empty string on success; 'unstable_ratio' when
                          abs(rho_within) > abs(rho_pooled), which can occur due to
                          noise at low pooled rho — panel_class is 'indeterminate'
                          in this case. Check decomposition_flag when panel_class
                          is indeterminate to distinguish insufficient data from
                          unstable decomposition.
      support_flag:       'insufficient_support' when n < min_n_shape or
                          n_players < min_n_players; empty string otherwise.
    """
    if panel_class_thresholds is None:
        panel_class_thresholds = _DEFAULT_PANEL_CLASS_THRESHOLDS

    empty = {
        "rho_pooled": np.nan,
        "rho_between": np.nan,
        "rho_within": np.nan,
        "within_share": np.nan,
        "panel_class": "indeterminate",
        "decomposition_flag": "",
        "n_records": 0,
        "n_players": 0,
        "support_flag": "insufficient_support",
    }

    subset = (
        df[df["position"] == position][[player_col, signal, target]].dropna().copy()
    )
    n = len(subset)

    if n < min_n_shape:
        return {**empty, "n_records": n}

    player_stats = (
        subset.groupby(player_col)
        .agg(
            x_mean=(signal, "mean"),
            y_mean=(target, "mean"),
        )
        .reset_index()
    )

    n_players = len(player_stats)

    if n_players < min_n_players:
        return {**empty, "n_records": n, "n_players": n_players}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rho_between, _ = spearmanr(
            player_stats["x_mean"].astype(float),
            player_stats["y_mean"].astype(float),
        )

    sig_mean = subset.groupby(player_col)[signal].transform("mean")
    tgt_mean = subset.groupby(player_col)[target].transform("mean")
    subset["x_dm"] = subset[signal].astype(float) - sig_mean.astype(float)
    subset["y_dm"] = subset[target].astype(float) - tgt_mean.astype(float)
    dm_clean = subset[["x_dm", "y_dm"]].dropna()

    rho_within_val = np.nan
    if len(dm_clean) >= min_n_shape:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rho_within_val, _ = spearmanr(
                dm_clean["x_dm"].astype(float),
                dm_clean["y_dm"].astype(float),
            )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rho_pooled, _ = spearmanr(
            subset[signal].astype(float),
            subset[target].astype(float),
        )

    decomposition_flag = ""
    within_share = np.nan
    panel_class = "indeterminate"

    if abs(rho_pooled) > 0.01 and not np.isnan(rho_within_val):
        raw_ratio = abs(rho_within_val) / abs(rho_pooled)
        if raw_ratio > 1.0:
            decomposition_flag = "unstable_ratio"
        else:
            within_share = round(float(raw_ratio), 3)
            panel_class = next(
                label
                for threshold, label in panel_class_thresholds
                if within_share >= threshold
            )

    return {
        "rho_pooled": round(float(rho_pooled), 4),
        "rho_between": round(float(rho_between), 4),
        "rho_within": round(float(rho_within_val), 4)
        if not np.isnan(rho_within_val)
        else np.nan,
        "within_share": within_share,
        "panel_class": panel_class,
        "decomposition_flag": decomposition_flag,
        "n_records": n,
        "n_players": n_players,
        "support_flag": "",
    }
