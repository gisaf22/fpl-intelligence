"""Historical evaluation of the transfer target heuristic.

Evaluates whether recommended transfer targets subsequently deliver better
cumulative returns than naive alternatives over a lookahead window.

The evaluation horizon is forward-looking by design: transfer decisions are
made at GW N, and the benefit (or cost) accrues over the next K gameweeks.
This is different from captain evaluation, where the outcome is single-GW.

Temporal integrity: rankings at GW N use only features[gw == N], which
encodes pre-deadline rolling state. Future outcomes (GW N+1 .. N+K) are
used solely as evaluation targets, never as ranking inputs.
"""

from __future__ import annotations

import pandas as pd

from intelligence.transfers import rank_transfer_targets
from tests.helpers.baselines import baseline_fixture_only, baseline_recent_points
from tests.helpers.metrics import return_variance
from tests.helpers.windows import assert_no_future_leakage


def _cumulative_future_returns(
    player_ids: list[int],
    features: pd.DataFrame,
    from_gw: int,
    lookahead: int,
) -> pd.Series:
    """Cumulative total_points per player over lookahead GWs after from_gw.

    Returns a Series indexed by player_id. Players with no data in the window
    are excluded (not zero-filled — BGW absences are treated as missing).
    """
    future_gws = list(range(from_gw + 1, from_gw + lookahead + 1))
    mask = features["gw"].isin(future_gws) & features["player_id"].isin(player_ids)
    future = features[mask].dropna(subset=["total_points"])
    if future.empty:
        return pd.Series(dtype=float)
    return future.groupby("player_id")["total_points"].sum()


def evaluate_transfer_heuristic(
    features: pd.DataFrame,
    gameweeks: list[int],
    lookahead: int = 3,
    n: int = 10,
) -> dict:
    """Evaluate transfer heuristic by measuring post-decision cumulative returns.

    For each eval GW: rank top-n transfer targets, then compare their cumulative
    total_points over the next `lookahead` GWs against naive baselines.

    A transfer heuristic adds value if its recommended players accumulate more
    points than those from simpler strategies over the evaluation horizon.

    Parameters
    ----------
    features:
        Full DAL state output spanning eval GWs and the lookahead window.
    gameweeks:
        Gameweeks at which transfer decisions are simulated.
    lookahead:
        Number of GWs after eval_gw to measure cumulative returns.
        Chosen by caller based on squad rotation assumptions (typically 3-5).
    n:
        Number of top candidates from each strategy to evaluate.

    Returns
    -------
    Dict containing:
    - gw_count: evaluated GWs with sufficient future data
    - heuristic_avg_future_return: mean per-player cumulative return of heuristic top-n
    - baseline_recent_avg_future_return: same for naive form baseline
    - baseline_fixture_avg_future_return: same for fixture-only baseline
    - heuristic_variance: std dev of per-GW heuristic mean returns
    - detail: per-GW DataFrame
    """
    all_gws = sorted(int(g) for g in features["gw"].unique())
    rows = []

    for gw in gameweeks:
        if features[features["gw"] == gw].empty:
            continue
        assert_no_future_leakage(features, gw)

        required_future_gw = gw + lookahead
        if required_future_gw not in all_gws:
            continue

        try:
            heuristic = rank_transfer_targets(features, target_gw=gw, n=n)
        except Exception:
            continue
        if heuristic.empty:
            continue

        bl_recent = baseline_recent_points(features, target_gw=gw, n=n)
        bl_fixture = baseline_fixture_only(features, target_gw=gw, n=n)

        h_ids = [int(x) for x in heuristic["player_id"]]
        r_ids = [int(x) for x in bl_recent["player_id"]] if not bl_recent.empty else []
        f_ids = [int(x) for x in bl_fixture["player_id"]] if not bl_fixture.empty else []

        h_future = _cumulative_future_returns(h_ids, features, gw, lookahead)
        r_future = _cumulative_future_returns(r_ids, features, gw, lookahead)
        f_future = _cumulative_future_returns(f_ids, features, gw, lookahead)

        rows.append(
            {
                "gw": gw,
                "heuristic_mean_return": float(h_future.mean()) if not h_future.empty else None,
                "baseline_recent_mean_return": float(r_future.mean()) if not r_future.empty else None,
                "baseline_fixture_mean_return": float(f_future.mean()) if not f_future.empty else None,
                "heuristic_n": len(h_ids),
            }
        )

    if not rows:
        return {"gw_count": 0}

    df = pd.DataFrame(rows)
    h_means = df["heuristic_mean_return"].dropna()
    bl_r_means = df["baseline_recent_mean_return"].dropna()
    bl_f_means = df["baseline_fixture_mean_return"].dropna()

    return {
        "gw_count": len(df),
        "heuristic_avg_future_return": float(h_means.mean()) if not h_means.empty else None,
        "baseline_recent_avg_future_return": float(bl_r_means.mean()) if not bl_r_means.empty else None,
        "baseline_fixture_avg_future_return": float(bl_f_means.mean()) if not bl_f_means.empty else None,
        "heuristic_variance": return_variance(h_means),
        "detail": df,
    }
