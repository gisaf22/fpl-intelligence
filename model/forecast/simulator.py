"""Phase 3.1 - Monte-Carlo points simulator on the closed points equation (Phase 3.0).

Samples each player-GW's components through the real FPL scoring rules to produce a full points
**distribution** - P(haul), captaincy ceiling (p90), downside (p10) - not just the mean. Consumes the
fitted per-GW parameters from :func:`model.forecast.points_model.walk_forward_points` (no re-fit):
``e_goals``/``e_assists``/``e_saves`` are Poisson means, ``p_cs`` gives the team goals-against mean via
``lambda_ga = -log(p_cs)``, ``p_dc``/``p60`` are Bernoulli probabilities, and the bonus proxy
coefficients (``bonus_intercept``/``bonus_slope``) map drawn returns to bonus.

Dependence (design 2026-07-09; grounded in the Track-2 diagnostics, distribution unverified):
  * **team goals-against is drawn ONCE per team-fixture and shared** across the team's players, so
    ``clean_sheet = 1{GA=0} & played>=60`` and ``conceded = -floor(GA/2)`` co-move (D-D). Exact for
    full-90 players, approximate for subs (on-pitch GA).
  * **DC is drawn independently** (D-A: DC _|_ GA given minutes).
  * **bonus co-varies via the drawn returns** (proxy per draw); its competitive residual is not sampled.

Gate = INTERNAL CORRECTNESS ONLY (reproducible; sim mean ~= analytic ``full_pts``; CS never co-occurs
with conceded>0). Distributional validation (PIT / haul-rate / CRPS) is Phase 4.

Scope limits: conditional on appearance (no ``P(play)`` blank / 0-minute tail - X1, Phase 5); single-
player marginals only (no team goals-for / attacking co-movement - Phase 5); goals _|_ assists within
player; rare events excluded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from domain.fpl_scoring import BPS_BONUS_FIRST, GK_SAVES_PER_POINT
from model.eval.walkforward import WARMUP_GW
from model.forecast.points_model import _CS_MULT, _GOAL_MULT, walk_forward_points

HAUL_THRESHOLD = 10
# ``p_dc`` is intentionally NOT required: GK have no DC term (NaN), handled as 0 downstream via the
# position gate - requiring it would drop every GK row from the simulation.
_REQUIRED = ["e_goals", "e_assists", "p_cs", "p60", "bonus_intercept", "bonus_slope"]


def _draw_team_ga(points: pd.DataFrame, n_sims: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Draw team goals-against ONCE per team-fixture (shared across the team's players).

    Returns ``(tf_index, ga_by_tf)`` where ``ga_by_tf`` is ``(n_team_fixtures, n_sims)`` and
    ``tf_index`` maps each row to its team-fixture. ``lambda_ga = -log(p_cs)`` (p_cs = P(GA=0)).
    """
    tf_key = points["team_id"].astype(str) + "_" + points["gw"].astype(str)
    tf_index, tf_uniques = pd.factorize(tf_key)
    # p_cs is constant within a team-fixture (broadcast); take the first per tf.
    first = points.groupby(tf_index)["p_cs"].first().reindex(range(len(tf_uniques)))
    lam = np.clip(-np.log(np.clip(first.to_numpy(dtype=float), 1e-6, 1.0)), 0.0, None)
    ga_by_tf = rng.poisson(lam[:, None], size=(len(tf_uniques), n_sims))
    return tf_index, ga_by_tf


