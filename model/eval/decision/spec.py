"""EvalSpec — how to evaluate a decision, and the registered eval specs (ADR-012 §5).

Serve-agnostic: the evaluator is handed the ranker as an injected ``pick_fn`` (see
``backtest.run_backtest``); nothing here imports ``serve``. An ``EvalSpec`` declares the small set that
varies across decisions — the outcome window (`return_fn`), the comparison baselines, whether the
decision is a single pick or a top-n shortlist (`metric_family`), and how far ahead the outcome reaches.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from model.eval.decision.baselines import baseline_fixture_only, baseline_highest_xgi, baseline_recent_points

# (player_ids, features, gw) -> actual returns per player; the fn owns its own outcome window.
ReturnFn = Callable[[list[int], pd.DataFrame, int], pd.Series]
# (features, gw, n) -> ranked frame carrying 'player_id'.
Baseline = Callable[..., pd.DataFrame]


@dataclass(frozen=True)
class EvalSpec:
    """How to evaluate one decision. The frozen fields are the measured axes of variation (ADR-012 §5)."""

    name: str
    return_fn: ReturnFn
    baselines: tuple[tuple[str, Baseline], ...]
    metric_family: str  # "top1" (single pick) | "portfolio" (top-n shortlist)
    max_future_offset: int  # skip a GW unless gw + offset is available (captain 0; transfers/value > 0)
    n: int = 20


def _points_at_gw(player_ids: list[int], features: pd.DataFrame, gw: int) -> pd.Series:
    """Actual points of the given players AT ``gw`` — captaincy's outcome is the decision GW itself."""
    at_gw = features[(features["gw"] == gw) & features["player_id"].isin(player_ids)]
    return at_gw.dropna(subset=["total_points"]).set_index("player_id")["total_points"]


def _cumulative_over(lookahead: int) -> ReturnFn:
    """Return-fn: cumulative points per player over ``gw+1 .. gw+lookahead`` (a transfer's forward hold)."""

    def _fn(player_ids: list[int], features: pd.DataFrame, gw: int) -> pd.Series:
        future_gws = list(range(gw + 1, gw + lookahead + 1))
        mask = features["gw"].isin(future_gws) & features["player_id"].isin(player_ids)
        future = features[mask].dropna(subset=["total_points"])
        if future.empty:
            return pd.Series(dtype=float)
        return future.groupby("player_id")["total_points"].sum()

    return _fn


def _per_cost_over(lookahead: int) -> ReturnFn:
    """Return-fn: cumulative points per £m (price at ``gw``) over ``gw+1 .. gw+lookahead`` (value's window)."""

    def _fn(player_ids: list[int], features: pd.DataFrame, gw: int) -> pd.Series:
        future_gws = list(range(gw + 1, gw + lookahead + 1))
        current_prices = features[features["gw"] == gw].set_index("player_id")["purchase_price"]
        mask = features["gw"].isin(future_gws) & features["player_id"].isin(player_ids)
        future_pts = features[mask].dropna(subset=["total_points"]).groupby("player_id")["total_points"].sum()
        if future_pts.empty:
            return pd.Series(dtype=float)
        prices = current_prices.reindex(future_pts.index)
        valid = prices[prices > 0]
        if valid.empty:
            return pd.Series(dtype=float)
        return future_pts.loc[valid.index] / valid

    return _fn


CAPTAIN_EVAL = EvalSpec(
    name="captain",
    return_fn=_points_at_gw,
    baselines=(("recent", baseline_recent_points), ("xgi", baseline_highest_xgi)),
    metric_family="top1",
    max_future_offset=0,
)

TRANSFERS_EVAL = EvalSpec(
    name="transfers",
    return_fn=_cumulative_over(3),
    baselines=(("recent", baseline_recent_points), ("fixture", baseline_fixture_only)),
    metric_family="portfolio",
    max_future_offset=3,
    n=10,
)

VALUE_EVAL = EvalSpec(
    name="value",
    return_fn=_per_cost_over(4),
    baselines=(("recent", baseline_recent_points), ("fixture", baseline_fixture_only)),
    metric_family="portfolio",
    max_future_offset=4,
    n=10,
)
