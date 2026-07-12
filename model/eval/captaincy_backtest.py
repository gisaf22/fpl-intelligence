"""Phase 5 - decision evaluation: does the calibrated model help you pick a CAPTAIN?

The ultimate test of the stack: not "is the model accurate" but "does it lead to better decisions,
with honest error bars." Evaluates captaincy (one pick per GW) - the clean single-player decision
where the distribution should matter (ceiling, not just mean).

Strategies (each picks argmax per GW over the candidate universe, scored by realized points, blanks=0
so rotation is priced): template (ownership), base_season (expanding mean incl blanks), model_mean
(``full_pts``), model_mean x P(play) (rotation-adjusted), ceiling (``p90`` and recalibrated ``p_haul``).

Universe (two views): **pool-free** = a model-agnostic lagged-minutes availability gate (primary, no
arbitrary pool); **ownership top-N** (secondary). Reads per strategy: mean pts/GW + **block-bootstrap CI**
(A5.1 - one season is thin and GWs autocorrelate), head-to-head win rate vs template, and regret vs the
oracle best captain. `P(play)` (X1) is built here from lagged minutes/starts (no injury news - a
limitation vs real managers).

Ex-ante scoring needs predictions for potential blanks, so this uses
``walk_forward_points(mart, predict_all=True)``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from model.eval.metrics import block_bootstrap_ci
from model.eval.walkforward import WARMUP_GW
from model.forecast.points_model import _lag_roll, walk_forward_points
from model.forecast.simulator import simulate_points

P_PLAY_FEATURES = ["minutes_roll3", "minutes_roll5", "starts_roll3"]
AVAILABILITY_MIN_ROLL = 45.0          # pool-free gate: averaged >= 45 min over the last 3 (lagged)
MIN_PPLAY_TRAIN = 200
_STRATEGIES = {
    "template": "ownership_count",
    "base_season": "base_season",
    "model_mean": "full_pts",
    "model_mean_x_pplay": "model_pplay",
    "ceiling_p90": "p90",
    "ceiling_phaul": "p_haul",
}


def _p_play(df: pd.DataFrame) -> np.ndarray:
    """Walk-forward P(minutes>0) from lagged minutes/starts (logistic). No injury news - flagged."""
    df = df.copy()
    df["played"] = (pd.to_numeric(df["minutes"], errors="coerce") > 0).astype(float)
    out = np.full(len(df), np.nan)
    for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
        tr = df[df["gw"] < t].dropna(subset=[*P_PLAY_FEATURES, "played"])
        te = (df["gw"] == t).to_numpy()
        if len(tr) < MIN_PPLAY_TRAIN or tr["played"].nunique() < 2:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                x = sm.add_constant(tr[P_PLAY_FEATURES].to_numpy(float), has_constant="add")
                res = sm.GLM(tr["played"].to_numpy(float), x, family=sm.families.Binomial()).fit()
                xte = sm.add_constant(df.loc[te, P_PLAY_FEATURES].fillna(0).to_numpy(float), has_constant="add")
                out[te] = res.predict(xte)
            except Exception:
                continue
    return out


def build_captaincy_panel(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Per player-GW captaincy inputs: strategy scores + realized points, on the full ex-ante universe."""
    pts = walk_forward_points(mart, predict_all=True)
    sim = simulate_points(pts, n_sims=n_sims, seed=seed)[["player_id", "gw", "p90", "p_haul"]]
    df = pts.merge(sim, on=["player_id", "gw"], how="left")
    for c in ["minutes", "minutes_roll3", "minutes_roll5", "ownership_count", "total_points"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "starts_roll3" not in df.columns:
        df["starts_roll3"] = _lag_roll(df.sort_values(["player_id", "gw"]), "player_id", "starts", 3)
    df["p_play"] = _p_play(df)
    df["model_pplay"] = df["full_pts"] * df["p_play"]
    return df


def _ci3(values: np.ndarray) -> tuple[float, float]:
    """Block-bootstrap CI (shared ``metrics.block_bootstrap_ci``) rounded to 3dp - preserves the prior
    displayed precision now that the raw helper returns unrounded floats."""
    lo, hi = block_bootstrap_ci(values)
    return (round(lo, 3), round(hi, 3))


def _pick_series(pool: pd.DataFrame) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Per-GW realized points of each strategy's captain pick, and the oracle best, over a candidate pool."""
    per_gw: dict[str, list[float]] = {s: [] for s in _STRATEGIES}
    oracle = []
    for _, g in pool.groupby("gw"):
        if len(g) < 3:
            continue
        oracle.append(float(g["total_points"].max()))
        for s, col in _STRATEGIES.items():
            gg = g.dropna(subset=[col])
            per_gw[s].append(float(gg.loc[gg[col].idxmax(), "total_points"]) if len(gg) else np.nan)
    return {s: np.array(v, dtype=float) for s, v in per_gw.items()}, np.array(oracle, dtype=float)


def captaincy_backtest(mart: pd.DataFrame, pool: str = "free", n_top: int = 50,
                       n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Captaincy strategy comparison over the chosen universe, with block-bootstrap CIs.

    ``pool='free'`` = lagged-minutes availability gate (model-agnostic, primary); ``pool='ownership'``
    = top-``n_top`` owned within that gate (secondary). Returns per-strategy mean pts/GW, block CI,
    head-to-head win rate vs template, and regret vs the oracle.
    """
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    ev = df[(df["gw"] > WARMUP_GW)].dropna(
        subset=["full_pts", "p90", "p_haul", "ownership_count", "base_season", "total_points"])
    gate = ev[ev["minutes_roll3"] >= AVAILABILITY_MIN_ROLL]
    if pool == "ownership":
        gate = gate.sort_values("ownership_count", ascending=False).groupby("gw").head(n_top)

    series, oracle = _pick_series(gate)
    templ = series["template"]
    oracle_mean = float(np.nanmean(oracle))
    rows = []
    for s, v in series.items():
        finite = v[~np.isnan(v)]
        lo, hi = _ci3(finite)
        mean_v = round(float(finite.mean()), 3) if len(finite) else float("nan")
        rows.append({
            "strategy": s, "mean_pts_gw": mean_v,
            "ci_lo": lo, "ci_hi": hi,
            "winrate_vs_template": round(float(np.nanmean(v > templ)), 3),
            "regret": round(oracle_mean - finite.mean(), 3) if len(finite) else float("nan"),
        })
    out = pd.DataFrame(rows).set_index("strategy")
    out.attrs["oracle_mean"] = round(float(np.nanmean(oracle)), 3)
    out.attrs["n_gw"] = len(oracle)
    return out
