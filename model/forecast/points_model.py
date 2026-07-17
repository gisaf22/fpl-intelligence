"""Phase 3.0 Track 3 - per-position POINTS model (extends the Phase-2 ranking model).

Where Phase 2 modelled 4 of the 12 scoring terms for *ranking*, this closes the equation into a
*points* model, per the `domain.fpl_scoring.POSITION_SCORING` spec and the Track-2 diagnostics
(`docs/studies/results/predictive-phase3-scoring-diagnostics.md`).

**Part 3.1 - team goals-against layer (this module, so far).** D-D showed `clean_sheet = 1{GA=0}`
and the conceded penalty `-floor(GA/2)` are the same random variable (team goals-against), so they
must fall out of ONE model, not two independent ones (independent models permit the impossible
`CS=1 & GA>0` state, observed 0% of the time). We model expected team goals-against as a Poisson
mean per team-fixture from leakage-safe lagged team defensive form + venue + fixture difficulty,
then derive **both** ``p_cs = P(GA=0) = exp(-lambda)`` **and** ``e_conceded_pts = E[-floor(GA/2)]``
from that one lambda - internally consistent by construction.

Remaining Track-3 parts (DC component, bonus proxy, minutes hurdle, per-position goals/assists)
land in follow-up commits; see the plan Phase 3.0 Track 3.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import poisson

from domain.fpl_scoring import (
    ASSIST_POINTS,
    BPS_BONUS_FIRST,
    CLEAN_SHEET_POINTS_DEF,
    CLEAN_SHEET_POINTS_GK,
    CLEAN_SHEET_POINTS_MID,
    DC_CBIRT_THRESHOLD_MID_FWD,
    DC_CBIT_THRESHOLD_DEF,
    DC_POINTS,
    FULL_APPEARANCE_POINTS,
    GK_SAVES_PER_POINT,
    GOAL_POINTS_DEF,
    GOAL_POINTS_FWD,
    GOAL_POINTS_GK,
    GOAL_POINTS_MID,
    SHORT_APPEARANCE_POINTS,
)
from model.eval.baselines import expanding_prior_mean
from model.eval.metrics import grouped_spearman
from model.eval.population import canonical
from model.eval.scorer import score_gates
from model.eval.walkforward import (
    MIN_ROWS_PER_POS,
    POSITIONS,
    WARMUP_GW,
)

# Leakage-safe lagged team defensive form + pre-kickoff fixture context (venue, difficulty).
TEAM_GA_FEATURES = ["ga_roll3", "ga_roll5", "xgc_roll3", "xgc_roll5", "was_home", "fdr_avg"]
MIN_TEAM_TRAIN_ROWS = 40
# GA support for the penalty expectation - P(GA>14) is negligible at any realistic lambda.
_GA_SUPPORT = np.arange(0, 15)
_GA_PENALTY = -(_GA_SUPPORT // 2)  # FPL: -1 per 2 conceded = -floor(GA/2)


def _lag_roll(df: pd.DataFrame, group: str, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per group (shift(1) BEFORE rolling -> excludes current row)."""
    return df.groupby(group)[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


def build_team_ga_panel(mart: pd.DataFrame) -> pd.DataFrame:
    """One row per (team_id, gw): team goals-against target + leakage-safe lagged features.

    Team GA is the max ``goals_conceded`` among the team's players who appeared (a full-match
    player saw every goal); team xGC is the mean expected-goals-conceded over appearances. DGW rows
    excluded (the team-fixture grain is ambiguous under two fixtures).
    """
    df = mart[~mart["is_dgw"].astype(bool)].copy()
    for c in ["goals_conceded", "xgc", "minutes", "was_home", "fdr_avg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    played = df[df["minutes"] > 0]
    team = (
        played.groupby(["team_id", "gw"])
        .agg(team_ga=("goals_conceded", "max"), team_xgc=("xgc", "mean"),
             was_home=("was_home", "max"), fdr_avg=("fdr_avg", "mean"))
        .reset_index()
        .sort_values(["team_id", "gw"])
    )
    for w in (3, 5):
        team[f"ga_roll{w}"] = _lag_roll(team, "team_id", "team_ga", w)
        team[f"xgc_roll{w}"] = _lag_roll(team, "team_id", "team_xgc", w)
    return team


def _conceded_penalty_expectation(lam: np.ndarray) -> np.ndarray:
    """E[-floor(GA/2)] under GA ~ Poisson(lam); NaN-safe (NaN lambda -> NaN)."""
    lam = np.asarray(lam, dtype=float)
    safe = np.nan_to_num(lam, nan=0.0)
    pmf = poisson.pmf(_GA_SUPPORT[None, :], safe[:, None])  # (n, K)
    exp = (pmf * _GA_PENALTY).sum(axis=1)
    return np.where(np.isnan(lam), np.nan, exp)


def walk_forward_team_ga(mart: pd.DataFrame) -> pd.DataFrame:
    """Expanding walk-forward team goals-against layer -> lambda_ga, p_cs, e_conceded_pts.

    Returns the team-fixture panel with a Poisson mean ``lambda_ga`` (fit on ``gw < t`` only) and
    the two derived, mutually-consistent quantities: ``p_cs = exp(-lambda_ga)`` and
    ``e_conceded_pts = E[-floor(GA/2)]``. Both CS and the conceded penalty come from this one column.
    """
    team = build_team_ga_panel(mart)
    eval_gws = sorted(g for g in team["gw"].unique() if g > WARMUP_GW)
    team["lambda_ga"] = np.nan
    for t in eval_gws:
        tr = team[team["gw"] < t].dropna(subset=[*TEAM_GA_FEATURES, "team_ga"])
        te = team[team["gw"] == t]
        if len(tr) < MIN_TEAM_TRAIN_ROWS or te.empty:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                x = sm.add_constant(tr[TEAM_GA_FEATURES].to_numpy(float), has_constant="add")
                res = sm.GLM(tr["team_ga"].to_numpy(float), x, family=sm.families.Poisson()).fit()
                xte = sm.add_constant(te[TEAM_GA_FEATURES].to_numpy(float), has_constant="add")
                team.loc[te.index, "lambda_ga"] = res.predict(xte)
            except Exception:
                continue
    team["p_cs"] = np.exp(-team["lambda_ga"].to_numpy(dtype=float))
    team["e_conceded_pts"] = _conceded_penalty_expectation(team["lambda_ga"].to_numpy())
    return team


# --- Part 3.2: defensive-contribution (DC) component ---------------------------------------
# DC scores +2 once a player hits their position's action threshold (DEF >= 10 CBIT; MID/FWD >=
# 12 CBIRT; GK exempt). Per D-A, DC is conditionally independent of conceding/CS given minutes, so
# it is a STANDALONE component: P(hit) from a logistic GLM on lagged DC-action form + minutes,
# then E[DC points] = DC_POINTS * P(hit). Fit per position (thresholds differ).
_DC_THRESHOLD = {"DEF": DC_CBIT_THRESHOLD_DEF, "MID": DC_CBIRT_THRESHOLD_MID_FWD,
                 "FWD": DC_CBIRT_THRESHOLD_MID_FWD}
_DC_POSITIONS = ("DEF", "MID", "FWD")
DC_FEATURES = ["dc_roll3", "dc_roll5", "minutes_roll3", "fdr_avg", "was_home"]
MIN_DC_TRAIN_ROWS = 50


def _add_dc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add leakage-safe lagged DC-action form (``dc_roll3/5``), the position threshold, and the
    binary target ``dc_hit`` = 1{defensive_contribution >= threshold}."""
    for c in ["defensive_contribution", "minutes_roll3", "fdr_avg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["was_home"] = df["was_home"].astype(float)
    for w in (3, 5):
        df[f"dc_roll{w}"] = _lag_roll(df, "player_id", "defensive_contribution", w)
    df["dc_threshold"] = df["position"].map(_DC_THRESHOLD)
    df["dc_hit"] = (df["defensive_contribution"] >= df["dc_threshold"]).astype(float)
    return df


def walk_forward_dc(mart: pd.DataFrame) -> pd.DataFrame:
    """Expanding walk-forward DC component -> per-row ``p_dc_hit`` and ``e_dc_pts`` (DEF/MID/FWD).

    Logistic GLM per position on lagged DC-action form + minutes + fixture context; GK are exempt
    (no DC term) and carry NaN. ``e_dc_pts = DC_POINTS * p_dc_hit``.
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    df = _add_dc_columns(df)
    df["p_dc_hit"] = np.nan
    for pos in _DC_POSITIONS:
        sdf = df[df["position"] == pos]
        for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
            tr = sdf[sdf["gw"] < t].dropna(subset=[*DC_FEATURES, "dc_hit"])
            te = sdf[sdf["gw"] == t]
            if len(tr) < MIN_DC_TRAIN_ROWS or tr["dc_hit"].nunique() < 2 or te.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    x = sm.add_constant(tr[DC_FEATURES].to_numpy(float), has_constant="add")
                    res = sm.GLM(tr["dc_hit"].to_numpy(float), x, family=sm.families.Binomial()).fit()
                    xte = sm.add_constant(te[DC_FEATURES].to_numpy(float), has_constant="add")
                    df.loc[te.index, "p_dc_hit"] = res.predict(xte)
                except Exception:
                    continue
    df["e_dc_pts"] = DC_POINTS * df["p_dc_hit"]
    return df


def dc_validation(mart: pd.DataFrame) -> pd.DataFrame:
    """Gate table: does modelled P(DC hit) rank realized DC hits, vs the lagged-count baseline?

    Within-position Spearman of ``p_dc_hit`` vs realized ``dc_hit`` beside the ``dc_roll3`` lagged
    baseline, with the base hit-rate (FWD is near-zero -> DC immaterial there). Indexed (position, model).
    """
    df = walk_forward_dc(mart)
    ev = df[(df["gw"] > WARMUP_GW) & df["p_dc_hit"].notna()]
    rows = []
    for pos in _DC_POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        rho_model = grouped_spearman(sub, "p_dc_hit", "dc_hit", ["gw"], MIN_ROWS_PER_POS)
        rho_base = grouped_spearman(sub.dropna(subset=["dc_roll3"]), "dc_roll3", "dc_hit",
                                     ["gw"], MIN_ROWS_PER_POS)
        n_gw = int(sub["gw"].nunique())
        hit = round(float(sub["dc_hit"].mean()), 3)
        rows.append({"position": pos, "model": "DC logistic P(hit)", "spearman": round(rho_model, 4),
                     "hit_rate": hit, "n_gw": n_gw})
        rows.append({"position": pos, "model": "dc_roll3 (baseline)", "spearman": round(rho_base, 4),
                     "hit_rate": hit, "n_gw": n_gw})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])


