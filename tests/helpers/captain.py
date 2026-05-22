"""Historical evaluation of the captain ranking heuristic.

Determines whether the captain composite heuristic (form + involvement +
fixture + minutes, statically weighted) produces better outcomes than
naive single-signal alternatives across historical gameweeks.

Temporal integrity: the intelligence layer already enforces lag-1 via the
state layer's shift(1) rolling windows. Features at GW N encode only GWs
1..N-1. The actual outcome (total_points at GW N) is used solely as a
post-hoc evaluation target — it plays no role in generating rankings.
"""

from __future__ import annotations

import pandas as pd

from tests.helpers.baselines import baseline_recent_points, baseline_highest_xgi
from tests.helpers.metrics import (
    downside_rate,
    hit_rate,
    regret,
    return_variance,
    top1_return,
)
from tests.helpers.windows import assert_no_future_leakage
from intelligence.captain import rank_captain_candidates


def evaluate_captain_heuristic(
    features: pd.DataFrame,
    gameweeks: list[int],
) -> dict:
    """Evaluate the captain heuristic across historical gameweeks.

    For each gameweek in the list:
    - Generates captain rankings using only pre-deadline features (lag-1 guaranteed)
    - Compares top-1 pick's actual return against two naive baselines
    - Records hit rate, regret, variance, and downside frequency

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain. Must include total_points
        (actual GW outcome) and all state rolling columns (points_roll3 etc.).
        Produced by get_state_features(get_curated_spine(db_path)).
    gameweeks:
        Ordered list of historical gameweeks to evaluate.

    Returns
    -------
    Dict containing:
    - gw_count: number of successfully evaluated gameweeks
    - heuristic_avg_return: mean actual points of heuristic's top-1 pick per GW
    - baseline_recent_avg_return: mean actual points of naive form baseline top-1
    - baseline_xgi_avg_return: mean actual points of naive xGI baseline top-1
    - top1_hit_rate: fraction where top-1 heuristic pick was actual highest scorer
    - top3_hit_rate: fraction where actual highest scorer appeared in heuristic top-3
    - mean_regret: mean opportunity cost (actual_best - heuristic_pick) per GW
    - heuristic_variance: std dev of heuristic top-1 returns across GWs
    - heuristic_downside_rate: fraction of GWs where top-1 returned < 4 points
    - detail: per-GW DataFrame with all intermediate values
    """
    rows = []

    for gw in gameweeks:
        if features[features["gw"] == gw].empty:
            continue
        assert_no_future_leakage(features, gw)

        gw_outcomes = (
            features[features["gw"] == gw][["player_id", "total_points"]]
            .dropna(subset=["total_points"])
        )
        if gw_outcomes.empty:
            continue

        try:
            heuristic = rank_captain_candidates(features, target_gw=gw, n=20)
        except Exception:
            continue
        if heuristic.empty:
            continue

        bl_recent = baseline_recent_points(features, target_gw=gw, n=20)
        bl_xgi = baseline_highest_xgi(features, target_gw=gw, n=20)

        top1_id = int(heuristic.iloc[0]["player_id"])
        top3_ids = {int(x) for x in heuristic.head(3)["player_id"]}

        top1_pts = top1_return(top1_id, gw_outcomes)
        bl_recent_id = int(bl_recent.iloc[0]["player_id"]) if not bl_recent.empty else None
        bl_xgi_id = int(bl_xgi.iloc[0]["player_id"]) if not bl_xgi.empty else None
        bl_recent_pts = top1_return(bl_recent_id, gw_outcomes) if bl_recent_id else None
        bl_xgi_pts = top1_return(bl_xgi_id, gw_outcomes) if bl_xgi_id else None

        best_row = gw_outcomes.loc[gw_outcomes["total_points"].idxmax()]
        actual_best_id = int(best_row["player_id"])
        actual_best_pts = float(best_row["total_points"])

        rows.append({
            "gw": gw,
            "heuristic_top1_id": top1_id,
            "heuristic_top1_return": top1_pts,
            "baseline_recent_return": bl_recent_pts,
            "baseline_xgi_return": bl_xgi_pts,
            "actual_best_id": actual_best_id,
            "actual_best_return": actual_best_pts,
            "top1_hit": hit_rate([top1_id], actual_best_id),
            "top3_hit": hit_rate(top3_ids, actual_best_id),
            "regret": regret(actual_best_pts, top1_pts),
        })

    if not rows:
        return {"gw_count": 0}

    df = pd.DataFrame(rows)
    h_returns = df["heuristic_top1_return"].dropna()
    bl_recent = df["baseline_recent_return"].dropna()
    bl_xgi = df["baseline_xgi_return"].dropna()
    valid_regret = df["regret"].dropna()

    return {
        "gw_count": len(df),
        "heuristic_avg_return": float(h_returns.mean()) if not h_returns.empty else None,
        "baseline_recent_avg_return": float(bl_recent.mean()) if not bl_recent.empty else None,
        "baseline_xgi_avg_return": float(bl_xgi.mean()) if not bl_xgi.empty else None,
        "top1_hit_rate": float(df["top1_hit"].mean()),
        "top3_hit_rate": float(df["top3_hit"].mean()),
        "mean_regret": float(valid_regret.mean()) if not valid_regret.empty else None,
        "heuristic_variance": return_variance(h_returns),
        "heuristic_downside_rate": downside_rate(h_returns),
        "detail": df,
    }
