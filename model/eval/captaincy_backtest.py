"""Phase 5 - decision evaluation: does the calibrated model help you pick a CAPTAIN?

The ultimate test of the stack: not "is the model accurate" but "does it lead to better decisions,
with honest error bars." Evaluates captaincy (one pick per GW) - the clean single-player decision
where the distribution should matter (ceiling, not just mean).

Strategies (each picks argmax per GW over the candidate universe, scored by realized points, blanks=0
so rotation is priced): template (ownership), base_season (expanding mean incl blanks), model_mean
(compose ``e_points``, the conditional mean), model_mean x P(play) (compose ``e_points_uncond``,
rotation-adjusted), ceiling (``p90`` and recalibrated ``p_haul``).

Universe (two views): **pool-free** = a model-agnostic lagged-minutes availability gate (primary, no
arbitrary pool); **ownership top-N** (secondary). Reads per strategy: mean pts/GW + **block-bootstrap CI**
(A5.1 - one season is thin and GWs autocorrelate), head-to-head win rate vs template, and regret vs the
oracle best captain.

Ex-ante scoring needs predictions for potential blanks, so this consumes the blank-inclusive compose
surface: ``compose_points(mart, keep_all=True)`` (E[points | played], ``base_season``, ``p_play``, and the
unconditional ``e_points_uncond`` = P(play) x E[points | played]) plus the conditional Monte-Carlo ceiling
from ``simulate_points(compose_parameters(mart, keep_all=True))``. The per-position P(play) term (X1) lives
in ``model.terms.p_play`` (lagged minutes/starts, no injury news - a limitation vs real managers).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.compose import compose_parameters, compose_points
from model.eval.metrics import block_bootstrap_ci
from model.eval.walkforward import WARMUP_GW
from model.simulate import simulate_points

AVAILABILITY_MIN_ROLL = 45.0          # pool-free gate: averaged >= 45 min over the last 3 (lagged)
# Raw mart signals carried onto the compose panel for the strategies (ownership/availability/realized) AND
# the Door-1 discrimination diagnostic (fdr/home/form/price). Present-subset: a thin fixture may lack some.
_RAW_CARRY_COLS = ["ownership_count", "total_points", "minutes_roll3",
                   "fdr_avg", "was_home", "xgi_roll5", "purchase_price"]
_STRATEGIES = {
    "template": "ownership_count",
    "base_season": "base_season",
    "model_mean": "e_points",
    "model_mean_x_pplay": "e_points_uncond",
    "ceiling_p90": "p90",
    "ceiling_phaul": "p_haul",
}


def build_captaincy_panel(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Per player-GW captaincy inputs: strategy scores + realized points, on the full ex-ante universe.

    Consumes compose directly (spec X1): ``compose_points(keep_all=True)`` gives the conditional mean
    ``e_points``, ``base_season``, ``p_play``, and the unconditional ``e_points_uncond``; the ceiling
    (``p90``/``p_haul``) comes from the conditional Monte-Carlo simulator. The mart's raw decision inputs
    (ownership, realized points, the availability-gate roll) are merged back on by (player_id, gw)."""
    pts = compose_points(mart, keep_all=True)
    params = compose_parameters(mart, keep_all=True)
    sim = simulate_points(params, n_sims=n_sims, seed=seed)[["player_id", "gw", "p90", "p_haul"]]
    df = pts.merge(sim, on=["player_id", "gw"], how="left")
    present = [c for c in _RAW_CARRY_COLS if c in mart.columns]
    raw = mart[~mart["is_dgw"].astype(bool)][["player_id", "gw", *present]].copy()
    for c in present:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    return df.merge(raw.drop_duplicates(["player_id", "gw"]), on=["player_id", "gw"], how="left")


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
        subset=["e_points", "p90", "p_haul", "ownership_count", "base_season", "total_points"])
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
