"""Phase 2.2 - regularized signal combination (extends the Phase 2.1 component model).

Phase 2.1 fit each point-driving component on a small, hand-picked feature set. Phase 2.2
re-tests the *full salvaged family roster* against each component's own target under an
**elastic-net penalty** (L1 selects, L2 groups collinear signals such as ``xgi_roll3`` vs
``xgi_roll5`` and ``minutes_roll3`` vs ``minutes_roll8``), then composes the fitted
components to E[points] via the FPL scoring rule and gates the result, within position,
against **two** bars: the Phase-0 incumbent (``base_season``) *and* the best single
candidate signal. Clearing both closes assumptions-register item A-F1 (family verdicts were
``total_points`` marginal reads, never component-validated against the baseline).

Design decisions (see docs/predictive-layer-plan.md Phase 2.2 and the frozen studies):
  * **Regularizer = per-component ``statsmodels`` GLM.fit_regularized**, NOT a single Gaussian
    ``sklearn`` ElasticNetCV. Each component keeps its evidence-picked family (goals/assists
    Poisson, clean sheet / GK-saves logistic-or-Poisson), so the zero-inflated count shape and
    the P(clean sheet) output survive - a Gaussian elastic net on ``total_points`` would lose both.
  * **Penalty strength (alpha) is chosen by an inner *temporal* split** of the training window
    (never random k-fold - that leaks across gameweeks): earlier GWs fit, latest GWs validate,
    pick the alpha minimizing the family's deviance. ``L1_WT`` fixes the L1/L2 mix.
  * **Features are standardized on train statistics before penalization** (the penalty is
    scale-sensitive); the intercept is never penalized (alpha vector is 0 in that slot).
  * **Lagged process parts are built in-harness** - the mart carries only the *composite*
    ``xgi_roll`` lag-safe, so ``xg_roll3/5`` and ``xa_roll3/5`` are derived here via
    ``.shift(1).rolling()`` (leakage-safe) so goals see lagged xG and assists see lagged xA
    component-appropriately (per X6, process > realized), not the double-counting composite.
  * **minutes enters as a free covariate**, not a proportional offset (A-P1 exposure test rejected
    proportionality for DEF/FWD); **conditional on appearance** (X1); expanding walk-forward.

Composition drops within-position constants (appearance/bonus/cards) - they do not change rank;
GK saves (~18% of GK points) is the one flagged exception, added as a lagged-rate term for GK.
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

# --- Candidate rosters (the salvaged family roster, re-tested PER COMPONENT: A-F1) ---
# All columns are strictly-prior / lag-safe: mart ``*_roll`` exclude the current GW (verified);
# ``xg_roll*``/``xa_roll*`` are derived lag-safe below; ``was_home`` is the upcoming venue,
# known pre-kickoff; ``fdr_avg`` is the published fixture difficulty (also pre-kickoff).
_GOAL_FEATURES = [
    "xg_roll3", "xg_roll5", "xgi_roll3", "xgi_roll5",
    "minutes_roll3", "minutes_roll8", "minutes_trend",
    "transfers_in", "ownership_count", "purchase_price", "was_home", "fdr_avg",
]
_ASSIST_FEATURES = [
    "xa_roll3", "xa_roll5", "xgi_roll3", "xgi_roll5",
    "minutes_roll3", "minutes_roll8", "transfers_in", "ownership_count", "was_home", "fdr_avg",
]
_CS_FEATURES = [
    "goals_conceded_roll3", "goals_conceded_roll5", "xgc_roll3", "xgc_roll5",
    "clean_sheets_roll3", "clean_sheets_roll5", "minutes_roll3", "was_home", "fdr_avg",
]
# GK saves ~ shots faced (xgc proxy) x minutes; converted to points at 3 saves = 1 pt.
_SAVES_FEATURES = ["xgc_roll3", "xgc_roll5", "minutes_roll3", "fdr_avg"]

# Union of every candidate column (coerced to plain float once - some mart cols are nullable
# Float64 / boolean, which break statsmodels' float design matrix).
_ALL_FEATURES = sorted(set(_GOAL_FEATURES + _ASSIST_FEATURES + _CS_FEATURES + _SAVES_FEATURES))

# ``minutes_trend`` is ORDINAL (a monotone playing-time direction), so it maps to a single
# signed numeric coefficient rather than one-hot dummies (no non-monotone hypothesis to test).
_MINUTES_TREND_MAP = {"falling": -1.0, "stable": 0.0, "rising": 1.0}

# Component -> (feature roster, GLM family). Clean sheet is binary (Bernoulli/logistic);
# goals/assists are near-Poisson (Phase-2 gate-1 dispersion diagnosis - NB parked, ~Poisson).
_COMPONENTS: dict[str, tuple[list[str], object]] = {
    "goals_scored": (_GOAL_FEATURES, sm.families.Poisson()),
    "assists": (_ASSIST_FEATURES, sm.families.Poisson()),
    "clean_sheets": (_CS_FEATURES, sm.families.Binomial()),
}

# Elastic-net penalty. Both the strength (alpha) AND the L1/L2 mix (L1_wt) are chosen per fit
# from these grids by inner *temporal* validation - the mix governs how the collinear roll3/roll5
# and minutes pairs are grouped, so it is tuned, not assumed. alpha=0 is the unpenalized fit
# (L1_wt is then irrelevant, so only its default is tried at alpha=0 to save fits).
ALPHA_GRID = (0.0, 0.001, 0.003, 0.01, 0.03, 0.1)
L1_WT_GRID = (0.2, 0.5, 0.8)
_L1_WT_DEFAULT = 0.5
# Share of the training window's *latest* gameweeks held out to score penalty candidates.
INNER_VAL_FRAC = 0.25
MIN_TRAIN_ROWS = 100
MIN_FIT_ROWS = 30


def _lagged_roll(df: pd.DataFrame, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean of ``src`` per player (shift(1) BEFORE rolling -> no current GW).

    Mirrors the leakage-safe construction of the mart's own ``*_roll`` columns, used here to
    build ``xg_roll*``/``xa_roll*`` which the mart does not carry lag-safe.
    """
    return (
        df.groupby("player_id")[src]
        .transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    )


