"""The serve-agnostic decision backtest driver (ADR-012 §5; §6 as amended 2026-08-03).

Walk-forward over historical gameweeks: for each GW take the decision's picks — via an injected
``pick_fn``, so the driver never imports ``serve`` — and its baselines, score them against actual
outcomes, and aggregate to baseline-relative metrics with a block-bootstrap **paired CI** drawn from
``research.kernels``. (`model→kernels` is permitted — the `no_model_to_research_analysis` contract
exempts kernels — whereas `serve↛research` is exactly why this cannot live in ``serve``.)

The ``operational`` composition root binds the real ``serve`` ranker in as ``pick_fn``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from model.eval.decision.metrics import hit_rate, regret, return_variance
from model.eval.decision.spec import EvalSpec
from research.kernels.evaluation import assert_no_future_leakage, downside_rate
from research.kernels.inferential.resampling import block_bootstrap_ci

# (features, gw) -> ranked candidate frame carrying 'player_id' (the injected decision ranker).
PickFn = Callable[[pd.DataFrame, int], pd.DataFrame]


@dataclass(frozen=True)
class BacktestResult:
    """Baseline-relative backtest outcome for one decision."""

    name: str
    gw_count: int
    heuristic_avg_return: float | None
    baselines: dict[str, float | None]  # label -> mean baseline return
    paired_ci: dict[str, tuple[float, float]]  # label -> block-bootstrap CI of (heuristic - baseline)
    family_metrics: dict[str, float | None]  # metric_family-specific summary (hit rate, regret, ...)
    detail: pd.DataFrame


def run_backtest(spec: EvalSpec, features: pd.DataFrame, eval_gws: list[int], *, pick_fn: PickFn) -> BacktestResult:
    """Backtest ``spec`` over ``eval_gws``, ranking with the injected ``pick_fn``."""
    if spec.metric_family == "top1":
        return _run_top1(spec, features, eval_gws, pick_fn)
    if spec.metric_family == "portfolio":
        return _run_portfolio(spec, features, eval_gws, pick_fn)
    raise NotImplementedError(f"metric_family {spec.metric_family!r} is not a known family")


def _run_top1(spec: EvalSpec, features: pd.DataFrame, eval_gws: list[int], pick_fn: PickFn) -> BacktestResult:
    """Single-pick family (captaincy): grade the top-1 pick vs baselines and the actual best scorer."""
    available = {int(g) for g in features["gw"].unique()}
    labels = [label for label, _ in spec.baselines]
    rows: list[dict] = []

    for gw in eval_gws:
        if gw not in available or gw + spec.max_future_offset not in available:
            continue
        assert_no_future_leakage(features, gw)
        outcomes = features[features["gw"] == gw][["player_id", "total_points"]].dropna(subset=["total_points"])
        if outcomes.empty:
            continue
        heuristic = pick_fn(features, gw)
        if heuristic.empty:
            continue

        top1_id = int(heuristic.iloc[0]["player_id"])
        top3_ids = {int(x) for x in heuristic.head(3)["player_id"]}
        top1_ret = spec.return_fn([top1_id], features, gw)
        top1_pts = float(top1_ret.loc[top1_id]) if top1_id in top1_ret.index else None

        best = outcomes.loc[outcomes["total_points"].idxmax()]
        best_id, best_pts = int(best["player_id"]), float(best["total_points"])

        row: dict = {
            "gw": gw,
            "heuristic_top1_id": top1_id,
            "heuristic_top1_return": top1_pts,
            "actual_best_id": best_id,
            "actual_best_return": best_pts,
            "top1_hit": hit_rate([top1_id], best_id),
            "top3_hit": hit_rate(top3_ids, best_id),
            "regret": regret(best_pts, top1_pts),
        }
        for label, baseline in spec.baselines:
            picks = baseline(features, gw, spec.n)
            if picks.empty:
                row[f"baseline_{label}_return"] = None
                continue
            bid = int(picks.iloc[0]["player_id"])
            bret = spec.return_fn([bid], features, gw)
            row[f"baseline_{label}_return"] = float(bret.loc[bid]) if bid in bret.index else None
        rows.append(row)

    if not rows:
        return BacktestResult(spec.name, 0, None, {lb: None for lb in labels}, {}, {}, pd.DataFrame())

    df = pd.DataFrame(rows)
    heuristic = df["heuristic_top1_return"].dropna()

    baselines: dict[str, float | None] = {}
    paired_ci: dict[str, tuple[float, float]] = {}
    for label in labels:
        col = df[f"baseline_{label}_return"]
        baselines[label] = float(col.dropna().mean()) if not col.dropna().empty else None
        diff = (df["heuristic_top1_return"] - col).dropna().to_numpy()
        paired_ci[label] = block_bootstrap_ci(diff)

    valid_regret = df["regret"].dropna()
    family_metrics: dict[str, float | None] = {
        "top1_hit_rate": float(df["top1_hit"].mean()),
        "top3_hit_rate": float(df["top3_hit"].mean()),
        "mean_regret": float(valid_regret.mean()) if not valid_regret.empty else None,
        "heuristic_variance": return_variance(heuristic),
        "heuristic_downside_rate": downside_rate(heuristic),
    }
    return BacktestResult(
        name=spec.name,
        gw_count=len(df),
        heuristic_avg_return=float(heuristic.mean()) if not heuristic.empty else None,
        baselines=baselines,
        paired_ci=paired_ci,
        family_metrics=family_metrics,
        detail=df,
    )


def _run_portfolio(spec: EvalSpec, features: pd.DataFrame, eval_gws: list[int], pick_fn: PickFn) -> BacktestResult:
    """Top-n shortlist family (value, transfers): grade the mean return of the top-n picks over the window."""
    available = {int(g) for g in features["gw"].unique()}
    labels = [label for label, _ in spec.baselines]
    rows: list[dict] = []

    for gw in eval_gws:
        if gw not in available or gw + spec.max_future_offset not in available:
            continue
        assert_no_future_leakage(features, gw)
        heuristic = pick_fn(features, gw)
        if heuristic.empty:
            continue

        h_ids = [int(x) for x in heuristic["player_id"]]
        h_returns = spec.return_fn(h_ids, features, gw)
        row: dict = {
            "gw": gw,
            "heuristic_mean_return": float(h_returns.mean()) if not h_returns.empty else None,
            "heuristic_n": len(h_ids),
        }
        for label, baseline in spec.baselines:
            picks = baseline(features, gw, spec.n)
            b_ids = [int(x) for x in picks["player_id"]] if not picks.empty else []
            b_returns = spec.return_fn(b_ids, features, gw) if b_ids else pd.Series(dtype=float)
            row[f"baseline_{label}_return"] = float(b_returns.mean()) if not b_returns.empty else None
        rows.append(row)

    if not rows:
        return BacktestResult(spec.name, 0, None, {lb: None for lb in labels}, {}, {}, pd.DataFrame())

    df = pd.DataFrame(rows)
    h_means = df["heuristic_mean_return"].dropna()

    baselines: dict[str, float | None] = {}
    paired_ci: dict[str, tuple[float, float]] = {}
    for label in labels:
        col = df[f"baseline_{label}_return"]
        baselines[label] = float(col.dropna().mean()) if not col.dropna().empty else None
        diff = (df["heuristic_mean_return"] - col).dropna().to_numpy()
        paired_ci[label] = block_bootstrap_ci(diff)

    return BacktestResult(
        name=spec.name,
        gw_count=len(df),
        heuristic_avg_return=float(h_means.mean()) if not h_means.empty else None,
        baselines=baselines,
        paired_ci=paired_ci,
        family_metrics={"heuristic_variance": return_variance(h_means)},
        detail=df,
    )
