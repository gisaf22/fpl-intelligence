"""Compose the term registry into E[points] via the domain scoring rule (spec §1 item 4, §2).

Iterates :data:`model.terms.registry.TERM_MODELS` (no hardcoded term list): fits each model once, maps
its emitted view(s) onto a master player panel (team-grain terms are **broadcast** to players), then
assembles the FPL points decomposition using the ``domain`` weights. ``bonus`` is fit last and calibrated
onto the *expected* returns of the other terms (its cross-term dependency).

This is now the **canonical** E[points] engine (the ``points_model.walk_forward_points`` god-file it
strangled has been deleted). ``selected`` goals/assists draw the full 5-feature process pool where the
mart carries it, matching the old ``full_pts`` attacking components; GK ``p60`` uses the ``minutes`` term's
robust rate rather than the old flat-0.98 shortcut, so GK scores diverge from the retired model **by
design** (a deliberate improvement, not a gap). The decomposition is internally exact (the parts sum to
``e_points``). ``compose_points(keep_all=True)`` adds the ex-ante blank tail: ``p_play`` and
``e_points_uncond`` = P(play) x E[points | played] (spec X1).
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
from model.eval.baselines import expanding_prior_mean
from model.features.build import broadcast
from model.terms.bonus.bonus import returns_points  # noqa: F401  (kept for parity/reference)
from model.terms.registry import BONUS_MODEL, PLAY_MODEL, TERM_MODELS

_GOAL_MULT = {"GK": GOAL_POINTS_GK, "DEF": GOAL_POINTS_DEF, "MID": GOAL_POINTS_MID, "FWD": GOAL_POINTS_FWD}
_CS_MULT = {"GK": CLEAN_SHEET_POINTS_GK, "DEF": CLEAN_SHEET_POINTS_DEF, "MID": CLEAN_SHEET_POINTS_MID, "FWD": 0}
_CONCEDED_POS = ("GK", "DEF")
_DC_POS = ("DEF", "MID", "FWD")
# Goal points are attributed to OUTFIELD only. A GK scoring is astronomically rare, but the pooled goals
# model emits a spurious tiny GK e_goals (~0.06) and the x10 GK goal multiplier squares that into a large
# variance (~6.3 — bigger than the clean-sheet term), which over-disperses the GK distribution and wrecks
# GK interval coverage (Phase-4 diagnosis). Gating GK goals to 0 is the honest correction: E[GK goals] ~ 0.
_GOAL_POS = ("DEF", "MID", "FWD")

# The points decomposition (parts sum to e_points); stable across positions, zero where inapplicable.
DECOMP_COLUMNS = ("appearance", "goals", "assists", "clean_sheets", "goals_conceded",
                  "saves", "defensive_contribution", "bonus")

# Raw term views renamed to the sampling vocabulary the simulator draws from (spec §1 item 5). These are
# the UN-scored, UN-gated parameters: Poisson means (e_*), P(GA=0) (p_cs), Bernoulli probs (p60, p_dc),
# and the already point-valued conceded penalty. simulate.py draws through the FPL rules from these.
_VIEW_TO_PARAM = {
    "goals": "e_goals", "assists": "e_assists", "saves": "e_saves",
    "clean_sheet": "p_cs", "conceded": "conceded_pts",
    "defensive_contribution": "p_dc", "p60": "p60",
}
# The parameter panel = identity keys + the raw params + bonus's per-row scoring-map coefficients.
PARAM_COLUMNS = (*_VIEW_TO_PARAM.values(), "bonus_intercept", "bonus_slope")


def _master_panel(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
    """The player panel every term view is aligned onto.

    Default (``keep_all=False``) is the conditional-on-appearance panel (``minutes>0``). ``keep_all=True``
    retains potential-blank (``minutes==0``) rows so the ex-ante universe can be scored — the components
    are evaluated as-if-played on those rows and P(play) de-conditions them (spec X1). The keep_all universe
    is **fixtures-only**: a no-fixture / blank-gameweek row (``minutes`` null) is not a captaincy candidate,
    so it is excluded (excluded either way — the default ``minutes>0`` already drops nulls).
    """
    keep = ((~mart["is_dgw"].astype(bool)) & mart["minutes"].notna()) if keep_all \
        else (mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))
    df = mart[keep].copy()
    return df.sort_values(["player_id", "gw"]).reset_index(drop=True)


def _collect_views(master: pd.DataFrame, mart: pd.DataFrame, keep_all: bool = False) -> dict[str, np.ndarray]:
    """Fit every registered model and map each emitted view onto ``master`` (broadcast if team-grain).

    ``keep_all`` widens the player-grain populations to potential blanks (predicted as-if-played, trained
    on ``minutes>0``); the team-grain joint model is unaffected (constraint: team-GA/CS need no blank
    handling — they are broadcast onto whatever players ``master`` carries)."""
    views: dict[str, np.ndarray] = {}
    for model in TERM_MODELS:
        team_grain = model.grain == "team_gw"
        fitted = model.fit(mart) if team_grain else model.fit(mart, keep_all=keep_all)
        pop = model.population(mart) if team_grain else model.population(mart, keep_all=keep_all)
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


def _bonus_coeffs_per_row(master: pd.DataFrame, mart: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """The bonus scoring-map coefficients (intercept, slope) aligned to each master row by (position, gw).

    Bonus is a contemporaneous per-(position, gw) OLS of realized bonus on realized returns; surfacing
    the coefficients per row lets both ``compose_points`` (apply to EXPECTED returns) and ``simulate.py``
    (apply to DRAWN returns, per sample) reuse the same fit. NaN where a (position, gw) cell is unfit.
    """
    coeffs = BONUS_MODEL.fit(mart).meta["coefficients"]
    if coeffs.empty:
        nan = np.full(len(master), np.nan)
        return nan, nan
    keyed = master[["position", "gw"]].merge(coeffs, on=["position", "gw"], how="left")
    return keyed["intercept"].to_numpy(), keyed["slope"].to_numpy()


def _p_play_view(master: pd.DataFrame, mart: pd.DataFrame) -> np.ndarray:
    """P(play) = P(minutes>0) mapped onto ``master`` (spec X1). ``PLAY_MODEL``'s population is already the
    whole universe, so it scores every master row (blanks included); NaN pre-warmup / on thin slices."""
    fitted = PLAY_MODEL.fit(mart, keep_all=True)
    pop = PLAY_MODEL.population(mart, keep_all=True)
    frame = pop[["player_id", "gw"]].copy()
    frame[PLAY_MODEL.term] = fitted.predictions.to_numpy()
    merged = master[["player_id", "gw"]].merge(frame, on=["player_id", "gw"], how="left")
    return merged[PLAY_MODEL.term].to_numpy()


def compose_parameters(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
    """The raw per-row parameter panel every term view exposes, BEFORE scoring/gating (spec §1 item 5).

    Returns the master player panel keyed by (player_id, team_id, gw, position, minutes) plus one column
    per :data:`PARAM_COLUMNS`: the Poisson means, P(GA=0), Bernoulli probs, point-valued conceded penalty,
    and bonus's scoring-map coefficients. This is the single surface both :func:`compose_points` (means ->
    E[points]) and ``simulate.py`` (draws -> points distribution) build on, so view-collection happens once.

    ``keep_all=True`` widens the panel to potential-blank rows (each term scored as-if-played) and adds a
    ``p_play`` = P(minutes>0) column — the unconditional factor :func:`compose_points` multiplies out front.
    The default path is unchanged (no ``p_play`` column; conditional-on-appearance panel).
    """
    master = _master_panel(mart, keep_all=keep_all)
    views = _collect_views(master, mart, keep_all=keep_all)
    out = master[["player_id", "team_id", "gw", "position", "minutes"]].copy()
    for view, param in _VIEW_TO_PARAM.items():
        out[param] = views.get(view, np.full(len(master), np.nan))
    out["bonus_intercept"], out["bonus_slope"] = _bonus_coeffs_per_row(master, mart)
    if keep_all:
        out["p_play"] = _p_play_view(master, mart)
    return out


def compose_points(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
    """Assemble E[points] (+ its per-term decomposition) from the term registry.

    Returns the master player panel with one column per :data:`DECOMP_COLUMNS`, ``e_points`` (their sum),
    and ``base_season`` (the player's expanding prior-mean points — the incumbent bar). Pre-warmup rows
    carry NaN term views -> 0 contributions (filter ``gw > WARMUP_GW`` downstream). Built on
    :func:`compose_parameters` (the shared raw-parameter surface) — this scores its means through the
    domain rule; ``simulate.py`` draws from the same panel for the distribution.

    ``e_points`` is the **conditional-on-appearance** expectation (E[points | played]) — appearance is the
    as-if-played ``1 + p60`` (never gated on realized minutes, matching the shipped ``full_pts``).
    ``keep_all=True`` widens to potential-blank rows and adds ``p_play`` + ``e_points_uncond`` =
    P(play) x E[points | played] (spec X1: the unconditional expectation over the ex-ante universe).
    """
    params = compose_parameters(mart, keep_all=keep_all)
    pos = params["position"]
    gmult = pos.map(_GOAL_MULT).astype(float).to_numpy()
    cmult = pos.map(_CS_MULT).astype(float).to_numpy()

    def p(name: str) -> np.ndarray:
        return np.nan_to_num(params[name].to_numpy(dtype=float), nan=0.0)

    p60 = p("p60")
    d = pd.DataFrame(index=params.index)
    # Conditional-on-appearance (as-if-played): appearance = 1 + p60, NOT gated on realized minutes. On the
    # default master (all minutes>0) this equals the prior ``where(minutes>0, ..., 0)`` bit-for-bit; on the
    # keep_all panel it is the E[appearance | played] a blank row must carry before the P(play) multiply.
    d["appearance"] = SHORT_APPEARANCE_POINTS + (FULL_APPEARANCE_POINTS - SHORT_APPEARANCE_POINTS) * p60
    d["goals"] = np.where(pos.isin(_GOAL_POS), gmult * p("e_goals"), 0.0)   # GK goals ~ 0 (see _GOAL_POS)
    d["assists"] = ASSIST_POINTS * p("e_assists")
    d["clean_sheets"] = cmult * p("p_cs") * p60                             # gated by minutes (>=60')
    d["goals_conceded"] = np.where(pos.isin(_CONCEDED_POS), p("conceded_pts"), 0.0)  # already point-valued (<=0)
    d["saves"] = np.where(pos.eq("GK"), p("e_saves") / GK_SAVES_PER_POINT, 0.0)
    d["defensive_contribution"] = np.where(pos.isin(_DC_POS), DC_POINTS * p("p_dc"), 0.0)

    # bonus: the per-row scoring map applied to the EXPECTED returns (point value of goals/assists/CS/saves).
    returns_pts = d["goals"] + d["assists"] + d["clean_sheets"] + d["saves"]
    e_bonus = p("bonus_intercept") + p("bonus_slope") * returns_pts.to_numpy()
    d["bonus"] = np.clip(e_bonus, 0.0, BPS_BONUS_FIRST)

    out = params[["player_id", "team_id", "gw", "position", "minutes"]].copy()
    for col in DECOMP_COLUMNS:
        out[col] = d[col].to_numpy()
    out["e_points"] = out[list(DECOMP_COLUMNS)].sum(axis=1)
    # base_season: the player's expanding prior-mean points (the incumbent bar), single-sourced from
    # model.eval.baselines. On the keep_all panel this is the incl-blanks variant (blanks lower the mean).
    out["base_season"] = expanding_prior_mean(_master_panel(mart, keep_all=keep_all)).to_numpy()
    if keep_all:
        # De-condition: E[points]_unconditional = P(play) x E[points | played]. The Monte-Carlo sim stays
        # conditional (constraint: P(play) enters only the mean/captaincy strategies, not the draws).
        out["p_play"] = params["p_play"].to_numpy()
        out["e_points_uncond"] = out["e_points"].to_numpy() * out["p_play"].to_numpy()
    return out
