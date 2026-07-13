"""Point-estimate stress test — is the mean the right summary of a player's "level"?

Pre-Phase-1 experiment. The season *mean* is theory-optimal for accumulation but a
high-variance estimator on a zero-inflated, haul-driven target. This module builds
alternative leakage-safe summaries of a player's **strictly-prior** points and scores
each as a within-position ranker of next-GW points on the Phase-0 harness — to decide
what Phase-1 shrinkage should shrink toward.

Every estimator is an expanding statistic over a player's own prior appearances
(``shift(1)`` first), so it is leakage-safe by construction. Population and metrics are
inherited from Phase 0 (``minutes > 0``, DGW excluded, warmup GW>3, within-position
ranking only, common evaluation set).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import trim_mean

from model.eval.baselines import expanding_prior_mean
from model.eval.population import canonical
from model.eval.walkforward import WARMUP_GW, score_topk_by_position

# Recency half-life (in appearances) for the exponentially-weighted mean.
EW_HALFLIFE = 5
# Two-sided trim fraction for the trimmed mean.
TRIM_FRAC = 0.1

# Estimator column -> human label. 'mean' is the incumbent (== base_season).
LEVEL_ESTIMATORS: dict[str, str] = {
    "lvl_mean": "mean (incumbent)",
    "lvl_median": "median",
    "lvl_trim": "trimmed mean (10%)",
    "lvl_huber": "Huber M-estimator",
    "lvl_p75": "p75 (upside)",
    "lvl_p90": "p90 (ceiling)",
    "lvl_ew": f"EW mean (hl={EW_HALFLIFE})",
}


def _huber_loc(x: np.ndarray, k: float = 1.345, iters: int = 25, tol: float = 1e-6) -> float:
    """Huber M-estimator of location — outlier-downweighted center, dependency-free."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.nan
    if x.size < 3:
        return float(np.mean(x))
    mu = float(np.median(x))
    s = float(np.median(np.abs(x - mu)) * 1.4826)
    if s <= 0:
        return mu
    for _ in range(iters):
        r = (x - mu) / s
        w = np.where(np.abs(r) <= k, 1.0, k / np.abs(np.where(r == 0, 1e-9, r)))
        new = float((w * x).sum() / w.sum())
        if abs(new - mu) < tol * s:
            mu = new
            break
        mu = new
    return mu


def build_level_features(mart: pd.DataFrame) -> pd.DataFrame:
    """Attach leakage-safe alternative 'level' estimates to each player-gameweek row.

    Same population contract as ``baselines.build_baseline_features``: ``minutes > 0``,
    DGW excluded, sorted by (player, gw). Every column is an expanding statistic over a
    player's strictly-prior points (``shift(1)``), so it never sees the current row.
    """
    df = canonical(mart)
    pts = df.groupby("player_id")["total_points"]

    # Compute the expanding statistic over rows 1..t, THEN shift(1) so row t sees only
    # rows 1..t-1. (Shifting first would leak a NaN into every apply() window.)
    def prior_expand(fn):
        return pts.transform(lambda s: s.expanding().apply(fn, raw=True).shift(1))

    # lvl_mean is the shared Phase-0 incumbent (expanding prior mean) on the canonical population.
    df["lvl_mean"] = expanding_prior_mean(df)
    df["lvl_median"] = pts.transform(lambda s: s.expanding().median().shift(1))
    df["lvl_trim"] = prior_expand(lambda a: trim_mean(a, TRIM_FRAC))
    df["lvl_huber"] = prior_expand(_huber_loc)
    df["lvl_p75"] = prior_expand(lambda a: np.quantile(a, 0.75))
    df["lvl_p90"] = prior_expand(lambda a: np.quantile(a, 0.90))
    df["lvl_ew"] = pts.transform(lambda s: s.ewm(halflife=EW_HALFLIFE).mean().shift(1))
    return df


def score_levels_by_position(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-(position, estimator) within-position ranking on the common evaluation set.

    Routes through the shared :func:`model.eval.walkforward.score_topk_by_position`, so each cell now
    carries a **block-bootstrap CI** (``ci_lo``/``ci_hi``) and ``coverage`` alongside spearman /
    precision_at_k / ndcg_at_k. Returns a frame indexed by (position, estimator), positions ordered
    GK->DEF->MID->FWD, estimators by spearman.
    """
    features = build_level_features(mart)
    cols = list(LEVEL_ESTIMATORS)
    # leakage guard: every estimator is player-history — undefined on the first appearance.
    first = features.groupby("player_id").head(1)
    if bool(first[cols].notna().any(axis=1).any()):
        raise AssertionError("leakage: a level estimate is defined on a player's first appearance")

    post = features[features["gw"] > WARMUP_GW]
    scored = score_topk_by_position(post, LEVEL_ESTIMATORS).rename(columns={"model": "estimator"})
    return scored.set_index(["position", "estimator"])[
        ["spearman", "ci_lo", "ci_hi", "precision_at_k", "ndcg_at_k", "coverage", "k", "n_gw"]
    ]
