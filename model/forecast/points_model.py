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
    GK_SAVES_PER_POINT,
    GOAL_POINTS_DEF,
    GOAL_POINTS_FWD,
    GOAL_POINTS_GK,
    GOAL_POINTS_MID,
)
from model.eval.walkforward import (
    MIN_ROWS_PER_POS,
    POSITIONS,
    WARMUP_GW,
    _grouped_spearman,
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
        rho_model = _grouped_spearman(sub, "p_dc_hit", "dc_hit", ["gw"], MIN_ROWS_PER_POS)
        rho_base = _grouped_spearman(sub.dropna(subset=["dc_roll3"]), "dc_roll3", "dc_hit",
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
        rho_proxy = _grouped_spearman(sub, "e_bonus", "bonus_actual", ["gw"], MIN_ROWS_PER_POS)
        rho_base = _grouped_spearman(sub, "returns_pts", "bonus_actual", ["gw"], MIN_ROWS_PER_POS)
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
        rho_model = _grouped_spearman(sub, "p_cs", "clean_sheets", ["gw"], MIN_ROWS_PER_POS)
        rho_base = _grouped_spearman(sub.dropna(subset=["cs_roll"]), "cs_roll", "clean_sheets",
                                     ["gw"], MIN_ROWS_PER_POS)
        n_gw = int(sub["gw"].nunique())
        rows.append({"position": pos, "model": "team-GA P(CS)", "spearman": round(rho_model, 4), "n_gw": n_gw})
        rows.append({"position": pos, "model": "clean_sheets_roll3 (incumbent)",
                     "spearman": round(rho_base, 4), "n_gw": n_gw})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).set_index(["position", "model"])
