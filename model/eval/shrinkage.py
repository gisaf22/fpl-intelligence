"""Empirical-Bayes shrinkage ranker — Phase 1 deliverable D2.

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
    (no iterative MixedLM refit in the walk-forward loop — that is D1's job).

Shrinking toward the *mean* (not a robust center) is the decision from the
level-estimator study. This module ranks players who played; it does not predict
who will play (conditional on appearance, inherited from Phase 0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.eval.metrics import grouped_spearman
from model.eval.walkforward import (
    MIN_ROWS_PER_POS,
    POSITIONS,
    WARMUP_GW,
    _ndcg_at_k,
    _position_k,
    _precision_at_k,
)

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
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    pts = df.groupby("player_id")[value_col]

    # Player-level leakage-safe prior mean and prior appearance count.
    df["lvl_mean"] = pts.transform(lambda s: s.expanding().mean().shift(1))
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

    Mirrors ``score_levels_by_position`` on the common evaluation set (rows where both
    estimators are defined), so the shrink-vs-mean comparison is not a sampling
    artifact. Returns a frame indexed by (position, estimator).
    """
    features = build_shrunk_features(mart)
    cols = list(SHRINK_ESTIMATORS)

    # Leakage guard: both estimators are player-history — undefined on the first appearance.
    first = features.groupby("player_id").head(1)
    if bool(first[cols].notna().any(axis=1).any()):
        raise AssertionError("leakage: a shrink estimate is defined on a player's first appearance")

    post = features[features["gw"] > WARMUP_GW]
    ev = post[post[cols].notna().all(axis=1).to_numpy()]

    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        k = _position_k(int(sub.groupby("gw").size().median()))
        for col, label in SHRINK_ESTIMATORS.items():
            pk, nd = [], []
            for _, g in sub.groupby("gw"):
                if len(g) < MIN_ROWS_PER_POS or g[col].nunique() <= 1 or g["total_points"].nunique() <= 1:
                    continue
                p, a = g[col].to_numpy(), g["total_points"].to_numpy()
                pk.append(_precision_at_k(p, a, k))
                nd.append(_ndcg_at_k(p, a, k))
            rows.append({
                "position": pos, "estimator": label,
                "spearman": round(grouped_spearman(sub, col, "total_points", ["gw"], MIN_ROWS_PER_POS), 4),
                "precision_at_k": round(float(np.mean(pk)), 4) if pk else np.nan,
                "ndcg_at_k": round(float(np.mean(nd)), 4) if nd else np.nan,
                "k": k, "n_gw": len(sub["gw"].unique()),
            })
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "estimator"])
