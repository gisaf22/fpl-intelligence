"""Walk-forward scoring harness — Phase 0.2 of the predictive-layer plan.

The temporal-CV substrate every later model plugs into. Because the baseline
features are built from strictly-prior gameweeks (see ``baselines.py``), scoring
each row against its own target *is* an expanding-window walk-forward: the
prediction for gameweek ``t`` uses only gameweeks ``< t``. This module verifies
that guarantee and reports per-gameweek and season-aggregated (per-position) metrics.

Metrics (headline is ranking, because FPL is won by ranking players, not by
hitting exact scores — and the target is zero-inflated / right-skewed, which
makes squared-error metrics haul-dominated and misleading):

  * ``spearman``       — mean within-(GW, position) rank correlation (the benchmark).
  * ``precision_at_k`` — per-position, tie-aware share of the actual top-K in the predicted top-K.
  * ``ndcg_at_k``      — per-position NDCG@K, points as gains (rewards ranking real scorers high).

**Ranking is always within-position.** Squads fill under position quotas (2 GK /
5 DEF / 5 MID / 3 FWD), so ranking a keeper against a forward is meaningless.
Cross-position pooling is therefore abolished — there is no ``spearman_mean`` and no
cross-position top-K. ``walk_forward_by_position`` is *the* benchmark. Absolute-error
(MAE) is not a leaderboard metric — the target is too haul-noisy to compare models by
— but ``score_predictions`` still returns it per column for an ad-hoc accuracy sanity.

RMSE is deliberately omitted: on this skewed target it is dominated by rare hauls.
Proper scoring for the distributional models (Poisson deviance, CRPS) arrives in
Phase 4, not here.

Fair comparison (fix A): all models in a run are scored on the **common evaluation
set** — rows where every model is defined — so differences are not a sampling
artifact of unequal history requirements. Each model's ``coverage`` (share of
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
from model.eval.metrics import (
    block_bootstrap_ci,
    cell_spearman,
    grouped_spearman,
    has_rank_signal,
    ndcg_at_k,
    precision_at_k,
)

# Gameweeks below this are warmup (too little history for rolling/expanding windows).
WARMUP_GW = 3
# Minimum rows in a (gameweek, position) cell to compute a per-position rank corr
# (kept low because GK cells are small — ~one keeper per club/GW).
MIN_ROWS_PER_POS = 10
# Top-K shortlist size for precision@K / NDCG@K (~top 7% of a ~300-player GW —
# the decision-relevant "would this be on my shortlist" scale).
TOP_K = 20
# Squads fill under position quotas (2 GK / 5 DEF / 5 MID / 3 FWD), so the shortlist
# size that matters scales with the position's pool — not a flat top-20.
POSITIONS = ("GK", "DEF", "MID", "FWD")


def _smoke_check_first_row_leakage(features: pd.DataFrame) -> None:
    """Fast leakage canary — inspects ONLY each player's first appearance, not every row.

    All baselines are player-history (``shift(1)`` within a player), so the first row — the one row
    with zero legitimate history — is where any leak (missing shift, forward-looking window, or a
    window bleeding across the player boundary) is *forced* to surface as a spurious non-NaN. That
    makes row 1 a sufficient tripwire for these vectorized constructions, which fail uniformly (a
    window can't be right at row 1 yet wrong later). This is a cheap runtime guard, not a proof:
    exhaustive per-row correctness is covered by the baseline tests (e.g. ``base_last`` == prior
    points across all rows).
    """
    first_rows = features.groupby("player_id").head(1)
    leaked = first_rows[list(BASELINES)].notna().any(axis=1)
    if bool(leaked.any()):
        raise AssertionError("leakage: a baseline is defined on a player's first appearance")


def position_k(players_per_gw: int) -> int:
    """Decision-relevant shortlist size for a position: ~top quartile, in [3, TOP_K]."""
    return min(TOP_K, max(3, players_per_gw // 4))


def _gw_cell_metrics(g: pd.DataFrame, col: str, target_col: str, k: int) -> tuple[float, float, float]:
    """The three within-position ranking metrics for one gameweek cell, in a single pass.

    Returns ``(spearman, precision_at_k, ndcg_at_k)``. Caller guards rankability via ``has_rank_signal``.
    """
    p, a = g[col].to_numpy(), g[target_col].to_numpy()
    return cell_spearman(p, a), precision_at_k(p, a, k), ndcg_at_k(p, a, k)


def per_gw_scores(
    candidates: pd.DataFrame,
    models: dict[str, str],
    target_col: str = "total_points",
    *,
    min_n: int = MIN_ROWS_PER_POS,
    positions: tuple[str, ...] = POSITIONS,
) -> pd.DataFrame:
    """Long per-(position, model, gameweek) ranking metrics — the substrate both views project from.

    One row per (position, model, gw) that clears :func:`has_rank_signal`, carrying the within-position
    ``spearman``, ``precision_at_k`` and ``ndcg_at_k`` for that *single* gameweek plus the position's
    shortlist size ``k``. :func:`score_topk_by_position` aggregates this into the season summary;
    notebooks plot it directly as a per-gameweek time series. Models are scored on the **common set**
    (rows where every model is defined), so the comparison is not a coverage artifact. Rows are ordered
    (position, gw, model) — gw ascending within each (position, model), which the block-bootstrap CI relies on.
    """
    cols = list(models)
    common = candidates.dropna(subset=cols)
    recs = []
    for pos in positions:
        sub = common[common["position"] == pos]
        if sub.empty:
            continue
        k = position_k(int(sub.groupby("gw").size().median()))
        for gw, g in sub.groupby("gw"):                     # group ONCE per position
            for col, label in models.items():
                if not has_rank_signal(g, col, target_col, min_n):
                    continue
                sp, pk, nd = _gw_cell_metrics(g, col, target_col, k)
                recs.append((pos, label, int(gw), k, sp, pk, nd))
    return pd.DataFrame(recs, columns=["position", "model", "gw", "k",
                                       "spearman", "precision_at_k", "ndcg_at_k"])


def _summarise(
    long: pd.DataFrame, candidates: pd.DataFrame, models: dict[str, str], *,
    positions: tuple[str, ...], seed: int, bootstrap: bool,
) -> pd.DataFrame:
    """Aggregate the per-gw long frame into the season summary (one row per position, model).

    ``spearman``/``precision_at_k``/``ndcg_at_k`` are the mean over the per-gw values; ``ci_lo``/``ci_hi``
    are a block bootstrap over the per-gw Spearman series; ``coverage`` (from the full ``candidates``),
    ``k`` and ``n_gw`` (from the common set) are position/-model facts. A row is emitted for every
    (position, model) whose common set is non-empty, even when no gameweek was rankable (NaN metrics).
    """
    common = candidates.dropna(subset=list(models))
    rows = []
    for pos in positions:
        sub = common[common["position"] == pos]
        if sub.empty:
            continue
        sub_all = candidates[candidates["position"] == pos]
        k = position_k(int(sub.groupby("gw").size().median()))
        n_gw = int(sub["gw"].nunique())
        lp = long[long["position"] == pos]
        for col, label in models.items():
            lm = lp[lp["model"] == label]
            series = lm["spearman"].to_numpy()
            est = float(np.mean(series)) if len(series) else np.nan
            lo, hi = block_bootstrap_ci(series, seed=seed) if bootstrap else (np.nan, np.nan)
            rows.append({
                "position": pos, "model": label,
                "spearman": round(est, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                "precision_at_k": round(float(lm["precision_at_k"].mean()), 4) if len(lm) else np.nan,
                "ndcg_at_k": round(float(lm["ndcg_at_k"].mean()), 4) if len(lm) else np.nan,
                "coverage": round(float(sub_all[col].notna().mean()), 3) if len(sub_all) else np.nan,
                "k": k, "n_gw": n_gw,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["position"] = pd.Categorical(out["position"], categories=positions, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).reset_index(drop=True)


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
    """The single per-(position, model) within-position ranking summary the whole harness shares.

    Thin orchestrator: builds the per-gw substrate (:func:`per_gw_scores`) then reduces it
    (:func:`_summarise`). Per (position, model) it returns the within-position Spearman, a
    **block-bootstrap CI** (``ci_lo``/``ci_hi``, ``seed``) when ``bootstrap``, the tie-aware top-K
    ``precision_at_k`` / ``ndcg_at_k``, ``coverage`` (share of the position's candidate rows on which the
    model is defined), the position-scaled shortlist size ``k`` and ``n_gw``. ``walk_forward_by_position``
    and the Phase-1 estimator studies (``level_estimators``/``shrinkage``) all route through this. Rows
    are ordered by (position, Spearman desc). For the per-gameweek time series, call ``per_gw_scores``.
    """
    long = per_gw_scores(candidates, models, target_col, min_n=min_n, positions=positions)
    return _summarise(long, candidates, models, positions=positions, seed=seed, bootstrap=bootstrap)


def walk_forward_by_position(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-(position, baseline) ranking on the common eval set — the sole benchmark.

    Ranking quality is wildly heterogeneous across positions (GK ranks near chance; MID/FWD
    rank well), so there is no pooled number: Phase 1+ models are judged against the
    *per-position* bars here. ``k`` is the position-scaled shortlist size (``precision_at_k``
    uses it). Thin wrapper over
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


def score_predictions(
    features: pd.DataFrame, pred_col: str, target_col: str = "total_points",
) -> dict:
    """Ranking + accuracy metrics for one prediction column, averaged over post-warmup GWs.

    Standalone ad-hoc scorer (not part of the ``walk_forward_by_position`` benchmark path) — the one
    place absolute error is surfaced, for a single-column sanity check.

    Args:
        features:  output of ``build_baseline_features`` (may already be restricted to a
                   common evaluation set by the caller; the warmup filter below is then a no-op).
        pred_col:  the prediction column to score.
        target_col: the realised outcome column.

    Returns:
        Dict ``{spearman, mae, n}`` — ``spearman`` averages within-(GW, position)
        rank correlations (there is no cross-position ranking). Per-position precision /
        NDCG live in :func:`walk_forward_by_position`.
    """
    ev = features[features["gw"] > WARMUP_GW].dropna(subset=[pred_col, target_col])
    if ev.empty:
        return {"spearman": np.nan, "mae": np.nan, "n": 0}

    mae = float((ev[pred_col] - ev[target_col]).abs().mean())
    return {
        "spearman": round(grouped_spearman(ev, pred_col, target_col, ["gw", "position"], MIN_ROWS_PER_POS), 4),
        "mae": round(mae, 4),
        "n": len(ev),
    }
