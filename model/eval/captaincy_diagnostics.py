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

from model.eval.captaincy_backtest import AVAILABILITY_MIN_ROLL, _ci3, build_captaincy_panel
from model.eval.walkforward import WARMUP_GW

# Strictly-lagged / pre-kickoff candidate signals for the oracle-discrimination model.
DISCRIMINATION_FEATURES = ["fdr_avg", "was_home", "xgi_roll5", "purchase_price", "ownership_count", "p90"]


def build_diagnostic_pool(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Phase-5 captaincy candidate pool (pool-free availability gate) with a per-GW ``is_oracle`` flag."""
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    for c in [*DISCRIMINATION_FEATURES, "minutes_roll3", "total_points", "e_points", "base_season"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    pool = df[df["gw"] > WARMUP_GW].dropna(subset=["e_points", "base_season", "total_points"])
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
        rows.append(
            {
                "gw": gw,
                "oracle": float(g["total_points"].max()),
                "base": float(g.loc[g["base_season"].idxmax(), "total_points"]),
                "model": float(g.loc[g["e_points"].idxmax(), "total_points"]),
            }
        )
    out = pd.DataFrame(rows)
    out["reducible"] = out["oracle"] - out["base"]
    red = np.sort(out["reducible"].to_numpy())[::-1]
    topk = int(np.ceil(0.2 * len(red)))
    out.attrs["top20_share"] = round(float(red[:topk].sum() / red.sum()), 3) if red.sum() else float("nan")
    out.attrs["gini"] = round(_gini(out["reducible"].to_numpy()), 3)
    return out


def oracle_rank_hits(
    pool: pd.DataFrame, score_cols: tuple[str, ...] = ("base_season", "e_points", "p90", "p_haul", "ownership_count")
) -> pd.DataFrame:
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
        rows.append(
            {
                "strategy": s,
                "hit_at_1": round(h1 / len(gws), 3),
                "hit_at_3": round(h3 / len(gws), 3),
                "chance_at_1": round(chance1, 3),
            }
        )
    return pd.DataFrame(rows).set_index("strategy")


def divergence_winrate(pool: pd.DataFrame, baseline_col: str = "base_season", challenger_col: str = "e_points") -> dict:
    """When ``challenger_col``'s captain != ``baseline_col``'s, does the challenger WIN?

    Q3, the diagnostic's crux, generalized to any pair of score columns. The default pair
    (``base_season`` vs ``e_points``) reproduces the frozen Phase-5 numbers; the ceiling columns
    (``p90``/``p_haul``) are the strategies that actually beat template in the Phase-5 backtest, so
    testing the crux against them is what licenses (or refutes) an 'irreducible' verdict for them.

    Both a **win-rate CI** (fraction of divergent GWs the challenger wins) and a **paired mean-delta
    CI** (the points swing itself) come from the shared block bootstrap, matching the Phase-5 backtest.
    Caveat: divergent GWs are non-contiguous, so a 'block' of 4 is 4 adjacent *divergent* GWs, not 4
    adjacent calendar GWs — the autocorrelation guard is approximate on a sparse subset.
    """
    diff = []
    for _, g in pool.groupby("gw"):
        gg = g.dropna(subset=[baseline_col, challenger_col, "total_points"])
        if gg.empty:
            continue
        base_row = gg.loc[gg[baseline_col].idxmax()]
        chal_row = gg.loc[gg[challenger_col].idxmax()]
        if base_row["player_id"] != chal_row["player_id"]:
            diff.append(float(chal_row["total_points"] - base_row["total_points"]))
    diff = np.asarray(diff, dtype=float)
    n_gw = pool["gw"].nunique()
    lo, hi = _ci3((diff > 0).astype(float)) if len(diff) >= 4 else (float("nan"), float("nan"))
    d_lo, d_hi = _ci3(diff) if len(diff) >= 4 else (float("nan"), float("nan"))
    return {
        "baseline": baseline_col,
        "challenger": challenger_col,
        "n_divergent": len(diff),
        "n_gw": int(n_gw),
        "winrate": round(float((diff > 0).mean()), 3) if len(diff) else float("nan"),
        "winrate_ci": (lo, hi),
        "mean_pts_diff": round(float(diff.mean()), 3) if len(diff) else float("nan"),
        "mean_pts_diff_ci": (d_lo, d_hi),
    }


def _oos_scores(sub: pd.DataFrame, feats: list[str], mode: str) -> np.ndarray:
    """Out-of-sample P(is_oracle) per row under one CV scheme (NaN where a GW went unscored).

    ``logo`` trains on every *other* gameweek — past **and future**. That maximizes power at this n,
    but it is not a deployable forecast: late-season form/fixture structure informs an early-GW score.
    ``walk_forward`` trains strictly on ``gw < t``, the discipline every term-level fit in
    ``model.terms`` already follows (``_poisson_component.fit``). Its early GWs are unscored (no prior
    data) and its early folds are thin — that thinness is part of the honest answer, not a bug to patch.
    """
    oos = np.full(len(sub), np.nan)
    for gw in sorted(sub["gw"].unique()):
        tr = sub[sub["gw"] != gw] if mode == "logo" else sub[sub["gw"] < gw]
        te = (sub["gw"] == gw).to_numpy()
        if tr["is_oracle"].nunique() < 2:  # walk-forward: no prior data / no prior oracle yet
            continue
        mu, sd = tr[feats].mean(), tr[feats].std() + 1e-9
        m = LogisticRegression(max_iter=200).fit((tr[feats] - mu) / sd, tr["is_oracle"])
        oos[te] = m.predict_proba((sub.loc[te, feats] - mu) / sd)[:, 1]
    return oos


def _auc_and_floor(sub: pd.DataFrame, oos: np.ndarray, n_null: int, seed: int) -> tuple[float, float, int]:
    """(out-of-sample AUC, min-detectable AUC, n_oracle) on whatever rows a scheme actually scored.

    The permutation floor is recomputed **on the scheme's own mask**: a scheme that scores fewer GWs
    has fewer oracle observations and therefore a genuinely higher detectability floor. Reusing the
    LOGO floor for a thinner walk-forward mask would understate what that scheme has to clear.
    """
    mask = ~np.isnan(oos)
    y = sub["is_oracle"].to_numpy()[mask]
    if mask.sum() == 0 or len(np.unique(y)) < 2:
        return (float("nan"), float("nan"), int(y.sum()) if len(y) else 0)
    auc = round(float(roc_auc_score(y, oos[mask])), 3)
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n_null):
        perm = sub.groupby("gw")["is_oracle"].transform(
            lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).to_numpy()
        )
        yp = perm.to_numpy()[mask]
        if len(np.unique(yp)) == 2:
            null.append(roc_auc_score(yp, oos[mask]))
    floor = round(float(np.percentile(null, 95)), 3) if null else float("nan")
    return (auc, floor, int(y.sum()))


def oracle_discrimination(
    pool: pd.DataFrame, features: tuple[str, ...] = tuple(DISCRIMINATION_FEATURES), n_null: int = 500, seed: int = 0
) -> dict:
    """Does any ex-ante signal separate the oracle from the field? (single AUCs + two CV schemes + power).

    Single-feature AUC for `P(is_oracle)`, plus an out-of-sample logistic AUC under **both** CV schemes
    — leave-one-GW-out and strictly walk-forward — each against its own within-GW label-permutation
    null (95th percentile = the **minimum detectable AUC** at that scheme's n). Both are reported: LOGO
    answers "is there signal here at all, at maximum power", walk-forward answers "could you have
    *used* it ex-ante". They are different questions and the gap between them is the point.
    """
    feats = [f for f in features if f in pool.columns]
    sub = pool.dropna(subset=[*feats, "is_oracle"]).copy()
    single = {
        f: round(float(roc_auc_score(sub["is_oracle"], sub[f])), 3) for f in feats if sub["is_oracle"].nunique() == 2
    }

    logo = _oos_scores(sub, feats, "logo")
    wf = _oos_scores(sub, feats, "walk_forward")
    logo_auc, logo_floor, n_oracle = _auc_and_floor(sub, logo, n_null, seed)
    wf_auc, wf_floor, n_oracle_wf = _auc_and_floor(sub, wf, n_null, seed)
    return {
        "single_auc": single,
        "combined_logo_auc": logo_auc,
        "min_detectable_auc": logo_floor,
        "signal_detected": bool(logo_auc > logo_floor),
        "n_oracle": n_oracle,
        "n_scored_logo": int((~np.isnan(logo)).sum()),
        "combined_wf_auc": wf_auc,
        "min_detectable_auc_wf": wf_floor,
        "signal_detected_wf": bool(wf_auc > wf_floor),
        "n_oracle_wf": n_oracle_wf,
        "n_scored_wf": int((~np.isnan(wf)).sum()),
        "n_gw_scored_wf": int(sub.loc[~np.isnan(wf), "gw"].nunique()),
    }


# Q3 is asked of every strategy that made a Phase-5 claim, not just the mean: the ceiling columns are
# the ones that beat template there, so 'the model's divergent picks lose' has to be shown for THEM
# before it can license an 'irreducible' verdict. (baseline, challenger) pairs.
DIVERGENCE_PAIRS = (
    ("base_season", "e_points"),  # the frozen Phase-5 crux
    ("base_season", "p90"),
    ("base_season", "p_haul"),
    ("ownership_count", "p90"),  # template as the baseline
    ("ownership_count", "p_haul"),
)


def captaincy_diagnostic_report(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> dict:
    """Full Door-1 report: Q1 concentration, Q2 oracle-rank, Q3 divergence, Q4 discrimination + power."""
    pool = build_diagnostic_pool(mart, n_sims=n_sims, seed=seed)
    reg = reducible_regret(pool)
    return {
        "n_gw": int(pool["gw"].nunique()),
        "concentration": reg,
        "top20_share": reg.attrs["top20_share"],
        "gini": reg.attrs["gini"],
        "oracle_hits": oracle_rank_hits(pool),
        "divergence": divergence_winrate(pool),
        "divergence_by_pair": pd.DataFrame(
            [divergence_winrate(pool, b, c) for b, c in DIVERGENCE_PAIRS if {b, c} <= set(pool.columns)]
        ),
        "discrimination": oracle_discrimination(pool, seed=seed),
    }
