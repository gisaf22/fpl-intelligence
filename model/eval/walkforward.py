"""Walk-forward scoring harness — Phase 0.2 of the predictive-layer plan.

The temporal-CV substrate every later model plugs into. Because the baseline
features are built from strictly-prior gameweeks (see ``baselines.py``), scoring
each row against its own target *is* an expanding-window walk-forward: the
prediction for gameweek ``t`` uses only gameweeks ``< t``. This module verifies
that guarantee and reports per-gameweek and pooled metrics.

Metrics (headline is ranking, because FPL is won by ranking players, not by
hitting exact scores — and the target is zero-inflated / right-skewed, which
makes squared-error metrics haul-dominated and misleading):

  * ``spearman_mean``    — mean per-GW rank correlation (primary).
  * ``precision_at_k``   — mean per-GW share of the actual top-K in the predicted top-K (decision-relevant).
  * ``ndcg_at_k``        — mean per-GW NDCG@K, points as gains (rewards ranking real scorers high).
  * ``mae``              — mean absolute error (secondary, robust point-accuracy sanity).

RMSE is deliberately omitted: on this skewed target it is dominated by rare hauls.
Proper scoring for the distributional models (Poisson deviance, CRPS) arrives in
Phase 4, not here.

Fair comparison (fix A): all baselines are scored on the **common evaluation set**
— rows where every baseline is defined — so differences are not a sampling
artifact of unequal history requirements. Each baseline's ``coverage`` (share of
post-warmup rows on which it is defined at all) is reported separately.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from model.eval.baselines import BASELINES, build_baseline_features

# Gameweeks below this are warmup (too little history for rolling/expanding windows).
WARMUP_GW = 3
# Minimum rows in a gameweek to compute a stable per-GW metric.
MIN_ROWS_PER_GW = 20
# Top-K shortlist size for precision@K / NDCG@K (~top 7% of a ~300-player GW —
# the decision-relevant "would this be on my shortlist" scale).
TOP_K = 20

_PLAYER_HISTORY_BASELINES = ("base_last", "base_roll3", "base_roll5", "base_season")


def _assert_no_leakage(features: pd.DataFrame) -> None:
    """Guard: no player-history baseline may derive from a player's own current/future row."""
    first_rows = features.groupby("player_id").head(1)
    leaked = first_rows[list(_PLAYER_HISTORY_BASELINES)].notna().any(axis=1)
    if bool(leaked.any()):
        raise AssertionError("leakage: a player-history baseline is defined on a player's first appearance")


def _precision_at_k(pred: np.ndarray, actual: np.ndarray, k: int) -> float:
    """Share of the actual top-K scorers that appear in the predicted top-K."""
    k = min(k, len(pred))
    top_pred = set(np.argsort(-pred)[:k])
    top_actual = set(np.argsort(-actual)[:k])
    return len(top_pred & top_actual) / k


def _ndcg_at_k(pred: np.ndarray, actual: np.ndarray, k: int) -> float:
    """NDCG@K with points (clipped at 0) as gains, players ordered by prediction."""
    k = min(k, len(pred))
    gains = np.clip(actual, 0, None)
    disc = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = (gains[np.argsort(-pred)][:k] * disc).sum()
    idcg = (np.sort(gains)[::-1][:k] * disc).sum()
    return float(dcg / idcg) if idcg > 0 else np.nan


def score_predictions(
    features: pd.DataFrame, pred_col: str, target_col: str = "total_points",
    eval_mask: pd.Series | None = None,
) -> dict:
    """Ranking + accuracy metrics for one prediction column, averaged over post-warmup GWs.

    Args:
        features:  output of ``build_baseline_features``.
        pred_col:  the prediction column to score.
        target_col: the realised outcome column.
        eval_mask: optional boolean mask (aligned to ``features``) selecting the
                   common evaluation set; when given, scoring is restricted to it.

    Returns:
        Dict ``{spearman_mean, precision_at_k, ndcg_at_k, mae, n}``.
    """
    ev = features[features["gw"] > WARMUP_GW]
    if eval_mask is not None:
        ev = ev[eval_mask.loc[ev.index]]
    ev = ev.dropna(subset=[pred_col, target_col])
    if ev.empty:
        return {"spearman_mean": np.nan, "precision_at_k": np.nan, "ndcg_at_k": np.nan, "mae": np.nan, "n": 0}

    mae = float((ev[pred_col] - ev[target_col]).abs().mean())
    sp, pk, nd = [], [], []
    for _, g in ev.groupby("gw"):
        if len(g) < MIN_ROWS_PER_GW or g[pred_col].nunique() <= 1 or g[target_col].nunique() <= 1:
            continue
        p, a = g[pred_col].to_numpy(), g[target_col].to_numpy()
        sp.append(float(spearmanr(p, a).statistic))
        pk.append(_precision_at_k(p, a, TOP_K))
        nd.append(_ndcg_at_k(p, a, TOP_K))
    return {
        "spearman_mean": round(float(np.mean(sp)), 4) if sp else np.nan,
        "precision_at_k": round(float(np.mean(pk)), 4) if pk else np.nan,
        "ndcg_at_k": round(float(np.mean(nd)), 4) if nd else np.nan,
        "mae": round(mae, 4),
        "n": len(ev),
    }


def walk_forward_baselines(mart: pd.DataFrame) -> pd.DataFrame:
    """Score every baseline on the leakage-checked, **coverage-matched** walk-forward.

    All baselines are scored on the common evaluation set (rows post-warmup where
    every baseline is defined), so the comparison is not confounded by unequal
    history requirements. ``coverage`` reports each baseline's applicability over
    all post-warmup rows. Sorted by ``spearman_mean`` (primary) — the frozen benchmark.
    """
    features = build_baseline_features(mart)
    _assert_no_leakage(features)

    post = features[features["gw"] > WARMUP_GW]
    common = post[list(BASELINES)].notna().all(axis=1)          # rows where ALL baselines exist
    common_mask = pd.Series(False, index=features.index)
    common_mask.loc[post.index] = common.to_numpy()

    rows = []
    for col, label in BASELINES.items():
        coverage = float(post[col].notna().mean())
        rows.append({"baseline": label, **score_predictions(features, col, eval_mask=common_mask),
                     "coverage": round(coverage, 3)})
    return pd.DataFrame(rows).set_index("baseline").sort_values("spearman_mean", ascending=False)
