"""Panel-structure correlation kernel — domain-agnostic rank-correlation decomposition.

Spearman (default) or Kendall tau-b (``method="kendall"``) — the latter tie-corrected for
heavily tied (zero-inflated) signals, offered as a sensitivity check on the Spearman read.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from domain.registry.association import PANEL_CLASS_THRESHOLDS as _DEFAULT_PANEL_CLASS_THRESHOLDS
from research.kernels.diagnostic._rankcorr import _METHODS
from research.kernels.diagnostic._rankcorr import rank_corr as _rank_corr

# Bootstrap defaults — mirror inferential.resampling so studies quote comparable
# intervals; kept local so this kernel stays a leaf (no cross-kernel import).
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 0
CI_LEVEL = 0.95


def split_between_within_player_rho(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    player_col: str = "player_id",
    min_n_players: int = 20,
    min_n_shape: int = 100,
    min_appearances: int = 1,
    panel_class_thresholds: list[tuple[float, str]] | None = None,
    method: str = "spearman",
) -> dict[str, Any]:
    """Separate the pooled rank correlation into between-player and within-player contributions.

    A high between-player share means the signal predicts which players are
    consistently better (identity effect). A high within-player share means it
    predicts when the same player outperforms their own baseline (state effect).
    The panel_class label summarises this split for governance decisions. ``method`` selects the
    rank correlation — ``'spearman'`` (default) or ``'kendall'`` (tau-b, tie-corrected).
    ``min_appearances`` drops players with fewer than that many games before the split (default
    1 = no filter), so the population can be aligned with the ``decompose_variance`` between/within
    partition — a one-game player has an unreliable season mean (between) and a zero deviation (within).

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
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")

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

    subset = df[df["position"] == position][[player_col, signal, target]].dropna().copy()
    if min_appearances > 1:
        # Share one population with the Step-1 ceiling: drop players with too few games, whose
        # season mean (between) and own-deviations (within) would otherwise be unreliable.
        appearances = subset.groupby(player_col)[player_col].transform("size")
        subset = subset[appearances >= min_appearances]
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

    rho_between = _rank_corr(
        player_stats["x_mean"].astype(float),
        player_stats["y_mean"].astype(float),
        method,
    )

    sig_mean = subset.groupby(player_col)[signal].transform("mean")
    tgt_mean = subset.groupby(player_col)[target].transform("mean")
    subset["x_dm"] = subset[signal].astype(float) - sig_mean.astype(float)
    subset["y_dm"] = subset[target].astype(float) - tgt_mean.astype(float)
    dm_clean = subset[["x_dm", "y_dm"]].dropna()

    rho_within_val = np.nan
    if len(dm_clean) >= min_n_shape:
        rho_within_val = _rank_corr(
            dm_clean["x_dm"].astype(float),
            dm_clean["y_dm"].astype(float),
            method,
        )

    rho_pooled = _rank_corr(
        subset[signal].astype(float),
        subset[target].astype(float),
        method,
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
            panel_class = next(label for threshold, label in panel_class_thresholds if within_share >= threshold)

    return {
        "rho_pooled": round(float(rho_pooled), 4),
        "rho_between": round(float(rho_between), 4),
        "rho_within": round(float(rho_within_val), 4) if not np.isnan(rho_within_val) else np.nan,
        "within_share": within_share,
        "panel_class": panel_class,
        "decomposition_flag": decomposition_flag,
        "n_records": n,
        "n_players": n_players,
        "support_flag": "",
    }


def _safe_rank_corr(a: np.ndarray, b: np.ndarray, method: str) -> float:
    """Rank correlation, or NaN when either side is constant (avoids scipy's warning/NaN noise)."""
    if np.unique(a).size <= 1 or np.unique(b).size <= 1:
        return np.nan
    return _rank_corr(a, b, method)


def _percentile_ci(values: list[float], ci_level: float) -> tuple[float, float]:
    """Two-sided percentile CI over the non-NaN bootstrap draws, rounded to 4 dp."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (np.nan, np.nan)
    alpha = 1.0 - ci_level
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return (round(lo, 4), round(hi, 4))


def _bootstrap_two_sided_p(values: list[float]) -> float:
    """Two-sided bootstrap p-value for H0: statistic = 0, over the non-NaN draws.

    Uses the ``(1 + k) / (1 + n)`` plug-in so the p-value is never exactly 0 (no finite draw
    count is treated as infinitely significant). Because the draws are player-resampled, this
    p-value respects player clustering — unlike scipy's Spearman p, which assumes independent
    rows and is anticonservative when the same players recur. Feeds the BH-FDR screen.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return np.nan
    tail = min(int(np.sum(arr <= 0.0)), int(np.sum(arr >= 0.0)))
    return round(min(1.0, 2.0 * (1 + tail) / (1 + arr.size)), 4)


def _within_share_band(value: float, thresholds: list[tuple[float, str]]) -> str | None:
    """Map a within_share value to its panel-class band, or None when not finite."""
    if value is None or np.isnan(value):
        return None
    return next(label for threshold, label in thresholds if value >= threshold)


def bootstrap_panel_decomposition(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    player_col: str = "player_id",
    n_boot: int = N_BOOTSTRAP,
    ci_level: float = CI_LEVEL,
    seed: int = BOOTSTRAP_SEED,
    min_n_players: int = 20,
    min_n_shape: int = 100,
    min_appearances: int = 1,
    panel_class_thresholds: list[tuple[float, str]] | None = None,
    method: str = "spearman",
) -> dict[str, Any]:
    """Player-clustered bootstrap CIs for the between/within split, with a CI-gated class.

    ``method`` ('spearman' default, or 'kendall' tau-b for tie-heavy signals) and ``min_appearances``
    (default 1 = no filter) are passed through to the point estimate and every bootstrap draw, so the
    CI is computed on the same metric and the same player population.

    Resamples **players** (clusters) with replacement ``n_boot`` times, recomputing the full
    decomposition each draw, and returns percentile CIs for ``rho_pooled`` / ``rho_between`` /
    ``rho_within`` / ``within_share`` alongside the observed point estimate (from
    ``split_between_within_player_rho``). The point estimate alone over-claims on one season;
    this adds the uncertainty and only assigns a class when the evidence is unambiguous.

    Resampling is clustered by **player, not row**: the between/within structure is defined by
    the player grouping, so a row bootstrap would dissolve it. A player drawn twice contributes
    twice (its rows enter the pooled/within draw twice and its mean enters the between draw
    twice), which is what gives the CI its honest, player-driven width.

    ``panel_class`` (CI-gated — assigned only when earned, else abstains):
      * ``identity_dominant`` | ``mixed`` | ``state_sensitive`` — the ``within_share`` CI lies
        wholly inside one threshold band.
      * ``undecomposable``       — the ``rho_pooled`` CI includes 0 (no association to split).
      * ``indeterminate``        — the ``within_share`` CI straddles a band boundary.
      * ``insufficient_support`` — below the sample floors; no bootstrap is attempted.

    Returns:
        ``{rho_pooled, rho_pooled_ci, rho_pooled_p, rho_between, rho_between_ci, rho_within,
        rho_within_ci, within_share, within_share_ci, panel_class, decomposition_flag, n_records,
        n_players, n_boot, support_flag}``. Each ``*_ci`` is a ``(lower, upper)`` tuple (NaNs when
        not estimable); ``rho_pooled_p`` is the player-clustered bootstrap p-value for pooled != 0
        (feeds the BH-FDR screen). Deterministic given ``seed``.
    """
    if panel_class_thresholds is None:
        panel_class_thresholds = _DEFAULT_PANEL_CLASS_THRESHOLDS

    point = split_between_within_player_rho(
        df,
        signal,
        target,
        position,
        player_col=player_col,
        min_n_players=min_n_players,
        min_n_shape=min_n_shape,
        min_appearances=min_appearances,
        panel_class_thresholds=panel_class_thresholds,
        method=method,
    )
    nan_ci = (np.nan, np.nan)
    base = {
        "rho_pooled": point["rho_pooled"],
        "rho_pooled_ci": nan_ci,
        "rho_pooled_p": np.nan,
        "rho_between": point["rho_between"],
        "rho_between_ci": nan_ci,
        "rho_within": point["rho_within"],
        "rho_within_ci": nan_ci,
        "within_share": point["within_share"],
        "within_share_ci": nan_ci,
        "panel_class": point["panel_class"],
        "decomposition_flag": point["decomposition_flag"],
        "n_records": point["n_records"],
        "n_players": point["n_players"],
        "n_boot": 0,
        "support_flag": point["support_flag"],
    }
    if point["support_flag"] == "insufficient_support":
        return {**base, "panel_class": "insufficient_support"}

    # Precompute the fixed building blocks on the analysis subset. A player's own-mean
    # deviations do not change with which players are resampled, so they are computed once.
    subset = df[df["position"] == position][[player_col, signal, target]].dropna()
    if min_appearances > 1:
        appearances = subset.groupby(player_col)[player_col].transform("size")
        subset = subset[appearances >= min_appearances]
    subset = subset.reset_index(drop=True)
    sig = subset[signal].to_numpy(dtype=float)
    tgt = subset[target].to_numpy(dtype=float)
    sig_dm = sig - subset.groupby(player_col)[signal].transform("mean").to_numpy(dtype=float)
    tgt_dm = tgt - subset.groupby(player_col)[target].transform("mean").to_numpy(dtype=float)

    groups = subset.groupby(player_col, sort=False)
    pmeans = groups.agg(x_mean=(signal, "mean"), y_mean=(target, "mean"))
    mean_sig = pmeans["x_mean"].to_numpy(dtype=float)
    mean_tgt = pmeans["y_mean"].to_numpy(dtype=float)
    row_index_by_player = [groups.indices[p] for p in pmeans.index]
    n_players = len(pmeans)

    rng = np.random.default_rng(seed)
    boot = {"pooled": [], "between": [], "within": [], "share": []}
    for _ in range(n_boot):
        drawn = rng.integers(0, n_players, size=n_players)
        rho_b = _safe_rank_corr(mean_sig[drawn], mean_tgt[drawn], method)
        rows = np.concatenate([row_index_by_player[d] for d in drawn])
        rho_p = _safe_rank_corr(sig[rows], tgt[rows], method)
        rho_w = _safe_rank_corr(sig_dm[rows], tgt_dm[rows], method)
        share = abs(rho_w) / abs(rho_p) if (abs(rho_p) > 0.01 and not np.isnan(rho_w)) else np.nan
        boot["pooled"].append(rho_p)
        boot["between"].append(rho_b)
        boot["within"].append(rho_w)
        boot["share"].append(share)

    pooled_ci = _percentile_ci(boot["pooled"], ci_level)
    share_ci = _percentile_ci(boot["share"], ci_level)

    # CI-gated classification: abstain unless the evidence is unambiguous.
    lo_band = _within_share_band(share_ci[0], panel_class_thresholds)
    hi_band = _within_share_band(share_ci[1], panel_class_thresholds)
    if not np.isnan(pooled_ci[0]) and pooled_ci[0] <= 0.0 <= pooled_ci[1]:
        panel_class = "undecomposable"  # CI for the pooled association includes 0
    elif lo_band is not None and lo_band == hi_band:
        panel_class = lo_band
    else:
        panel_class = "indeterminate"

    return {
        **base,
        "rho_pooled_ci": pooled_ci,
        "rho_pooled_p": _bootstrap_two_sided_p(boot["pooled"]),
        "rho_between_ci": _percentile_ci(boot["between"], ci_level),
        "rho_within_ci": _percentile_ci(boot["within"], ci_level),
        "within_share_ci": share_ci,
        "panel_class": panel_class,
        "n_boot": n_boot,
    }
