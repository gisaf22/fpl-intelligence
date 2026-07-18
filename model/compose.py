"""Compose the term registry into E[points] via the domain scoring rule (spec §1 item 4, §2).

Iterates :data:`model.terms.registry.TERM_MODELS` (no hardcoded term list): fits each model once, maps
its emitted view(s) onto a master player panel (team-grain terms are **broadcast** to players), then
assembles the FPL points decomposition using the ``domain`` weights. ``bonus`` is fit last and calibrated
onto the *expected* returns of the other terms (its cross-term dependency).

**Reproduction scope (agreed):** this reproduces the **component composition** — the terms *as extracted*
(goals/assists on their 2 mechanistic features). It does **not** yet reproduce the shipped
``points_model.walk_forward_points`` (``full_pts``), which inlines richer 5-feature goals/assists, a flat
GK ``p60``, and the expected-returns bonus at full fidelity. Closing that gap (materialize the xg/xa
process rolls, reconcile GK ``p60``) is a tracked follow-up; the decomposition here is internally exact
(the parts sum to ``e_points``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from domain.fpl_scoring import (
    ASSIST_POINTS,
    BPS_BONUS_FIRST,
    CLEAN_SHEET_POINTS_DEF,
    CLEAN_SHEET_POINTS_GK,
    CLEAN_SHEET_POINTS_MID,
    DC_POINTS,
    FULL_APPEARANCE_POINTS,
    GK_SAVES_PER_POINT,
    GOAL_POINTS_DEF,
    GOAL_POINTS_FWD,
    GOAL_POINTS_GK,
    GOAL_POINTS_MID,
    SHORT_APPEARANCE_POINTS,
)
from model.features.build import broadcast
from model.terms.bonus.bonus import returns_points  # noqa: F401  (kept for parity/reference)
from model.terms.registry import BONUS_MODEL, TERM_MODELS

_GOAL_MULT = {"GK": GOAL_POINTS_GK, "DEF": GOAL_POINTS_DEF, "MID": GOAL_POINTS_MID, "FWD": GOAL_POINTS_FWD}
_CS_MULT = {"GK": CLEAN_SHEET_POINTS_GK, "DEF": CLEAN_SHEET_POINTS_DEF, "MID": CLEAN_SHEET_POINTS_MID, "FWD": 0}
_CONCEDED_POS = ("GK", "DEF")
_DC_POS = ("DEF", "MID", "FWD")

# The points decomposition (parts sum to e_points); stable across positions, zero where inapplicable.
DECOMP_COLUMNS = ("appearance", "goals", "assists", "clean_sheets", "goals_conceded",
                  "saves", "defensive_contribution", "bonus")


def _master_panel(mart: pd.DataFrame) -> pd.DataFrame:
    """The conditional-on-appearance player panel every term view is aligned onto."""
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    return df.sort_values(["player_id", "gw"]).reset_index(drop=True)


def _collect_views(master: pd.DataFrame, mart: pd.DataFrame) -> dict[str, np.ndarray]:
    """Fit every registered model and map each emitted view onto ``master`` (broadcast if team-grain)."""
    views: dict[str, np.ndarray] = {}
    for model in TERM_MODELS:
        fitted = model.fit(mart)
        pop = model.population(mart)
        emitted = model.emit(fitted)
        if model.grain == "team_gw":
            frame = pop[["team_id", "gw"]].copy()
            for term, arr in emitted.items():
                frame[term] = arr
            bc = broadcast(master, frame, list(emitted))
            for term in emitted:
                views[term] = bc[term].to_numpy()
        else:
            frame = pop[["player_id", "gw"]].copy()
            for term, arr in emitted.items():
                frame[term] = arr
            merged = master[["player_id", "gw"]].merge(frame, on=["player_id", "gw"], how="left")
            for term in emitted:
                views[term] = merged[term].to_numpy()
    return views


def _bonus_on_expected_returns(master: pd.DataFrame, mart: pd.DataFrame, returns_pts: pd.Series) -> np.ndarray:
    """Calibrate bonus (fit on realized returns) and apply the coefficients to the EXPECTED returns.

    This is bonus's cross-term dependency (spec §bonus): the OLS is fit per (position, gw) on realized
    returns, then applied to the returns the other terms *expect*, so bonus co-moves with them.
    """
    coeffs = BONUS_MODEL.fit(mart).meta["coefficients"]
    if coeffs.empty:
        return np.full(len(master), np.nan)
    keyed = master[["position", "gw"]].merge(coeffs, on=["position", "gw"], how="left")
    e_bonus = keyed["intercept"].to_numpy() + keyed["slope"].to_numpy() * returns_pts.to_numpy()
    return np.clip(e_bonus, 0.0, BPS_BONUS_FIRST)


def compose_points(mart: pd.DataFrame) -> pd.DataFrame:
    """Assemble E[points] (+ its per-term decomposition) from the term registry.

    Returns the master player panel with one column per :data:`DECOMP_COLUMNS` and ``e_points`` (their
    sum). Pre-warmup rows carry NaN term views -> 0 contributions (filter ``gw > WARMUP_GW`` downstream).
    """
    master = _master_panel(mart)
    views = _collect_views(master, mart)
    pos = master["position"]
    gmult = pos.map(_GOAL_MULT).astype(float).to_numpy()
    cmult = pos.map(_CS_MULT).astype(float).to_numpy()

    def v(name: str) -> np.ndarray:
        return np.nan_to_num(views.get(name, np.full(len(master), np.nan)), nan=0.0)

    p60 = v("p60")
    d = pd.DataFrame(index=master.index)
    d["appearance"] = np.where(master["minutes"].to_numpy() > 0,
                               SHORT_APPEARANCE_POINTS + (FULL_APPEARANCE_POINTS - SHORT_APPEARANCE_POINTS) * p60, 0.0)
    d["goals"] = gmult * v("goals")
    d["assists"] = ASSIST_POINTS * v("assists")
    d["clean_sheets"] = cmult * v("clean_sheet") * p60                      # gated by minutes (>=60')
    d["goals_conceded"] = np.where(pos.isin(_CONCEDED_POS), v("conceded"), 0.0)   # already point-valued (<=0)
    d["saves"] = np.where(pos.eq("GK"), v("saves") / GK_SAVES_PER_POINT, 0.0)
    d["defensive_contribution"] = np.where(pos.isin(_DC_POS), DC_POINTS * v("defensive_contribution"), 0.0)

    # bonus: calibrated onto the EXPECTED returns (the point value of goals/assists/CS/saves so far).
    returns_pts = d["goals"] + d["assists"] + d["clean_sheets"] + d["saves"]
    d["bonus"] = np.nan_to_num(_bonus_on_expected_returns(master, mart, returns_pts), nan=0.0)

    out = master[["player_id", "team_id", "gw", "position", "minutes"]].copy()
    for col in DECOMP_COLUMNS:
        out[col] = d[col].to_numpy()
    out["e_points"] = out[list(DECOMP_COLUMNS)].sum(axis=1)
    return out
