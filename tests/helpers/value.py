"""Historical evaluation of the value player heuristic.

Evaluates whether the value composite heuristic (efficiency + form +
consistency, statically weighted) identifies players who subsequently
deliver higher per-cost returns than naive selection strategies.

Value evaluation is inherently a multi-GW question: a player identified as
"value" should sustain returns over several weeks, not just the next game.
The lookahead window captures this medium-term consistency requirement.

Temporal integrity: same lag-1 guarantee as captain and transfer evaluations.
"""

from __future__ import annotations

import pandas as pd

from tests.helpers.baselines import baseline_fixture_only, baseline_recent_points
from tests.helpers.metrics import return_variance, top1_return
from tests.helpers.windows import assert_no_future_leakage
from intelligence.value import rank_value_players


def _points_per_cost(
    player_ids: list[int],
    features: pd.DataFrame,
    from_gw: int,
    lookahead: int,
) -> pd.Series:
    """Mean points-per-£m per player over lookahead GWs after from_gw.

    Uses the purchase_price recorded at from_gw (pre-decision price) divided
    into cumulative total_points over the forward window. This mirrors how a
    manager evaluates value: cost is known now, returns accrue later.
    """
    future_gws = list(range(from_gw + 1, from_gw + lookahead + 1))
    current_prices = (
        features[features["gw"] == from_gw]
        .set_index("player_id")["purchase_price"]
    )
    mask = features["gw"].isin(future_gws) & features["player_id"].isin(player_ids)
    future_pts = (
        features[mask]
        .dropna(subset=["total_points"])
        .groupby("player_id")["total_points"]
        .sum()
    )
    if future_pts.empty:
        return pd.Series(dtype=float)
    prices = current_prices.reindex(future_pts.index)
    valid = prices[prices > 0]
    if valid.empty:
        return pd.Series(dtype=float)
    return future_pts.loc[valid.index] / valid


def evaluate_value_heuristic(
    features: pd.DataFrame,
    gameweeks: list[int],
    lookahead: int = 4,
    n: int = 10,
    max_price: float | None = None,
) -> dict:
    """Evaluate the value heuristic over historical gameweeks.

    For each eval GW: identify value players, then measure their points-per-£m
    over the subsequent lookahead window vs naive baselines.

    A value heuristic is useful if its picks deliver higher points-per-cost
    than players ranked by simple form or fixture difficulty alone.

    Parameters
    ----------
    features:
        Full DAL state output spanning eval GWs and lookahead window.
    gameweeks:
        Gameweeks at which value selections are evaluated.
    lookahead:
        GWs after eval_gw to measure returns (default 4 — medium term value).
    n:
        Top-n value picks to compare per strategy.
    max_price:
        Optional price ceiling passed through to rank_value_players.

    Returns
    -------
    Dict containing:
    - gw_count: evaluated GWs with sufficient future data
    - heuristic_avg_ppc: mean points-per-£m of heuristic top-n across eval GWs
    - baseline_recent_avg_ppc: same for naive form baseline
    - baseline_fixture_avg_ppc: same for fixture-only baseline
    - heuristic_variance: std dev of per-GW mean ppc
    - detail: per-GW DataFrame
    """
    all_gws = sorted(int(g) for g in features["gw"].unique())
    rows = []

    for gw in gameweeks:
        if features[features["gw"] == gw].empty:
            continue
        assert_no_future_leakage(features, gw)

        if gw + lookahead not in all_gws:
            continue

        kwargs: dict = {"target_gw": gw, "n": n}
        if max_price is not None:
            kwargs["max_price"] = max_price

        try:
            heuristic = rank_value_players(features, **kwargs)
        except Exception:
            continue
        if heuristic.empty:
            continue

        bl_recent = baseline_recent_points(features, target_gw=gw, n=n)
        bl_fixture = baseline_fixture_only(features, target_gw=gw, n=n)

        h_ids = [int(x) for x in heuristic["player_id"]]
        r_ids = [int(x) for x in bl_recent["player_id"]] if not bl_recent.empty else []
        f_ids = [int(x) for x in bl_fixture["player_id"]] if not bl_fixture.empty else []

        h_ppc = _points_per_cost(h_ids, features, gw, lookahead)
        r_ppc = _points_per_cost(r_ids, features, gw, lookahead)
        f_ppc = _points_per_cost(f_ids, features, gw, lookahead)

        rows.append({
            "gw": gw,
            "heuristic_mean_ppc": float(h_ppc.mean()) if not h_ppc.empty else None,
            "baseline_recent_mean_ppc": float(r_ppc.mean()) if not r_ppc.empty else None,
            "baseline_fixture_mean_ppc": float(f_ppc.mean()) if not f_ppc.empty else None,
        })

    if not rows:
        return {"gw_count": 0}

    df = pd.DataFrame(rows)
    h_ppc = df["heuristic_mean_ppc"].dropna()
    bl_r_ppc = df["baseline_recent_mean_ppc"].dropna()
    bl_f_ppc = df["baseline_fixture_mean_ppc"].dropna()

    return {
        "gw_count": len(df),
        "heuristic_avg_ppc": float(h_ppc.mean()) if not h_ppc.empty else None,
        "baseline_recent_avg_ppc": float(bl_r_ppc.mean()) if not bl_r_ppc.empty else None,
        "baseline_fixture_avg_ppc": float(bl_f_ppc.mean()) if not bl_f_ppc.empty else None,
        "heuristic_variance": return_variance(h_ppc),
        "detail": df,
    }
