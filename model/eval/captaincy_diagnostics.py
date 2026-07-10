"""Door 1 - captaincy diagnostic: is the captaincy edge irreducible or fixable?

Phase 5 found a season-average (`base_season`) beats the points model at captaincy, with nothing
separable on one season. This asks *why*, to decide whether more modelling could ever help:

  Q1 concentration  - is captaincy won in a few GWs? (reducible regret spread; top-K share, Gini)
  Q2 oracle rank    - is the single best captain predictable? (hit@1/@3 vs chance)
  Q3 divergence     - when the model disagrees with base_season, does it WIN? (conditional win-rate)  [crux]
  Q4 discrimination - does ANY ex-ante signal separate the oracle from the field? (LOGO-CV AUC vs a
                      permutation-null detectability floor - the one-season power check)              [crux]

Pre-registered decision rule: IRREDUCIBLE if regret is concentrated AND AUC CI includes the null floor
AND divergent picks don't beat base_season; FIXABLE if AUC clears the floor OR divergent picks win;
CEILING-TILT otherwise. Consumes the Phase-5 captaincy panel; all discrimination features strictly lagged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from model.eval.decisions import AVAILABILITY_MIN_ROLL, _block_bootstrap_ci, build_captaincy_panel
from model.eval.walkforward import WARMUP_GW

# Strictly-lagged / pre-kickoff candidate signals for the oracle-discrimination model.
DISCRIMINATION_FEATURES = ["fdr_avg", "was_home", "xgi_roll5", "purchase_price", "ownership_count", "p90"]


def build_diagnostic_pool(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Phase-5 captaincy candidate pool (pool-free availability gate) with a per-GW ``is_oracle`` flag."""
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    for c in [*DISCRIMINATION_FEATURES, "minutes_roll3", "total_points", "full_pts", "base_season"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    pool = df[df["gw"] > WARMUP_GW].dropna(subset=["full_pts", "base_season", "total_points"])
    pool = pool[pool["minutes_roll3"] >= AVAILABILITY_MIN_ROLL].copy()
    pool["is_oracle"] = 0
    pool.loc[pool.groupby("gw")["total_points"].idxmax(), "is_oracle"] = 1
    return pool


def _gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def reducible_regret(pool: pd.DataFrame) -> pd.DataFrame:
    """Per-GW oracle vs base_season/model captain, and the concentration of the reducible regret.

    Returns a per-GW frame; ``.attrs`` carries ``top20_share`` and ``gini`` of the reducible regret
    (oracle - base_season pick). High concentration -> captaincy is a few-GW variance game.
    """
    rows = []
    for gw, g in pool.groupby("gw"):
        rows.append({
            "gw": gw, "oracle": float(g["total_points"].max()),
            "base": float(g.loc[g["base_season"].idxmax(), "total_points"]),
            "model": float(g.loc[g["full_pts"].idxmax(), "total_points"]),
        })
    out = pd.DataFrame(rows)
    out["reducible"] = out["oracle"] - out["base"]
    red = np.sort(out["reducible"].to_numpy())[::-1]
    topk = int(np.ceil(0.2 * len(red)))
    out.attrs["top20_share"] = round(float(red[:topk].sum() / red.sum()), 3) if red.sum() else float("nan")
    out.attrs["gini"] = round(_gini(out["reducible"].to_numpy()), 3)
    return out


def oracle_rank_hits(pool: pd.DataFrame, score_cols: tuple[str, ...] = (
        "base_season", "full_pts", "p90", "p_haul", "ownership_count")) -> pd.DataFrame:
    """hit@1 / hit@3: how often each strategy ranks the eventual oracle at the top of its list."""
    gws = pool["gw"].unique()
    chance1 = float(np.mean(1.0 / pool.groupby("gw").size()))
    rows = []
    for s in score_cols:
        if s not in pool.columns:
            continue
        h1 = h3 = 0
        for _, g in pool.groupby("gw"):
            rank = g[s].rank(ascending=False, method="min")[g["is_oracle"] == 1].min()
            h1 += rank <= 1
            h3 += rank <= 3
        rows.append({"strategy": s, "hit_at_1": round(h1 / len(gws), 3),
                     "hit_at_3": round(h3 / len(gws), 3), "chance_at_1": round(chance1, 3)})
    return pd.DataFrame(rows).set_index("strategy")


def divergence_winrate(pool: pd.DataFrame) -> dict:
    """When the model's captain != base_season's, does the model win? (conditional win-rate + block CI)."""
    diff = []
    for _, g in pool.groupby("gw"):
        bp = g.loc[g["base_season"].idxmax(), "player_id"]
        mp = g.loc[g["full_pts"].idxmax(), "player_id"]
        if bp != mp:
            diff.append(g.loc[g["full_pts"].idxmax(), "total_points"]
                        - g.loc[g["base_season"].idxmax(), "total_points"])
    diff = np.asarray(diff, dtype=float)
    n_gw = pool["gw"].nunique()
    lo, hi = _block_bootstrap_ci((diff > 0).astype(float)) if len(diff) >= 4 else (float("nan"), float("nan"))
    return {"n_divergent": len(diff), "n_gw": int(n_gw),
            "winrate": round(float((diff > 0).mean()), 3) if len(diff) else float("nan"),
            "winrate_ci": (lo, hi),
            "mean_pts_diff": round(float(diff.mean()), 3) if len(diff) else float("nan")}


def oracle_discrimination(pool: pd.DataFrame, features: tuple[str, ...] = tuple(DISCRIMINATION_FEATURES),
                          n_null: int = 500, seed: int = 0) -> dict:
    """Does any ex-ante signal separate the oracle from the field? (single AUCs + LOGO-CV AUC + power).

    Single-feature AUC for `P(is_oracle)`, plus a leave-one-GW-out logistic (out-of-sample) AUC, and a
    within-GW label-permutation null whose 95th percentile is the **minimum detectable AUC** at this n.
    """
    feats = [f for f in features if f in pool.columns]
    sub = pool.dropna(subset=[*feats, "is_oracle"]).copy()
    single = {f: round(float(roc_auc_score(sub["is_oracle"], sub[f])), 3) for f in feats
              if sub["is_oracle"].nunique() == 2}

    gws = sorted(sub["gw"].unique())
    oos = np.full(len(sub), np.nan)
    for gw in gws:
        tr = sub[sub["gw"] != gw]
        te = (sub["gw"] == gw).to_numpy()
        if tr["is_oracle"].nunique() < 2:
            continue
        mu, sd = tr[feats].mean(), tr[feats].std() + 1e-9
        m = LogisticRegression(max_iter=200).fit((tr[feats] - mu) / sd, tr["is_oracle"])
        oos[te] = m.predict_proba((sub.loc[te, feats] - mu) / sd)[:, 1]
    mask = ~np.isnan(oos)
    y = sub["is_oracle"].to_numpy()[mask]
    combined = round(float(roc_auc_score(y, oos[mask])), 3)

    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n_null):
        perm = sub.groupby("gw")["is_oracle"].transform(
            lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).to_numpy())
        null.append(roc_auc_score(perm.to_numpy()[mask], oos[mask]))
    min_detectable = round(float(np.percentile(null, 95)), 3)
    return {"single_auc": single, "combined_logo_auc": combined,
            "min_detectable_auc": min_detectable, "signal_detected": combined > min_detectable,
            "n_oracle": int(sub["is_oracle"].sum())}


def captaincy_diagnostic_report(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> dict:
    """Full Door-1 report: Q1 concentration, Q2 oracle-rank, Q3 divergence, Q4 discrimination + power."""
    pool = build_diagnostic_pool(mart, n_sims=n_sims, seed=seed)
    reg = reducible_regret(pool)
    return {
        "n_gw": int(pool["gw"].nunique()),
        "concentration": reg,
        "top20_share": reg.attrs["top20_share"], "gini": reg.attrs["gini"],
        "oracle_hits": oracle_rank_hits(pool),
        "divergence": divergence_winrate(pool),
        "discrimination": oracle_discrimination(pool, seed=seed),
    }