def _simulate_rows(block: pd.DataFrame, ga: np.ndarray, n_sims: int,
                   rng: np.random.Generator) -> np.ndarray:
    """Sampled points ``(n_rows, n_sims)`` for a block of player-GW rows (``ga`` already indexed)."""
    n = len(block)
    pos = block["position"].to_numpy()
    gmult = block["position"].map(_GOAL_MULT).to_numpy(dtype=float)[:, None]
    cmult = block["position"].map(_CS_MULT).to_numpy(dtype=float)[:, None]
    is_gk = (pos == "GK")[:, None]
    has_conceded = np.isin(pos, ["GK", "DEF"])[:, None]
    has_dc = np.isin(pos, ["DEF", "MID", "FWD"])[:, None]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(block[name].to_numpy(dtype=float))[:, None]

    play60 = rng.random((n, n_sims)) < col("p60")
    goals = rng.poisson(col("e_goals"), size=(n, n_sims))
    assists = rng.poisson(col("e_assists"), size=(n, n_sims))
    saves = np.where(is_gk, rng.poisson(np.clip(col("e_saves"), 0, None), size=(n, n_sims)), 0)
    dc = (rng.random((n, n_sims)) < col("p_dc")) & has_dc

    cs = (ga == 0) & play60                                   # clean sheet needs GA=0 AND >=60'
    conceded = np.where(has_conceded, -(ga // 2), 0)
    saves_pts = np.where(is_gk, saves // GK_SAVES_PER_POINT, 0)
    dc_pts = np.where(dc, 2, 0)
    appearance = 1 + play60                                   # 1 (played) + 1 (>=60')

    returns_pts = gmult * goals + 3 * assists + cmult * cs + saves_pts
    bonus = np.clip(col("bonus_intercept") + col("bonus_slope") * returns_pts, 0.0, BPS_BONUS_FIRST)

    return (appearance + gmult * goals + 3 * assists + cmult * cs
            + conceded + dc_pts + saves_pts + bonus)


def simulate_points(points: pd.DataFrame, n_sims: int = 10000, seed: int = 0,
                    batch_rows: int = 400) -> pd.DataFrame:
    """Monte-Carlo the points distribution for each scored player-GW row of a points panel.

    ``points`` is a :func:`walk_forward_points` output. Team goals-against is drawn once per
    team-fixture (shared); other components per row. Rows are processed in blocks to bound memory,
    but the team-GA draws are shared across all blocks (drawn up front). Returns per-row summaries:
    ``sim_mean, sim_sd, p10, p50, p90, p_haul`` (P(points>=10)), alongside the analytic ``full_pts``.
    """
    df = points[points["gw"] > WARMUP_GW].dropna(subset=_REQUIRED).copy().reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=["player_id", "gw", "position", "sim_mean", "sim_sd",
                                     "p10", "p50", "p90", "p_haul", "full_pts"])
    rng = np.random.default_rng(seed)
    tf_index, ga_by_tf = _draw_team_ga(df, n_sims, rng)

    out = []
    for start in range(0, len(df), batch_rows):
        block = df.iloc[start:start + batch_rows]
        ga = ga_by_tf[tf_index[start:start + batch_rows]]
        pts = _simulate_rows(block, ga, n_sims, rng)
        q10, q50, q90 = np.percentile(pts, [10, 50, 90], axis=1)
        out.append(pd.DataFrame({
            "player_id": block["player_id"].to_numpy(), "gw": block["gw"].to_numpy(),
            "position": block["position"].to_numpy(),
            "sim_mean": pts.mean(axis=1), "sim_sd": pts.std(axis=1),
            "p10": q10, "p50": q50, "p90": q90,
            "p_haul": (pts >= HAUL_THRESHOLD).mean(axis=1),
            "full_pts": block["full_pts"].to_numpy(),
        }))
    return pd.concat(out, ignore_index=True)


def simulate_from_mart(mart: pd.DataFrame, n_sims: int = 10000, seed: int = 0) -> pd.DataFrame:
    """Convenience: run the full points model then simulate its distribution."""
    return simulate_points(walk_forward_points(mart), n_sims=n_sims, seed=seed)


def simulator_consistency(mart: pd.DataFrame, n_sims: int = 4000, seed: int = 0) -> dict:
    """Internal-correctness check: sim mean vs analytic ``full_pts`` (consistency, NOT a predictive gate).

    Returns ``{corr, mean_abs_diff, n}`` - the simulator should reproduce the composition's mean up to
    MC error (and small saves floor / bonus clip nonlinearities). Distributional quality is Phase 4.
    """
    sim = simulate_points(walk_forward_points(mart), n_sims=n_sims, seed=seed)
    sim = sim.dropna(subset=["full_pts", "sim_mean"])
    return {
        "corr": round(float(np.corrcoef(sim["sim_mean"], sim["full_pts"])[0, 1]), 4),
        "mean_abs_diff": round(float(np.abs(sim["sim_mean"] - sim["full_pts"]).mean()), 4),
        "n": len(sim),
    }
