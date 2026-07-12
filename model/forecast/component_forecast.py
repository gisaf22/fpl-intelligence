"""Phase 2.1 - component forecast: fit, compose to E[points], gate vs the Phase-0 baseline.

Predicts each point-driving component one gameweek ahead from **strictly-prior, lag-safe**
features (the mart's ``*_roll3/5`` columns exclude the current GW - verified), then composes
the fitted components into an expected-points column via the FPL scoring rule and scores it,
within position, against the Phase-0 incumbent (`base_season`).

Design decisions (see the plan §Phase 2.1 and the frozen studies):
  * families by the dispersion diagnosis - goals/assists Poisson (near-Poisson, Gate 1),
    clean sheet Bernoulli/logistic;
  * **minutes enters as a covariate, NOT a proportional offset** (exposure test rejected
    proportionality for DEF/FWD) - via lagged ``minutes_roll3`` (expected minutes);
  * **conditional on appearance** (X1) - ranks players who featured; future availability
    (P(play)) is out of scope here;
  * expanding walk-forward - at each evaluated GW *t*, fit on rows with ``gw < t`` only.

Composition for *ranking* drops constant/deferred pieces (appearance, saves, bonus, cards)
because a within-position constant does not change rank; saves (GK ~18% of points) are the
one flagged exception, added as a lagged-rate term for GK.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from domain.fpl_scoring import (
    ASSIST_POINTS,
    CLEAN_SHEET_POINTS_DEF,
    CLEAN_SHEET_POINTS_GK,
    CLEAN_SHEET_POINTS_MID,
    GK_SAVES_PER_POINT,
    GOAL_POINTS_DEF,
    GOAL_POINTS_FWD,
    GOAL_POINTS_GK,
    GOAL_POINTS_MID,
)
from model.eval.metrics import grouped_spearman
from model.eval.walkforward import (
    MIN_ROWS_PER_POS,
    POSITIONS,
    WARMUP_GW,
)

_GOAL_MULT = {"GK": GOAL_POINTS_GK, "DEF": GOAL_POINTS_DEF, "MID": GOAL_POINTS_MID, "FWD": GOAL_POINTS_FWD}
_CS_MULT = {"GK": CLEAN_SHEET_POINTS_GK, "DEF": CLEAN_SHEET_POINTS_DEF, "MID": CLEAN_SHEET_POINTS_MID, "FWD": 0}

# Feature columns. Roll features are lag-safe (verified exclude current GW); `was_home` is the
# upcoming fixture's venue — known before kickoff, so a legitimate predictor (not leakage).
_GOAL_FEATURES = ["xgi_roll3", "minutes_roll3"]
_ASSIST_FEATURES = ["xgi_roll3", "minutes_roll3"]
_CS_FEATURES = ["goals_conceded_roll3", "xgc_roll3", "minutes_roll3", "was_home"]
# GK saves ~ shots faced (xgc proxy) x minutes; converted to points at 3 saves = 1 pt.
_SAVES_FEATURES = ["xgc_roll3", "minutes_roll3"]


def _design(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Intercept + features design matrix (float, NaNs already dropped by caller)."""
    return sm.add_constant(df[features].to_numpy(dtype=float), has_constant="add")


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, target: str, features: list[str], family) -> np.ndarray:
    """Fit a GLM on train, return predicted mean for test. NaN vector on failure."""
    tr = train.dropna(subset=[*features, target])
    if len(tr) < 30 or tr[target].nunique() < 2:
        return np.full(len(test), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res = sm.GLM(tr[target].to_numpy(dtype=float), _design(tr, features), family=family).fit()
            return res.predict(_design(test, features))
        except Exception:
            return np.full(len(test), np.nan)


def walk_forward_component_points(mart: pd.DataFrame) -> pd.DataFrame:
    """Expanding walk-forward component model -> composed E[points], scored per position.

    Returns a frame indexed by (position, model) with within-position Spearman on the common
    evaluation set, comparing the composed component model against the `base_season` incumbent.
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    df["was_home"] = df["was_home"].astype(float)
    # Phase-0 incumbent: expanding prior mean of points (base_season), within player.
    df["base_season"] = df.groupby("player_id")["total_points"].transform(lambda s: s.expanding().mean().shift(1))

    feat_cols = sorted(set(_GOAL_FEATURES + _ASSIST_FEATURES + _CS_FEATURES))
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)
    df["e_points"] = np.nan

    for t in eval_gws:
        train = df[df["gw"] < t]
        test = df[df["gw"] == t]
        if test.empty or len(train) < 100:
            continue
        e_goals = _fit_predict(train, test, "goals_scored", _GOAL_FEATURES, sm.families.Poisson())
        e_assists = _fit_predict(train, test, "assists", _ASSIST_FEATURES, sm.families.Poisson())
        e_cs = _fit_predict(train, test, "clean_sheets", _CS_FEATURES, sm.families.Binomial())
        pos = test["position"].to_numpy()
        goal_mult = np.array([_GOAL_MULT.get(p, 0) for p in pos], dtype=float)
        cs_mult = np.array([_CS_MULT.get(p, 0) for p in pos], dtype=float)
        e_points = goal_mult * e_goals + ASSIST_POINTS * e_assists + cs_mult * e_cs

        # GK saves component (~18% of GK points): fit on GK rows only, add saves points.
        gk_tr, gk_te = train[train["position"] == "GK"], test[test["position"] == "GK"]
        if not gk_te.empty and len(gk_tr.dropna(subset=_SAVES_FEATURES)) >= 30:
            e_saves = _fit_predict(gk_tr, gk_te, "saves", _SAVES_FEATURES, sm.families.Poisson())
            e_points[np.isin(test.index, gk_te.index)] += e_saves / GK_SAVES_PER_POINT

        df.loc[test.index, "e_points"] = e_points

    # Common evaluation set: rows where both the model and the incumbent are defined.
    ev = df[(df["gw"] > WARMUP_GW)].dropna(subset=["e_points", "base_season"])
    ev = ev[ev[feat_cols].notna().all(axis=1)]

    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        for col, label in [("base_season", "base_season (incumbent)"), ("e_points", "component model")]:
            rows.append({
                "position": pos, "model": label,
                "spearman": round(grouped_spearman(sub, col, "total_points", ["gw"], MIN_ROWS_PER_POS), 4),
                "n_gw": int(sub["gw"].nunique()),
            })
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])
