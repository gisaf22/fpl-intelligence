"""Walk-forward scoring harness — Phase 0.2 of the predictive-layer plan.

The temporal-CV substrate every later model plugs into. Because the baseline
features are built from strictly-prior gameweeks (see ``baselines.py``), scoring
each row against its own target *is* an expanding-window walk-forward: the
prediction for gameweek ``t`` uses only gameweeks ``< t``. This module verifies
that guarantee and reports per-gameweek and pooled metrics.

Metrics (headline is ranking, because FPL is won by ranking players, not by
hitting exact scores — and the target is zero-inflated / right-skewed, which
makes squared-error metrics haul-dominated and misleading):

  * ``spearman_pos``   — mean within-(GW, position) rank correlation (the benchmark).
  * ``precision_at_k`` — per-position, tie-aware share of the actual top-K in the predicted top-K.
  * ``ndcg_at_k``      — per-position NDCG@K, points as gains (rewards ranking real scorers high).
  * ``mae``            — mean absolute error (secondary, robust point-accuracy sanity).

**Ranking is always within-position.** Squads fill under position quotas (2 GK /
5 DEF / 5 MID / 3 FWD), so ranking a keeper against a forward is meaningless.
Cross-position pooling is therefore abolished — there is no ``spearman_mean`` and no
cross-position top-K. ``walk_forward_by_position`` is the benchmark;
``walk_forward_baselines`` reports the within-position average as a one-line summary.

RMSE is deliberately omitted: on this skewed target it is dominated by rare hauls.
Proper scoring for the distributional models (Poisson deviance, CRPS) arrives in
Phase 4, not here.

Fair comparison (fix A): all baselines are scored on the **common evaluation set**
— rows where every baseline is defined — so differences are not a sampling
artifact of unequal history requirements. Each baseline's ``coverage`` (share of
post-warmup rows on which it is defined at all) is reported separately.

**Conditional on appearance.** The population is ``minutes > 0``, so every metric is
computed over players who *actually featured* that gameweek — availability is treated
as known. These numbers are therefore "ranking accuracy **given** the player played",
a valid sub-problem; jointly predicting who plays is the availability family's job and
is out of scope here. Do not read the benchmark as end-to-end forecast accuracy.
``precision_at_k`` is tie-aware on the actual side (the target is heavily tied — 36%
of returns are exactly 1 point).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.eval.baselines import BASELINES, build_baseline_features
from model.eval.metrics import grouped_spearman, ndcg_at_k, precision_at_k, spearman_with_ci

# Gameweeks below this are warmup (too little history for rolling/expanding windows).
WARMUP_GW = 3
# Minimum rows in a (gameweek, position) cell to compute a per-position rank corr
# (kept low because GK cells are small — ~one keeper per club/GW).
MIN_ROWS_PER_POS = 10
# Top-K shortlist size for precision@K / NDCG@K (~top 7% of a ~300-player GW —
# the decision-relevant "would this be on my shortlist" scale).
TOP_K = 20

_PLAYER_HISTORY_BASELINES = ("base_last", "base_roll3", "base_roll5", "base_season")


def _smoke_check_first_row_leakage(features: pd.DataFrame) -> None:
    """Guard: no player-history baseline may derive from a player's own current/future row."""
    first_rows = features.groupby("player_id").head(1)
    leaked = first_rows[list(_PLAYER_HISTORY_BASELINES)].notna().any(axis=1)
    if bool(leaked.any()):
        raise AssertionError("leakage: a player-history baseline is defined on a player's first appearance")


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
        Dict ``{spearman_pos, mae, n}`` — ``spearman_pos`` averages within-(GW, position)
        rank correlations (there is no cross-position ranking). Per-position precision /
        NDCG live in :func:`walk_forward_by_position`.
    """
    ev = features[features["gw"] > WARMUP_GW]
    if eval_mask is not None:
        ev = ev[eval_mask.loc[ev.index]]
    ev = ev.dropna(subset=[pred_col, target_col])
    if ev.empty:
        return {"spearman_pos": np.nan, "mae": np.nan, "n": 0}

    mae = float((ev[pred_col] - ev[target_col]).abs().mean())
    return {
        "spearman_pos": round(grouped_spearman(ev, pred_col, target_col, ["gw", "position"], MIN_ROWS_PER_POS), 4),
        "mae": round(mae, 4),
        "n": len(ev),
    }


def walk_forward_baselines(mart: pd.DataFrame) -> pd.DataFrame:
    """Within-position summary per baseline (one line each) on the coverage-matched set.

    A compact leaderboard: ``spearman_pos`` (within-position average) and ``mae`` over
    the common evaluation set, with ``coverage``. The per-position detail — and the
    actual bars Phase 1 must beat — is in :func:`walk_forward_by_position`. There is no
    cross-position ranking here. Sorted by ``spearman_pos``.
    """
    features = build_baseline_features(mart)
    _smoke_check_first_row_leakage(features)

    post = features[features["gw"] > WARMUP_GW]
    common = post[list(BASELINES)].notna().all(axis=1)          # rows where ALL baselines exist
    common_mask = pd.Series(False, index=features.index)
    common_mask.loc[post.index] = common.to_numpy()

    rows = []
    for col, label in BASELINES.items():
        coverage = float(post[col].notna().mean())
        rows.append({"baseline": label, **score_predictions(features, col, eval_mask=common_mask),
                     "coverage": round(coverage, 3)})
    return pd.DataFrame(rows).set_index("baseline").sort_values("spearman_pos", ascending=False)


# Squads fill under position quotas (2 GK / 5 DEF / 5 MID / 3 FWD), so the shortlist
# size that matters scales with the position's pool — not a flat top-20.
POSITIONS = ("GK", "DEF", "MID", "FWD")


def position_k(players_per_gw: int) -> int:
    """Decision-relevant shortlist size for a position: ~top quartile, in [3, TOP_K]."""
    return min(TOP_K, max(3, players_per_gw // 4))


# Back-compat: the shortlist-size helper was private before Phase 1 routed the gate loop
# through ``score_topk_by_position``. Kept so any straggler importing the old name still works.
_position_k = position_k


def score_topk_by_position(
    candidates: pd.DataFrame,
    models: dict[str, str],
    target_col: str = "total_points",
    *,
    min_n: int = MIN_ROWS_PER_POS,
    positions: tuple[str, ...] = POSITIONS,
    seed: int = 0,
    bootstrap: bool = True,
) -> pd.DataFrame:
    """The single per-(position, model) within-position ranking loop the whole harness shares.

    ``candidates`` is the post-warmup frame (NOT yet common-filtered); every model is scored on the
    rows where *all* ``models`` columns are defined, so a shrink-vs-mean comparison is not a sampling
    artifact. Per (position, model) it returns the within-position Spearman, a **block-bootstrap CI**
    (``ci_lo``/``ci_hi``, ``seed``) when ``bootstrap``, the tie-aware top-K ``precision_at_k`` /
    ``ndcg_at_k``, ``coverage`` (share of the position's candidate rows on which the model is defined),
    the position-scaled shortlist size ``k`` and ``n_gw``. ``walk_forward_by_position`` and the Phase-1
    estimator studies (``level_estimators``/``shrinkage``) all route through this so the loop -- and any
    future metric fix -- lives in one place. Rows are ordered by (position, Spearman desc).
    """
    cols = list(models)
    common = candidates.dropna(subset=cols)
    rows = []
    for pos in positions:
        sub_all = candidates[candidates["position"] == pos]
        sub = common[common["position"] == pos]
        if sub.empty:
            continue
        k = position_k(int(sub.groupby("gw").size().median()))
        for col, label in models.items():
            if bootstrap:
                est, (lo, hi) = spearman_with_ci(sub, col, target_col, ["gw"], min_n, seed=seed)
            else:
                est, (lo, hi) = grouped_spearman(sub, col, target_col, ["gw"], min_n), (np.nan, np.nan)
            pk, nd = [], []
            for _, g in sub.groupby("gw"):
                if len(g) < min_n or g[col].nunique() <= 1 or g[target_col].nunique() <= 1:
                    continue
                p, a = g[col].to_numpy(), g[target_col].to_numpy()
                pk.append(precision_at_k(p, a, k))
                nd.append(ndcg_at_k(p, a, k))
            rows.append({
                "position": pos, "model": label,
                "spearman": round(est, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                "precision_at_k": round(float(np.mean(pk)), 4) if pk else np.nan,
                "ndcg_at_k": round(float(np.mean(nd)), 4) if nd else np.nan,
                "coverage": round(float(sub_all[col].notna().mean()), 3) if len(sub_all) else np.nan,
                "k": k, "n_gw": int(sub["gw"].nunique()),
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["position"] = pd.Categorical(out["position"], categories=positions, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).reset_index(drop=True)


def walk_forward_by_position(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-(position, baseline) ranking on the common eval set — the decision-relevant view.

    Pooled ``spearman_pos`` masks large heterogeneity (GK ranks near chance; MID/FWD
    rank well), so Phase 1+ models must be judged against the *per-position* bars here.
    ``k`` is the position-scaled shortlist size (``precision_at_k`` uses it). Thin wrapper over
    :func:`score_topk_by_position` (CI skipped here to keep the Phase-0 leaderboard fast/columns
    stable); the per-position CI is what the Phase-1 estimator gates surface.

    Returns a frame indexed by (position, baseline) with spearman / precision_at_k /
    k / n_gw, positions ordered GK→DEF→MID→FWD and baselines by spearman within each.
    """
    features = build_baseline_features(mart)
    _smoke_check_first_row_leakage(features)
    post = features[features["gw"] > WARMUP_GW]
    scored = score_topk_by_position(post, BASELINES, bootstrap=False).rename(columns={"model": "baseline"})
    return scored.set_index(["position", "baseline"])[["spearman", "precision_at_k", "ndcg_at_k", "k", "n_gw"]]


_BASELINE_LABEL_TO_COL = {v: k for k, v in BASELINES.items()}


def best_baseline_per_position(mart: pd.DataFrame) -> dict[str, str]:
    """The strongest naive baseline COLUMN per position - the true bar a per-position gate should beat.

    ``base_season`` is the pooled/headline incumbent, but it is NOT the best naive baseline at every
    position: at GK the rolling-5 average out-ranks it. Gates that report a per-position incumbent
    should use this so, e.g., a GK model is judged against the real floor (rolling5), not base_season.
    """
    by_pos = walk_forward_by_position(mart).reset_index()
    out = {}
    for pos, g in by_pos.groupby("position", observed=True):
        top = g.sort_values("spearman", ascending=False).iloc[0]["baseline"]
        out[str(pos)] = _BASELINE_LABEL_TO_COL[top]
    return out
