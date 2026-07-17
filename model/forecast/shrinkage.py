"""Empirical-Bayes shrinkage ranker — the Phase 1 partial-pooling estimator.

Turns the Q1/Q1b between-vs-within split into a *predictive* estimator: a
partial-pooling shrinkage of each player's own prior mean toward the position's
prior grand mean. Few prior games ⇒ shrink hard to the position mean; many games
⇒ trust the player's own history.

    lvl_shrunk_{i,t} = mu_pos,t + lambda_{i,t} * (mean_{i,t} - mu_pos,t)
    lambda_{i,t}     = n_{i,t} / (n_{i,t} + sigma2_within / sigma2_between)

Everything is computed from **strictly-prior** rows (gw < t), so the estimator is
leakage-safe exactly like the Phase-0 baselines:
  * ``mean_{i,t}``  — player i's expanding prior mean (== Phase-0 ``base_season`` / ``lvl_mean``),
  * ``mu_pos,t``    — the position's expanding prior grand mean (the shrink target),
  * ``n_{i,t}``     — player i's prior appearance count,
  * ``sigma2_within/sigma2_between`` — the position's variance ratio, estimated by
    method-of-moments on the prior slice and re-estimated per evaluated gameweek
    (no iterative MixedLM refit in the walk-forward loop — that is the ICC study's job).

Shrinking toward the *mean* (not a robust center) is the decision from the
level-estimator study. This module ranks players who played; it does not predict
who will play (conditional on appearance, inherited from Phase 0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.eval.baselines import expanding_prior_mean
from model.eval.population import canonical
from model.eval.walkforward import WARMUP_GW, score_topk_by_position

# Minimum prior rows in a (position) slice before we trust its variance ratio.
MIN_PRIOR_ROWS = 30

# Columns produced/scored: the incumbent and the shrunk challenger.
SHRINK_ESTIMATORS: dict[str, str] = {
    "lvl_mean": "mean (incumbent)",
    "lvl_shrunk": "EB shrunk (Phase 1)",
}


def _variance_ratio_mom(prior: pd.DataFrame, value_col: str, group_col: str) -> float:
    """Method-of-moments sigma2_within / sigma2_between for a one-way unbalanced layout.

    Returns ``np.inf`` when between-variance is non-positive or the slice is too thin
    (⇒ lambda→0 ⇒ shrink fully to the position mean — the safe default early-season).
    """
    n_obs = len(prior)
    sizes = prior.groupby(group_col)[value_col].size().to_numpy()
    k = len(sizes)
    if k < 2 or n_obs <= k:
        return np.inf

    grand = float(prior[value_col].mean())
    x = prior[value_col].to_numpy()
    ss_total = float(((x - grand) ** 2).sum())
    group_means = prior.groupby(group_col)[value_col].transform("mean").to_numpy()
    ss_within = float(((x - group_means) ** 2).sum())
    ss_between = ss_total - ss_within

    msw = ss_within / (n_obs - k)
    msb = ss_between / (k - 1)
    n0 = (n_obs - (sizes**2).sum() / n_obs) / (k - 1)
    if n0 <= 0:
        return np.inf
    sigma2_between = (msb - msw) / n0
    if sigma2_between <= 0:
        return np.inf
    return msw / sigma2_between


def build_shrunk_features(mart: pd.DataFrame, value_col: str = "total_points") -> pd.DataFrame:
    """Attach the leakage-safe ``lvl_mean`` and ``lvl_shrunk`` columns per player-gameweek.

    Same population contract as the Phase-0 baselines: ``minutes > 0``, DGW excluded,
    sorted by (player, gw). ``mu_pos`` / ``var_ratio`` are computed from each row's
    strictly-prior position slice; players/rows with no usable prior slice get NaN.
    """
    df = canonical(mart)
    pts = df.groupby("player_id")[value_col]

    # Player-level leakage-safe prior mean (== Phase-0 ``base_season`` on the canonical
    # population) and prior appearance count.
    df["lvl_mean"] = (
        expanding_prior_mean(df) if value_col == "total_points"
        else pts.transform(lambda s: s.shift(1).expanding().mean())
    )
    df["prior_n"] = pts.transform(lambda s: s.expanding().count().shift(1))

    # Position-level prior grand mean and variance ratio, evaluated per (position, gw).
    df["mu_pos"] = np.nan
    df["var_ratio"] = np.nan
    for pos in df["position"].unique():
        pos_df = df[df["position"] == pos]
        for t in sorted(pos_df["gw"].unique()):
            prior = pos_df[pos_df["gw"] < t]
            if len(prior) < MIN_PRIOR_ROWS:
                continue
            mask = (df["position"] == pos) & (df["gw"] == t)
            df.loc[mask, "mu_pos"] = float(prior[value_col].mean())
            df.loc[mask, "var_ratio"] = _variance_ratio_mom(prior, value_col, "player_id")

    lam = df["prior_n"] / (df["prior_n"] + df["var_ratio"])
    df["lvl_shrunk"] = df["mu_pos"] + lam * (df["lvl_mean"] - df["mu_pos"])
    return df


def score_shrinkage_by_position(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-(position, estimator) within-position ranking of ``lvl_mean`` vs ``lvl_shrunk``.

    Routes through the shared :func:`model.eval.walkforward.score_topk_by_position` on the common
    evaluation set (rows where both estimators are defined), so the shrink-vs-mean comparison carries a
    **block-bootstrap CI** (``ci_lo``/``ci_hi``) + ``coverage`` and is not a sampling artifact. Returns
    a frame indexed by (position, estimator).
    """
    features = build_shrunk_features(mart)
    cols = list(SHRINK_ESTIMATORS)

    # Leakage guard: both estimators are player-history — undefined on the first appearance.
    first = features.groupby("player_id").head(1)
    if bool(first[cols].notna().any(axis=1).any()):
        raise AssertionError("leakage: a shrink estimate is defined on a player's first appearance")

    post = features[features["gw"] > WARMUP_GW]
    scored = score_topk_by_position(post, SHRINK_ESTIMATORS).rename(columns={"model": "estimator"})
    return scored.set_index(["position", "estimator"])[
        ["spearman", "ci_lo", "ci_hi", "precision_at_k", "ndcg_at_k", "coverage", "k", "n_gw"]
    ]
