"""Pre-Phase-2 validation sprint — reproduces the three must-fix checks that open Phase 2.

Run: ``python -m model.eval.prephase2_validation``. Reads the live mart. Prints the three
tables frozen in ``docs/studies/results/predictive-prephase2-validation.md``:

  X2  — is D1's Gaussian-LMM ICC robust to dropping normality? (distribution-free bootstrap
        of the SS between-share, player-clustered).
  X6  — does lagged xG beat lagged goals at predicting next-GW goals? (within-position Spearman).
  A2.2 — how much of the points are deferred by the component map? (bonus / GK-saves share).

Population matches Phase 0/1: ``minutes > 0``, DGW excluded, per position.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from dal.pipeline import load as load_mart
from research.kernels.descriptive.variance_components import decompose_variance

POSITIONS = ["GK", "DEF", "MID", "FWD"]
# Frozen Gaussian-LMM ICCs from D1 (predictive-phase1-icc-shrinkage.md) for side-by-side.
_D1_ICC = {"GK": (0.000, 0.000, 0.027), "DEF": (0.056, 0.000, 0.082),
           "MID": (0.101, 0.070, 0.122), "FWD": (0.097, 0.000, 0.143)}


def _population(mart: pd.DataFrame) -> pd.DataFrame:
    return mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].sort_values(["player_id", "gw"]).copy()


def x2_between_share_bootstrap(sub: pd.DataFrame, n_boot: int = 3000, seed: int = 7, min_app: int = 10):
    """Distribution-free player-clustered bootstrap CI of the SS between-share (no normality assumed).

    Vectorised via per-player sufficient stats: n_i, s_i=sum(x), q_i=sum(x^2). SS_within_i = q_i - s_i^2/n_i.
    """
    g = sub.groupby("player_id")["total_points"]
    n = g.size().to_numpy(float)
    s = g.sum().to_numpy(float)
    q = g.apply(lambda x: float((x * x).sum())).to_numpy(float)
    keep = n >= min_app
    n, s, q = n[keep], s[keep], q[keep]
    p = len(n)
    rng = np.random.default_rng(seed)
    reps = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, p, p)
        big_n, big_s, big_q = n[idx].sum(), s[idx].sum(), q[idx].sum()
        grand = big_s / big_n
        sst = big_q - big_n * grand * grand
        ssw = (q[idx] - s[idx] ** 2 / n[idx]).sum()
        reps[b] = (sst - ssw) / sst if sst > 0 else np.nan
    return np.nanpercentile(reps, [2.5, 50, 97.5])


def _wp_spearman(df: pd.DataFrame, col: str, target: str, min_n: int = 10) -> float:
    rs = []
    for _, gg in df.groupby("gw"):
        if len(gg) < min_n or gg[col].nunique() <= 1 or gg[target].nunique() <= 1:
            continue
        rs.append(spearmanr(gg[col], gg[target]).correlation)
    return float(np.nanmean(rs)) if rs else float("nan")


def run() -> None:
    pop = _population(load_mart().mart)

    print("X2 — distribution-free SS between-share (player-clustered bootstrap) vs Gaussian-LMM ICC:")
    print(f"{'pos':4}{'SS_point':>10}{'boot_lo':>9}{'boot_med':>10}{'boot_hi':>9}   D1 ICC [CI]")
    for pos in POSITIONS:
        sub = pop[pop["position"] == pos]
        pt = decompose_variance(sub)["pct_between"] / 100.0
        lo, med, hi = x2_between_share_bootstrap(sub)
        g = _D1_ICC[pos]
        print(f"{pos:4}{pt:10.3f}{lo:9.3f}{med:10.3f}{hi:9.3f}   {g[0]:.3f} [{g[1]:.3f},{g[2]:.3f}]")

    g = pop.groupby("player_id")
    pop["xg_prior"] = g["xg"].transform(lambda s: s.expanding().mean().shift(1))
    pop["goals_prior"] = g["goals_scored"].transform(lambda s: s.expanding().mean().shift(1))
    ev = pop[pop["gw"] > 3].dropna(subset=["xg_prior", "goals_prior"])
    print("\nX6 — predicting next-GW goals_scored, within-position Spearman (lagged predictor):")
    print(f"{'pos':4}{'xG_prior':>10}{'goals_prior':>13}{'delta':>9}  winner")
    for pos in ["DEF", "MID", "FWD"]:
        sub = ev[ev["position"] == pos]
        rx = _wp_spearman(sub, "xg_prior", "goals_scored")
        rg = _wp_spearman(sub, "goals_prior", "goals_scored")
        print(f"{pos:4}{rx:10.3f}{rg:13.3f}{rx - rg:+9.3f}  {'xG' if rx > rg else 'goals'}")

    print("\nA2.2 — deferred-points share (bonus, and GK saves):")
    print(f"{'pos':4}{'Sum_pts':>10}{'bonus%':>9}{'GKsaves%':>10}")
    for pos in POSITIONS:
        sub = pop[pop["position"] == pos]
        tp = sub["total_points"].sum()
        bonus_pct = 100 * sub["bonus"].sum() / tp
        saves_pct = 100 * float(np.floor(sub["saves"].fillna(0) / 3).sum()) / tp if pos == "GK" else 0.0
        print(f"{pos:4}{tp:10.0f}{bonus_pct:9.1f}{saves_pct:10.1f}")


if __name__ == "__main__":
    run()