# --- Part 3.4: minutes hurdle + appearance --------------------------------------------------
# Minutes is a GATE, not a smooth covariate: appearance is 1 (1-59') / 2 (>=60'), and the
# clean-sheet term is only awarded at >=60'. Within the conditional-on-appearance population
# (minutes>0), we model P(>=60' | played); P(play) itself - the blank / 0-minute tail - is X1,
# deferred to Phase 5 (documented scope gap; it is the biggest missing tail for a distribution).
# For outfield, a per-position logistic on lagged minutes form yields the calibrated probability
# (ranking is ~parity with lagged minutes, but a raw minutes level is not a probability); GK play
# >=60' ~99% of the time, so the target is near-constant and the logistic is unstable - GK use a
# robust lagged rate instead. Uses: E[appearance | played] = 1 + P(>=60'), and P(>=60') gates CS.
MINUTES_HURDLE_FEATURES = ["minutes_roll3", "minutes_roll5", "minutes_roll8", "starts_roll3"]
_HURDLE_LOGIT_POSITIONS = ("DEF", "MID", "FWD")
MIN_HURDLE_TRAIN_ROWS = 50


def walk_forward_minutes_hurdle(mart: pd.DataFrame) -> pd.DataFrame:
    """Expanding walk-forward P(>=60' | played) -> ``p60`` and ``e_appearance`` = 1 + p60.

    Outfield: per-position logistic on lagged minutes form. GK: robust lagged expanding rate of
    ``play60`` (near-constant ~1, the logistic is degenerate there). ``play60`` is the realized
    >=60' indicator (the target).
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    for c in [*MINUTES_HURDLE_FEATURES[:-1], "minutes", "starts"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["starts_roll3"] = _lag_roll(df, "player_id", "starts", 3)
    df["play60"] = (df["minutes"] >= 60).astype(float)
    df["p60"] = np.nan

    # GK: robust prior-only expanding rate of play60 (per player), backfilled with the global
    # prior rate so early GWs still get a value.
    gk = df["position"] == "GK"
    prior_rate = df.groupby("player_id")["play60"].transform(lambda s: s.shift(1).expanding().mean())
    global_prior = df.loc[gk, "play60"].shift(1).expanding().mean()
    df.loc[gk, "p60"] = prior_rate[gk].fillna(global_prior).fillna(0.98)

    for pos in _HURDLE_LOGIT_POSITIONS:
        sdf = df[df["position"] == pos]
        for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
            tr = sdf[sdf["gw"] < t].dropna(subset=[*MINUTES_HURDLE_FEATURES, "play60"])
            te = sdf[sdf["gw"] == t]
            if len(tr) < MIN_HURDLE_TRAIN_ROWS or tr["play60"].nunique() < 2 or te.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    x = sm.add_constant(tr[MINUTES_HURDLE_FEATURES].to_numpy(float), has_constant="add")
                    res = sm.GLM(tr["play60"].to_numpy(float), x, family=sm.families.Binomial()).fit()
                    xte = sm.add_constant(te[MINUTES_HURDLE_FEATURES].to_numpy(float), has_constant="add")
                    df.loc[te.index, "p60"] = res.predict(xte)
                except Exception:
                    continue
    df["e_appearance"] = SHORT_APPEARANCE_POINTS + (FULL_APPEARANCE_POINTS - SHORT_APPEARANCE_POINTS) * df["p60"]
    return df


def minutes_hurdle_validation(mart: pd.DataFrame) -> pd.DataFrame:
    """Gate table: does modelled P(>=60') rank the realized >=60' indicator, vs lagged minutes?

    Within-position Spearman of ``p60`` vs ``play60`` beside the ``minutes_roll3`` baseline. Outfield
    is ~parity (the value is the calibrated probability, not a ranking win); GK is near-constant
    (~0.99 base rate) so ranking is near-meaningless. Indexed (position, model).
    """
    df = walk_forward_minutes_hurdle(mart)
    df["minutes_roll3"] = pd.to_numeric(df["minutes_roll3"], errors="coerce")
    ev = df[(df["gw"] > WARMUP_GW) & df["p60"].notna()]
    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        rho_model = grouped_spearman(sub, "p60", "play60", ["gw"], MIN_ROWS_PER_POS)
        rho_base = grouped_spearman(sub.dropna(subset=["minutes_roll3"]), "minutes_roll3", "play60",
                                     ["gw"], MIN_ROWS_PER_POS)
        n_gw = int(sub["gw"].nunique())
        base_rate = round(float(sub["play60"].mean()), 3)
        rows.append({"position": pos, "model": "P(>=60') hurdle", "spearman": round(rho_model, 4),
                     "play60_rate": base_rate, "n_gw": n_gw})
        rows.append({"position": pos, "model": "minutes_roll3 (baseline)", "spearman": round(rho_base, 4),
                     "play60_rate": base_rate, "n_gw": n_gw})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])


# --- Composition: full per-position points model (Track 3 close-out) -------------------------
# Compose the shipped parts to E[points] per player-GW via the domain scoring structure, then gate
# per position against TWO bars: the Phase-0 incumbent (base_season) and the Phase-2.1 four-component
# ranking model (goals + assists + player-CS-Bernoulli + saves). Saves ported from Phase 2.1. Bonus
# uses EXPECTED returns (the whole chain is linear, so the plug-in is exact for the mean). CS is
# gated per player by P(>=60'); conceded (GK/DEF) and DC (DEF/MID) applied per the position spec.
GOAL_FEATURES = ["xg_roll3", "xg_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"]
ASSIST_FEATURES = ["xa_roll3", "xa_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"]
SAVES_FEATURES = ["xgc_roll3", "minutes_roll3"]           # GK, ported from Phase 2.1
CS_OLD_FEATURES = ["goals_conceded_roll3", "xgc_roll3", "minutes_roll3", "was_home"]  # Phase-2.1 bar


def _logit_fit_predict(train: pd.DataFrame, test: pd.DataFrame, feats: list[str], tgt: str) -> np.ndarray:
    tr = train.dropna(subset=[*feats, tgt])
    if len(tr) < MIN_DC_TRAIN_ROWS or tr[tgt].nunique() < 2:
        return np.full(len(test), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            x = sm.add_constant(tr[feats].to_numpy(float), has_constant="add")
            res = sm.GLM(tr[tgt].to_numpy(float), x, family=sm.families.Binomial()).fit()
            return np.asarray(res.predict(sm.add_constant(test[feats].to_numpy(float), has_constant="add")))
        except Exception:
            return np.full(len(test), np.nan)


def _prepare_points_panel(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
    """Player panel (DGW-excluded) with every lagged feature + team-GA broadcast + base_season.

    Default keeps only ``minutes>0`` rows (the conditional-on-appearance population). ``keep_all=True``
    retains 0-minute rows too (for ex-ante scoring of potential blanks, Phase 5) - components are still
    TRAINED on ``minutes>0`` only (see ``walk_forward_points``); this only widens the prediction set.
    """
    team = walk_forward_team_ga(mart)[["team_id", "gw", "p_cs", "e_conceded_pts"]]
    keep = ~mart["is_dgw"].astype(bool) if keep_all else (mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))
    df = mart[keep].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    numeric = ["xg", "xa", "xgc_roll3", "xgi_roll3", "xgi_roll5", "minutes_roll3", "minutes_roll5",
               "minutes_roll8", "goals_conceded_roll3", "defensive_contribution", "starts", "fdr_avg",
               "goals_scored", "assists", "saves", "clean_sheets", "bonus", "total_points"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["was_home"] = df["was_home"].astype(float)
    for s in ("xg", "xa"):
        for w in (3, 5):
            df[f"{s}_roll{w}"] = _lag_roll(df, "player_id", s, w)
    for w in (3, 5):
        df[f"dc_roll{w}"] = _lag_roll(df, "player_id", "defensive_contribution", w)
    df["starts_roll3"] = _lag_roll(df, "player_id", "starts", 3)
    df["play60"] = (df["minutes"] >= 60).astype(float)
    df["dc_hit"] = (df["defensive_contribution"] >= df["position"].map(_DC_THRESHOLD)).astype(float)
    df = df.merge(team, on=["team_id", "gw"], how="left")
    df["base_season"] = expanding_prior_mean(df)
    return df


def walk_forward_points(mart: pd.DataFrame, predict_all: bool = False) -> pd.DataFrame:
    """Expanding walk-forward FULL points model -> ``full_pts`` (+ ``p21_pts`` Phase-2.1 bar, ``base_season``).

    Composes E[points] from the shipped parts per the position scoring structure; ``p21_pts`` is the
    Phase-2.1 four-component ranking model scored on identical rows for a fair gate. ``predict_all=True``
    also scores 0-minute (potential-blank) rows ex-ante (Phase 5 captaincy) - components are still
    TRAINED on ``minutes>0`` only, so this only widens the prediction set, not the fit.
    """
    df = _prepare_points_panel(mart, keep_all=predict_all)
    for col in ["e_goals", "e_assists", "e_saves", "p_dc", "p60", "p_cs_old", "e_bonus",
                "bonus_intercept", "bonus_slope"]:
        df[col] = np.nan
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)
    for t in eval_gws:
        tr, te = df[(df["gw"] < t) & (df["minutes"] > 0)], df[df["gw"] == t]
        if te.empty or len(tr) < MIN_TEAM_TRAIN_ROWS:
            continue
        df.loc[te.index, "e_goals"] = _poisson_fit_predict(tr, te, GOAL_FEATURES, "goals_scored")
        df.loc[te.index, "e_assists"] = _poisson_fit_predict(tr, te, ASSIST_FEATURES, "assists")
        df.loc[te.index, "p_cs_old"] = _logit_fit_predict(tr, te, CS_OLD_FEATURES, "clean_sheets")
        gk_tr, gk_te = tr[tr["position"] == "GK"], te[te["position"] == "GK"]
        if not gk_te.empty:
            df.loc[gk_te.index, "e_saves"] = _poisson_fit_predict(gk_tr, gk_te, SAVES_FEATURES, "saves")
            df.loc[gk_te.index, "p60"] = 0.98  # GK play >=60' ~always (3.4)
        for pos in _DC_POSITIONS:
            trp, tep = tr[tr["position"] == pos], te[te["position"] == pos]
            if tep.empty:
                continue
            df.loc[tep.index, "p_dc"] = _logit_fit_predict(trp, tep, DC_FEATURES, "dc_hit")
            df.loc[tep.index, "p60"] = _logit_fit_predict(trp, tep, MINUTES_HURDLE_FEATURES, "play60")
        # bonus: per-position OLS on realized returns_pts, applied to EXPECTED returns_pts
        tr_rp = tr.assign(rp=_returns_points(tr))
        for pos in POSITIONS:
            trp = tr_rp[tr_rp["position"] == pos].dropna(subset=["rp", "bonus"])
            tep = te[te["position"] == pos]
            if len(trp) < MIN_BONUS_TRAIN_ROWS or tep.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                b = sm.OLS(trp["bonus"].to_numpy(float),
                           sm.add_constant(trp[["rp"]].to_numpy(float), has_constant="add")).fit()
            idx = tep.index
            e_cs = df.loc[idx, "p_cs"].fillna(0) * df.loc[idx, "p60"].fillna(0)
            e_sav = (df.loc[idx, "e_saves"].fillna(0) / GK_SAVES_PER_POINT) if pos == "GK" else 0.0
            erp = (_GOAL_MULT[pos] * df.loc[idx, "e_goals"].fillna(0)
                   + ASSIST_POINTS * df.loc[idx, "e_assists"].fillna(0)
                   + _CS_MULT[pos] * e_cs + e_sav)
            pred = b.predict(sm.add_constant(erp.to_numpy().reshape(-1, 1), has_constant="add"))
            df.loc[idx, "e_bonus"] = np.clip(pred, 0.0, BPS_BONUS_FIRST)
            # expose the proxy coefficients so the simulator can apply bonus per draw (co-movement)
            df.loc[idx, "bonus_intercept"] = float(b.params[0])
            df.loc[idx, "bonus_slope"] = float(b.params[1])

    pos = df["position"]
    gmult, cmult = pos.map(_GOAL_MULT).astype(float), pos.map(_CS_MULT).astype(float)
    core = gmult * df["e_goals"] + ASSIST_POINTS * df["e_assists"] + df["e_bonus"].fillna(0) + (1.0 + df["p60"])
    e_sav = (df["e_saves"] / GK_SAVES_PER_POINT).where(pos == "GK", 0.0).fillna(0.0)
    df["full_pts"] = (core
                      + (cmult * df["p_cs"] * df["p60"]).fillna(0)
                      + df["e_conceded_pts"].where(pos.isin(["GK", "DEF"]), 0.0).fillna(0)
                      + (DC_POINTS * df["p_dc"]).where(pos.isin(_DC_POSITIONS), 0.0).fillna(0)
                      + e_sav)
    df["p21_pts"] = gmult * df["e_goals"] + ASSIST_POINTS * df["e_assists"] + (cmult * df["p_cs_old"]).fillna(0) + e_sav
    return df


def points_model_gate(mart: pd.DataFrame) -> pd.DataFrame:
    """Dual-bar gate: full points model vs Phase-2.1 component model vs base_season, per position.

    Routes through the reusable :func:`model.eval.scorer.score_gates`, so each cell now carries a
    **block-bootstrap CI** and **coverage** alongside the within-position Spearman (all three scored on
    the common eval set - identical rows). Indexed (position, model).
    """
    df = walk_forward_points(mart)
    ev = df[df["gw"] > WARMUP_GW].dropna(subset=["full_pts", "p21_pts", "base_season"])
    out = score_gates(ev, {
        "full_pts": "full points model",
        "p21_pts": "Phase-2.1 component model",
        "base_season": "base_season (incumbent)",
    })
    return out.set_index(["position", "model"])


# --- Part 3.5: per-position vs pooled goals/assists (A-P2) -----------------------------------
# Phase 2 fit goals/assists POOLED across positions + a position multiplier at composition. The
# multiplier is a within-position constant (irrelevant to within-position ranking), so this tests
# whether the goal/assist RATE process genuinely differs by position enough that a per-position fit
# ranks better. Verdict (real mart): NO - pooled wins or ties almost everywhere (pooling gives more
# data per fit; the process is common up to scale). This function reproduces the comparison; the
# resolution is to KEEP the pooled model (Phase 2's approach).
_PROCESS_SPECS = {
    "goals_scored": ["xg_roll3", "xg_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"],
    "assists": ["xa_roll3", "xa_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"],
}


def _add_process_rolls(df: pd.DataFrame) -> pd.DataFrame:
    """Leakage-safe lagged xg/xa process rolls (mart carries only the composite xgi lag-safe)."""
    for src in ("xg", "xa"):
        df[src] = pd.to_numeric(df[src], errors="coerce")
        for w in (3, 5):
            df[f"{src}_roll{w}"] = _lag_roll(df, "player_id", src, w)
    return df


def _poisson_fit_predict(train: pd.DataFrame, test: pd.DataFrame, feats: list[str], tgt: str) -> np.ndarray:
    tr = train.dropna(subset=[*feats, tgt])
    if len(tr) < 40 or tr[tgt].nunique() < 2:
        return np.full(len(test), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            x = sm.add_constant(tr[feats].to_numpy(float), has_constant="add")
            res = sm.GLM(tr[tgt].to_numpy(float), x, family=sm.families.Poisson()).fit()
            return np.asarray(res.predict(sm.add_constant(test[feats].to_numpy(float), has_constant="add")))
        except Exception:
            return np.full(len(test), np.nan)


def pooled_vs_perposition(mart: pd.DataFrame) -> pd.DataFrame:
    """A-P2 gate: within-position Spearman of goals/assists, pooled+multiplier vs per-position fit.

    Expanding walk-forward; the pooled model fits one Poisson on all positions, the per-position
    model fits a separate Poisson per position. Returns (component, position) -> pooled,
    per_position, delta. A positive delta means per-position beats pooled at that cell.
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    df = _add_process_rolls(df)
    for c in ["xgi_roll3", "xgi_roll5", "minutes_roll3", "goals_scored", "assists"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    eval_gws = sorted(g for g in df["gw"].unique() if g > WARMUP_GW)

    rows = []
    for tgt, feats in _PROCESS_SPECS.items():
        df["pooled"] = np.nan
        df["perpos"] = np.nan
        for t in eval_gws:
            tr, te = df[df["gw"] < t], df[df["gw"] == t]
            if te.empty:
                continue
            df.loc[te.index, "pooled"] = _poisson_fit_predict(tr, te, feats, tgt)
            for pos in POSITIONS:
                tep = te[te["position"] == pos]
                if tep.empty:
                    continue
                df.loc[tep.index, "perpos"] = _poisson_fit_predict(tr[tr["position"] == pos], tep, feats, tgt)
        ev = df[df["gw"] > WARMUP_GW].dropna(subset=["pooled", "perpos", tgt])
        for pos in POSITIONS:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            rp = grouped_spearman(sub, "pooled", tgt, ["gw"], MIN_ROWS_PER_POS)
            rq = grouped_spearman(sub, "perpos", tgt, ["gw"], MIN_ROWS_PER_POS)
            rows.append({"component": tgt, "position": pos, "pooled": round(rp, 4),
                         "per_position": round(rq, 4), "delta": round(rq - rp, 4)})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["component", "position"]).set_index(["component", "position"])


# --- Part 3.3: bonus proxy ------------------------------------------------------------------
# Bonus (top-3 BPS in the match -> 3/2/1) is caused by the SAME-match performance, so this is a
# contemporaneous scoring-map (returns -> bonus), used at composition/simulation time when the
# returns are expected/sampled - NOT a lagged forecast. D-B found the ``returns_pts`` composite
# (FPL point value of the modelled returns) is a strong BPS proxy (rho 0.50-0.77); a per-component
# GLM does NOT beat it, and adding DC HURTS the ranking (D-C's small partial correlation does not
# survive as a linear model term). So the proxy is a per-position calibration on ``returns_pts``:
# it preserves that ranking and yields an ``E[bonus]`` magnitude for composition.
_GOAL_MULT = {"GK": GOAL_POINTS_GK, "DEF": GOAL_POINTS_DEF, "MID": GOAL_POINTS_MID, "FWD": GOAL_POINTS_FWD}
_CS_MULT = {"GK": CLEAN_SHEET_POINTS_GK, "DEF": CLEAN_SHEET_POINTS_DEF, "MID": CLEAN_SHEET_POINTS_MID, "FWD": 0}
MIN_BONUS_TRAIN_ROWS = 50


def _returns_points(df: pd.DataFrame) -> pd.Series:
    """FPL point value of the modelled returns (goals/assists/CS/GK-saves), per position -
    the strong BPS proxy from D-B. Uses whatever component columns are present (realized at
    validation; expected at composition)."""
    goals = pd.to_numeric(df["goals_scored"], errors="coerce").fillna(0.0)
    assists = pd.to_numeric(df["assists"], errors="coerce").fillna(0.0)
    cs = pd.to_numeric(df["clean_sheets"], errors="coerce").fillna(0.0)
    saves = pd.to_numeric(df["saves"], errors="coerce").fillna(0.0)
    gmult = df["position"].map(_GOAL_MULT).astype(float)
    cmult = df["position"].map(_CS_MULT).astype(float)
    save_pts = np.where(df["position"].eq("GK"), saves // GK_SAVES_PER_POINT, 0.0)
    return goals * gmult + assists * ASSIST_POINTS + cs * cmult + save_pts


def walk_forward_bonus(mart: pd.DataFrame) -> pd.DataFrame:
    """Expanding walk-forward bonus proxy -> per-row ``e_bonus`` (calibrated E[bonus] in [0, 3]).

    Per-position OLS of realized ``bonus`` on ``returns_pts`` (fit on ``gw < t``), applied to the
    row's ``returns_pts``; clipped to the valid bonus range. Ranking equals ``returns_pts`` (a
    monotone calibration); the fit only sets the magnitude.
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df["returns_pts"] = _returns_points(df)
    df["bonus_actual"] = pd.to_numeric(df["bonus"], errors="coerce")
    df["e_bonus"] = np.nan
    for pos in POSITIONS:
        sdf = df[df["position"] == pos]
        for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
            tr = sdf[sdf["gw"] < t].dropna(subset=["returns_pts", "bonus_actual"])
            te = sdf[sdf["gw"] == t]
            if len(tr) < MIN_BONUS_TRAIN_ROWS or te.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    x = sm.add_constant(tr[["returns_pts"]].to_numpy(float), has_constant="add")
                    res = sm.OLS(tr["bonus_actual"].to_numpy(float), x).fit()
                    xte = sm.add_constant(te[["returns_pts"]].to_numpy(float), has_constant="add")
                    df.loc[te.index, "e_bonus"] = np.clip(res.predict(xte), 0.0, BPS_BONUS_FIRST)
                except Exception:
                    continue
    return df


def bonus_validation(mart: pd.DataFrame) -> pd.DataFrame:
    """Gate table: does the calibrated bonus proxy rank realized bonus (vs the raw returns_pts)?

    Within-position Spearman of ``e_bonus`` vs realized ``bonus`` beside the ``returns_pts`` signal
    (they match by construction - the calibration preserves ranking; D-B levels). Indexed (position, model).
    """
    df = walk_forward_bonus(mart)
    ev = df[(df["gw"] > WARMUP_GW) & df["e_bonus"].notna()]
    rows = []
    for pos in POSITIONS:
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        rho_proxy = grouped_spearman(sub, "e_bonus", "bonus_actual", ["gw"], MIN_ROWS_PER_POS)
        rho_base = grouped_spearman(sub, "returns_pts", "bonus_actual", ["gw"], MIN_ROWS_PER_POS)
        n_gw = int(sub["gw"].nunique())
        rows.append({"position": pos, "model": "bonus proxy (calibrated)",
                     "spearman": round(rho_proxy, 4), "n_gw": n_gw})
        rows.append({"position": pos, "model": "returns_pts (signal)",
                     "spearman": round(rho_base, 4), "n_gw": n_gw})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])


def team_ga_cs_validation(mart: pd.DataFrame) -> pd.DataFrame:
    """Gate table: does the team-GA-derived P(CS) rank realized clean sheets, vs a naive baseline?

    Within-position Spearman of ``p_cs`` (from the one team-GA model) against realized
    ``clean_sheets``, beside the lagged ``clean_sheets_roll3`` incumbent, for the positions where a
    clean sheet scores (GK/DEF/MID). Indexed by (position, model).
    """
    team = walk_forward_team_ga(mart)
    played = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    pl = played.merge(team[["team_id", "gw", "p_cs"]], on=["team_id", "gw"], how="left")
    pl["cs_roll"] = pd.to_numeric(pl["clean_sheets_roll3"], errors="coerce")
    ev = pl[(pl["gw"] > WARMUP_GW) & pl["p_cs"].notna()]

    rows = []
    for pos in [p for p in POSITIONS if p != "FWD"]:  # FWD get no clean-sheet points
        sub = ev[ev["position"] == pos]
        if sub.empty:
            continue
        rho_model = grouped_spearman(sub, "p_cs", "clean_sheets", ["gw"], MIN_ROWS_PER_POS)
        rho_base = grouped_spearman(sub.dropna(subset=["cs_roll"]), "cs_roll", "clean_sheets",
                                     ["gw"], MIN_ROWS_PER_POS)
        n_gw = int(sub["gw"].nunique())
        rows.append({"position": pos, "model": "team-GA P(CS)", "spearman": round(rho_model, 4), "n_gw": n_gw})
        rows.append({"position": pos, "model": "clean_sheets_roll3 (incumbent)",
                     "spearman": round(rho_base, 4), "n_gw": n_gw})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])


def unmodeled_points_share(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-position share of total points DEFERRED by the component map (bonus, and GK saves).

    Quantifies the accuracy ceiling the component ranking model cannot reach and motivates closing
    the points equation here. Findings:
    docs/studies/results/predictive-phase3-scoring-diagnostics.md.
    """
    pop = canonical(mart)
    rows = []
    for pos in POSITIONS:
        sub = pop[pop["position"] == pos]
        tp = float(pd.to_numeric(sub["total_points"], errors="coerce").sum())
        bonus_pct = 100 * float(pd.to_numeric(sub["bonus"], errors="coerce").sum()) / tp
        saves = np.floor(pd.to_numeric(sub["saves"], errors="coerce").fillna(0) / GK_SAVES_PER_POINT)
        saves_pct = 100 * float(saves.sum()) / tp if pos == "GK" else 0.0
        rows.append({"position": pos, "total_points": round(tp),
                     "bonus_pct": round(bonus_pct, 1), "gk_saves_pct": round(saves_pct, 1)})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values("position").set_index("position")