def _add_lagged_process(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``xg_roll3/5`` and ``xa_roll3/5`` (lag-safe) so components see their own process part."""
    for src, roll in (("xg", "xg_roll"), ("xa", "xa_roll")):
        for w in (3, 5):
            df[f"{roll}{w}"] = _lagged_roll(df, src, w)
    return df


def _encode_ordinals(df: pd.DataFrame) -> pd.DataFrame:
    """Map the ordinal ``minutes_trend`` string to a signed numeric (falling/stable/rising -> -1/0/1).

    Guards on "not already numeric" (not ``dtype == object``) because the mart backs this column
    with a pyarrow string dtype, which is neither ``object`` nor numeric.
    """
    if "minutes_trend" in df.columns and not pd.api.types.is_numeric_dtype(df["minutes_trend"]):
        df["minutes_trend"] = df["minutes_trend"].map(_MINUTES_TREND_MAP).astype(float)
    return df


def _present(features: list[str], columns) -> list[str]:
    """Roster restricted to columns actually in the mart (so an absent optional signal is dropped,
    not assumed) - closes the ``fdr_avg`` "verify before including" gap (A-F1 build discipline)."""
    return [f for f in features if f in columns]


def _prepare(mart: pd.DataFrame) -> pd.DataFrame:
    """Shared population + feature prep for every entry point (canonical population, lag-safe).

    ``minutes > 0`` and DGW-excluded (canonical), sorted per player-GW, ``was_home`` and the
    ordinal ``minutes_trend`` numericized, lagged xg/xa process parts added, candidate columns
    coerced to plain float. Warns (does not assume) if the optional ``fdr_avg`` is absent.
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    df["was_home"] = df["was_home"].astype(float)
    df = _encode_ordinals(df)
    df = _add_lagged_process(df)
    if "fdr_avg" not in df.columns:
        warnings.warn("fdr_avg absent from mart; dropped from candidate rosters", stacklevel=2)
    present = [c for c in _ALL_FEATURES if c in df.columns]
    df[present] = df[present].astype(float)
    return df


def _standardize(train_x: np.ndarray, test_x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Z-score features on train statistics (penalty is scale-sensitive); apply to test.

    Zero-variance columns get std=1 (their standardized value is 0; the penalty then zeroes them).
    """
    mean = np.nanmean(train_x, axis=0)
    std = np.nanstd(train_x, axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return (train_x - mean) / std, (test_x - mean) / std


def _deviance(family: object, y: np.ndarray, mu: np.ndarray) -> float:
    """Mean family deviance (lower is better) for scoring alpha candidates on the inner split."""
    mu = np.clip(mu, 1e-8, None)
    if isinstance(family, sm.families.Binomial):
        p = np.clip(mu, 1e-8, 1 - 1e-8)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    # Poisson deviance (y*log(y/mu) -> 0 at y=0; compute the log only where y>0).
    term = np.zeros_like(mu, dtype=float)
    pos = y > 0
    term[pos] = y[pos] * np.log(y[pos] / mu[pos])
    return float(np.mean(2.0 * (term - (y - mu))))


def _fit_regularized(x: np.ndarray, y: np.ndarray, family: object, alpha: float, l1_wt: float):
    """Elastic-net GLM with a design that already has an intercept in column 0 (never penalized)."""
    alpha_vec = np.full(x.shape[1], alpha)
    alpha_vec[0] = 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.GLM(y, x, family=family)
        if alpha <= 0.0:
            return model.fit()
        return model.fit_regularized(alpha=alpha_vec, L1_wt=l1_wt)


def _select_penalty(
    train: pd.DataFrame, target: str, features: list[str], family: object
) -> tuple[float, float]:
    """Pick (alpha, L1_wt) minimizing family deviance on an inner *temporal* holdout of the train.

    Earlier GWs fit, the latest ``INNER_VAL_FRAC`` of distinct GWs validate. The L1/L2 mix is
    tuned alongside the strength (it governs collinear-pair grouping); at alpha=0 the mix is
    irrelevant so only the default is tried. Falls back to the unpenalized fit when too short.
    """
    default = (0.0, _L1_WT_DEFAULT)
    gws = np.sort(train["gw"].unique())
    if len(gws) < 4:
        return default
    cut = gws[int(len(gws) * (1.0 - INNER_VAL_FRAC))]
    inner_tr = train[train["gw"] < cut].dropna(subset=[*features, target])
    inner_va = train[train["gw"] >= cut].dropna(subset=[*features, target])
    if len(inner_tr) < MIN_FIT_ROWS or len(inner_va) < MIN_FIT_ROWS or inner_tr[target].nunique() < 2:
        return default

    tr_x, va_x = _standardize(inner_tr[features].to_numpy(float), inner_va[features].to_numpy(float))
    tr_x = sm.add_constant(tr_x, has_constant="add")
    va_x = sm.add_constant(va_x, has_constant="add")
    y_tr, y_va = inner_tr[target].to_numpy(float), inner_va[target].to_numpy(float)

    best, best_dev = default, np.inf
    for alpha in ALPHA_GRID:
        mixes = L1_WT_GRID if alpha > 0.0 else (_L1_WT_DEFAULT,)
        for l1_wt in mixes:
            try:
                res = _fit_regularized(tr_x, y_tr, family, alpha, l1_wt)
                dev = _deviance(family, y_va, np.asarray(res.predict(va_x)))
            except Exception:
                continue
            if dev < best_dev:
                best, best_dev = (alpha, l1_wt), dev
    return best


def _fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, target: str, features: list[str], family: object
) -> tuple[np.ndarray, dict | None]:
    """Select (alpha, L1_wt) by inner temporal CV, refit on the full train, predict test.

    Returns ``(predictions, info)`` where ``info`` carries the chosen penalty and the fitted
    standardized coefficients per feature (for selection logging), or ``None`` on a too-thin /
    degenerate slice or a convergence failure (prediction is a NaN vector then; contract as 2.1).
    """
    tr = train.dropna(subset=[*features, target])
    if len(tr) < MIN_FIT_ROWS or tr[target].nunique() < 2:
        return np.full(len(test), np.nan), None
    alpha, l1_wt = _select_penalty(train, target, features, family)
    tr_x, te_x = _standardize(tr[features].to_numpy(float), test[features].to_numpy(float))
    tr_x = sm.add_constant(tr_x, has_constant="add")
    te_x = sm.add_constant(te_x, has_constant="add")
    try:
        res = _fit_regularized(tr_x, tr[target].to_numpy(float), family, alpha, l1_wt)
        coefs = dict(zip(features, np.asarray(res.params, dtype=float)[1:]))  # drop intercept (col 0)
        info = {"alpha": alpha, "l1_wt": l1_wt, "coefs": coefs}
        return np.asarray(res.predict(te_x)), info
    except Exception:
        return np.full(len(test), np.nan), None


def _record(log: list | None, gw: int, component: str, info: dict | None) -> None:
    """Append one row per feature to the selection log (chosen penalty + standardized coef)."""
    if log is None or info is None:
        return
    for feat, coef in info["coefs"].items():
        log.append({
            "gw": gw, "component": component, "feature": feat,
            "alpha": info["alpha"], "l1_wt": info["l1_wt"],
            "coef": float(coef), "selected": int(abs(coef) > 1e-8),
        })


def _compose_e_points(
    df: pd.DataFrame, eval_gws: list[int], log: list | None = None
) -> pd.Series:
    """Expanding walk-forward: fit each component regularized, compose to E[points] per row.

    When ``log`` is provided, each fit's chosen penalty and coefficients are recorded (P4
    selection stability) - the composition itself is unchanged whether or not logging is on.
    """
    e = pd.Series(np.nan, index=df.index)
    goal_feats = _present(_COMPONENTS["goals_scored"][0], df.columns)
    assist_feats = _present(_COMPONENTS["assists"][0], df.columns)
    cs_feats = _present(_COMPONENTS["clean_sheets"][0], df.columns)
    saves_feats = _present(_SAVES_FEATURES, df.columns)
    for t in eval_gws:
        train = df[df["gw"] < t]
        test = df[df["gw"] == t]
        if test.empty or len(train) < MIN_TRAIN_ROWS:
            continue
        pos = test["position"].to_numpy()
        goal_mult = np.array([_GOAL_MULT.get(p, 0) for p in pos], dtype=float)
        cs_mult = np.array([_CS_MULT.get(p, 0) for p in pos], dtype=float)

        e_goals, info_g = _fit_predict(train, test, "goals_scored", goal_feats, _COMPONENTS["goals_scored"][1])
        e_assists, info_a = _fit_predict(train, test, "assists", assist_feats, _COMPONENTS["assists"][1])
        e_cs, info_c = _fit_predict(train, test, "clean_sheets", cs_feats, _COMPONENTS["clean_sheets"][1])
        _record(log, t, "goals_scored", info_g)
        _record(log, t, "assists", info_a)
        _record(log, t, "clean_sheets", info_c)
        e_points = goal_mult * e_goals + ASSIST_POINTS * e_assists + cs_mult * e_cs

        # GK saves (~18% of GK points): fit on GK rows only, add converted saves points.
        gk_tr, gk_te = train[train["position"] == "GK"], test[test["position"] == "GK"]
        if not gk_te.empty and len(gk_tr.dropna(subset=saves_feats)) >= MIN_FIT_ROWS:
            e_saves, info_s = _fit_predict(gk_tr, gk_te, "saves", saves_feats, sm.families.Poisson())
            _record(log, t, "saves", info_s)
            e_points[np.isin(test.index, gk_te.index)] += e_saves / GK_SAVES_PER_POINT

        e.loc[test.index] = e_points
    return e


def _best_single_signal(ev: pd.DataFrame, features: list[str]) -> tuple[str, float]:
    """Strongest single candidate as a within-position ranker: max |Spearman(signal, points)|.

    Oracle-oriented (absolute rho) so it is an *upper bound* on any single-signal ranker - beating
    it is an unambiguous "beats the best single signal" (the second gate leg, A-F1). Returns
    (signal, rho) with rho carrying the winning signal's natural (signed) correlation.
    """
    best_sig, best_abs, best_signed = "", -np.inf, np.nan
    for s in features:
        if ev[s].nunique() <= 1:
            continue
        rho = grouped_spearman(ev, s, "total_points", ["gw"], MIN_ROWS_PER_POS)
        if not np.isnan(rho) and abs(rho) > best_abs:
            best_sig, best_abs, best_signed = s, abs(rho), rho
    return best_sig, round(best_signed, 4)


def walk_forward_signal_combination(mart: pd.DataFrame) -> pd.DataFrame:
    """Regularized component combination vs the incumbent AND the best single signal, per position.

    Returns a frame indexed by (position, model) with within-position Spearman on the common
    evaluation set. Rows per position: ``base_season (incumbent)``, ``best single signal``
    (with the winning signal name in ``note``), and ``regularized combination`` (Phase 2.2).
    The gate is: regularized combination beats BOTH bars, per position.
    """
    df = _prepare(mart)
    df["base_season"] = df.groupby("player_id")["total_points"].transform(lambda s: s.expanding().mean().shift(1))

    feat_cols = _present(sorted(set(_GOAL_FEATURES + _ASSIST_FEATURES + _CS_FEATURES)), df.columns)
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)
    df["e_points"] = _compose_e_points(df, eval_gws)

    # Common evaluation set: rows where the model, the incumbent, and every candidate are defined,
    # so all three bars are scored on identical rows (differences aren't a coverage artifact).
    ev = df[df["gw"] > WARMUP_GW].dropna(subset=["e_points", "base_season"])
    ev = ev[ev[feat_cols].notna().all(axis=1)]

    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        pos_feats = _present(
            sorted(set(_GOAL_FEATURES + _ASSIST_FEATURES + (_CS_FEATURES if _CS_MULT[pos] else []))),
            df.columns,
        )
        best_sig, best_rho = _best_single_signal(sub, pos_feats)
        n_gw = int(sub["gw"].nunique())
        rho_base = grouped_spearman(sub, "base_season", "total_points", ["gw"], MIN_ROWS_PER_POS)
        rho_reg = grouped_spearman(sub, "e_points", "total_points", ["gw"], MIN_ROWS_PER_POS)
        rows.append({"position": pos, "model": "base_season (incumbent)",
                     "spearman": round(rho_base, 4), "n_gw": n_gw, "note": ""})
        rows.append({"position": pos, "model": "best single signal",
                     "spearman": best_rho, "n_gw": n_gw, "note": best_sig})
        rows.append({"position": pos, "model": "regularized combination",
                     "spearman": round(rho_reg, 4), "n_gw": n_gw, "note": ""})

    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])


def gradient_boosting_ceiling(mart: pd.DataFrame) -> pd.DataFrame:
    """A2.3 ceiling probe: a non-linear reference ranking directly on ``total_points``, per position.

    NOT a ship candidate - a diagnostic on how much the linear-additive, component-compositional
    structure of :func:`walk_forward_signal_combination` leaves on the table for missed feature
    interactions. Same population, same expanding walk-forward, same common eval set; a
    ``HistGradientBoostingRegressor`` (native NaN handling) is fit on the full candidate roster.
    Returns per-position Spearman to sit beside the regularized combination.
    """
    from sklearn.ensemble import HistGradientBoostingRegressor

    df = _prepare(mart)
    feats = _present(sorted(set(_GOAL_FEATURES + _ASSIST_FEATURES + _CS_FEATURES)), df.columns)
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)
    df["gbm"] = np.nan
    for t in eval_gws:
        train = df[(df["gw"] < t)].dropna(subset=["total_points"])
        test = df[df["gw"] == t]
        if test.empty or len(train) < MIN_TRAIN_ROWS:
            continue
        # Drop columns that are constant/all-NaN in this fold (early folds have a constant
        # minutes_trend before enough history exists) - HGB's binning rejects a zero-variance column.
        fold_feats = [c for c in feats if train[c].nunique(dropna=True) > 1]
        if not fold_feats:
            continue
        gbm = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200,
                                            l2_regularization=1.0, random_state=0)
        gbm.fit(train[fold_feats].to_numpy(float), train["total_points"].to_numpy(float))
        df.loc[test.index, "gbm"] = gbm.predict(test[fold_feats].to_numpy(float))

    ev = df[df["gw"] > WARMUP_GW].dropna(subset=["gbm"])
    ev = ev[ev[feats].notna().all(axis=1)]
    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        rows.append({"position": pos, "model": "gradient boosting (ceiling)",
                     "spearman": round(grouped_spearman(sub, "gbm", "total_points", ["gw"], MIN_ROWS_PER_POS), 4),
                     "n_gw": int(sub["gw"].nunique())})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values("position").set_index(["position", "model"])


def selection_stability(mart: pd.DataFrame) -> pd.DataFrame:
    """Which candidates the penalty actually KEEPS per component, across the walk-forward (A-F1).

    Re-runs the same expanding component fits with coefficient logging on, then aggregates to
    ``selection_freq`` (share of folds where the standardized coef is non-zero) and
    ``mean_abs_coef`` (its average standardized magnitude) per (component, feature). This is the
    receipt that demotes the family "informative" labels to a prior: it shows *what survived a
    fair, tuned elastic-net selection*, not just the final composed score. It also settles the
    ``was_home`` placement question (P3) empirically - read the ``was_home`` rows across
    components to see whether the penalty keeps it for clean sheets but drops it for goals/assists
    (the Phase 2.1 v2 "venue is a defensive signal" finding), rather than us hard-coding it.

    Returns a frame indexed by (component, feature), ordered by component then selection_freq desc.
    """
    df = _prepare(mart)
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)
    log: list = []
    _compose_e_points(df, eval_gws, log=log)
    if not log:
        return pd.DataFrame(columns=["selection_freq", "mean_abs_coef", "mean_alpha", "folds"])

    lg = pd.DataFrame(log)
    agg = (
        lg.groupby(["component", "feature"])
        .agg(
            selection_freq=("selected", "mean"),
            mean_abs_coef=("coef", lambda s: float(np.mean(np.abs(s)))),
            mean_alpha=("alpha", "mean"),
            folds=("selected", "size"),
        )
        .reset_index()
    )
    agg["selection_freq"] = agg["selection_freq"].round(3)
    agg["mean_abs_coef"] = agg["mean_abs_coef"].round(4)
    agg["mean_alpha"] = agg["mean_alpha"].round(4)
    comp_order = ["goals_scored", "assists", "clean_sheets", "saves"]
    agg["component"] = pd.Categorical(agg["component"], categories=comp_order, ordered=True)
    return agg.sort_values(["component", "selection_freq"], ascending=[True, False]).set_index(
        ["component", "feature"]
    )
