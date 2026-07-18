"""The bonus Model + Term (spec §2) — strangled from ``points_model.walk_forward_bonus``.

Bonus (top-3 BPS in the match -> 3/2/1) is **caused by the same-match performance**, so this is a
**contemporaneous scoring-map**, not a lagged forecast: a per-position **OLS** calibration of realized
``bonus`` on ``returns_pts`` (the FPL value of the modelled returns — the strong BPS proxy from D-B). The
OLS *coefficients* are fit on prior gameweeks (``gw < t``) but applied to the *same-match* ``returns_pts``.

A one-off shape (OLS, contemporaneous), so it is standalone — no shared base. ``fit`` reproduces
``walk_forward_bonus`` (``e_bonus``) to the bit **and** exposes the per-(position, gw) intercept/slope in
``Fitted.meta`` so the simulator can apply bonus per draw (co-movement). At composition time the input is
the *expected* returns (from the other terms); here — for validation and the golden — it is the realized
returns in the mart.
"""

from __future__ import annotations

import warnings
from typing import ClassVar

import numpy as np
import pandas as pd
import statsmodels.api as sm

from domain.fpl_scoring import (
    ASSIST_POINTS,
    BPS_BONUS_FIRST,
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
from model.eval.walkforward import MIN_ROWS_PER_POS, POSITIONS, WARMUP_GW
from model.terms._base import (
    AssumptionReport,
    Diagnostics,
    Fitted,
    GateResult,
    Hypothesis,
)
from model.terms.bonus.spec import BONUS_POOL, GRAIN

_GOAL_MULT = {"GK": GOAL_POINTS_GK, "DEF": GOAL_POINTS_DEF, "MID": GOAL_POINTS_MID, "FWD": GOAL_POINTS_FWD}
_CS_MULT = {"GK": CLEAN_SHEET_POINTS_GK, "DEF": CLEAN_SHEET_POINTS_DEF, "MID": CLEAN_SHEET_POINTS_MID, "FWD": 0}
MIN_BONUS_TRAIN_ROWS = 50


def returns_points(df: pd.DataFrame) -> pd.Series:
    """FPL point value of the returns (goals/assists/CS/GK-saves), per position — the D-B BPS proxy.

    Uses whatever component columns are present: realized at validation, expected at composition. Mirrors
    ``points_model._returns_points`` exactly so the calibration reproduces the god-file.
    """
    goals = pd.to_numeric(df["goals_scored"], errors="coerce").fillna(0.0)
    assists = pd.to_numeric(df["assists"], errors="coerce").fillna(0.0)
    cs = pd.to_numeric(df["clean_sheets"], errors="coerce").fillna(0.0)
    saves = pd.to_numeric(df["saves"], errors="coerce").fillna(0.0)
    gmult = df["position"].map(_GOAL_MULT).astype(float)
    cmult = df["position"].map(_CS_MULT).astype(float)
    save_pts = np.where(df["position"].eq("GK"), saves // GK_SAVES_PER_POINT, 0.0)
    return goals * gmult + assists * ASSIST_POINTS + cs * cmult + save_pts


class BonusModel:
    """Per-position OLS calibration of realized bonus on ``returns_pts`` (the fittable unit)."""

    grain = GRAIN
    pool = BONUS_POOL
    family = staticmethod(sm.OLS)
    name = "bonus"
    term = "bonus"
    target = "bonus_actual"
    baseline_feature = "returns_pts"
    clip_max = BPS_BONUS_FIRST               # bonus is in [0, 3]
    hypotheses: ClassVar[tuple[Hypothesis, ...]] = (
        Hypothesis(
            claim="returns_pts (FPL value of modelled returns) is a strong same-match BPS proxy",
            test="within-position Spearman of e_bonus vs realized bonus (== returns_pts by construction), GW>3",
            success_threshold="proxy rho matches the returns_pts signal (calibration preserves ranking; D-B levels)",
            status="supported (D-B: rho 0.50-0.77; GLM/DC do not beat it)",
        ),
    )

    def __init__(self, variant: str = "selected", feature_override: list[str] | None = None) -> None:
        self.variant = variant
        self._feature_override = feature_override  # unused (single predictor) — kept for interface symmetry

    def features(self, df: pd.DataFrame) -> list[str]:
        """The single predictor (a contemporaneous composite), always ``returns_pts``."""
        return ["returns_pts"]

    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """Player rows (minutes>0, DGW excluded) with the same-match ``returns_pts`` + realized bonus.

        Mirrors ``walk_forward_bonus`` so the calibration reproduces its output. Sorting is cosmetic — the
        per-(position, gw) OLS is order-independent.
        """
        df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
        df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
        df["returns_pts"] = returns_points(df)
        df["bonus_actual"] = pd.to_numeric(df["bonus"], errors="coerce")
        return df

    def check_assumptions(self, prepared: pd.DataFrame) -> AssumptionReport:
        """Gaussian OLS calibration: report the proxy strength (returns_pts↔bonus) + enough rows."""
        complete = prepared.dropna(subset=["returns_pts", self.target])
        rho = grouped_spearman(complete, "returns_pts", self.target, ["gw", "position"], MIN_ROWS_PER_POS)
        detectable = len(complete) >= MIN_BONUS_TRAIN_ROWS
        note = "" if detectable else f"under detectability floor: {len(complete)} rows"
        disp = {"family": "gaussian_ols", "family_ok": True, "proxy_spearman": round(float(rho), 4)}
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    def fit(self, mart: pd.DataFrame) -> Fitted:
        """Expanding walk-forward per-position OLS -> ``e_bonus`` (+ per-(position, gw) intercept/slope)."""
        df = self.population(mart)
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        coeffs = []
        for pos in POSITIONS:
            sdf = df[df["position"] == pos]
            for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
                tr = sdf[sdf["gw"] < t].dropna(subset=["returns_pts", self.target])
                te = sdf[sdf["gw"] == t]
                if len(tr) < MIN_BONUS_TRAIN_ROWS or te.empty:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        x = sm.add_constant(tr[["returns_pts"]].to_numpy(float), has_constant="add")
                        res = sm.OLS(tr[self.target].to_numpy(float), x).fit()
                        xte = sm.add_constant(te[["returns_pts"]].to_numpy(float), has_constant="add")
                        pred.loc[te.index] = np.clip(res.predict(xte), 0.0, self.clip_max)
                        coeffs.append({"position": pos, "gw": int(t),
                                       "intercept": float(res.params[0]), "slope": float(res.params[1])})
                    except Exception:
                        continue
        return Fitted(name=self.name, predictions=pred, features=("returns_pts",),
                      meta={"variant": self.variant, "coefficients": pd.DataFrame(coeffs)})

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The scored view — one term (``bonus``): calibrated E[bonus] per row."""
        return {self.term: fitted.predictions.to_numpy()}


class BonusTerm:
    """The bonus term — calibrated E[bonus] scored vs the ``returns_pts`` signal (spec §5, all positions).

    The gate is a **calibration** check: the proxy preserves the ``returns_pts`` ranking by construction,
    so proxy rho == signal rho — the fit sets magnitude, not order. Recorded honestly, not as a ranking win.
    """

    name = "bonus"
    baseline_col = "returns_pts"
    view_col = "e_bonus"

    def __init__(self, model: BonusModel | None = None) -> None:
        self.model = model or BonusModel()

    def _scored_rows(self, mart: pd.DataFrame, fitted: Fitted) -> pd.DataFrame:
        df = self.model.population(mart)
        df[self.view_col] = fitted.predictions
        return df[(df["gw"] > WARMUP_GW) & df[self.view_col].notna()]

    def validate(self, mart: pd.DataFrame) -> GateResult:
        """Within-position Spearman of E[bonus] vs realized bonus, beside the raw ``returns_pts`` signal."""
        target = self.model.target
        fitted = self.model.fit(mart)
        ev = self._scored_rows(mart, fitted)
        rows, passed = [], {}
        for pos in POSITIONS:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            r_model = grouped_spearman(sub, self.view_col, target, ["gw"], MIN_ROWS_PER_POS)
            r_base = grouped_spearman(sub, self.baseline_col, target, ["gw"], MIN_ROWS_PER_POS)
            rows.append({"position": pos, "baseline": round(r_base, 4), self.view_col: round(r_model, 4),
                         "delta": round(r_model - r_base, 4), "n_gw": int(sub["gw"].nunique())})
            passed[pos] = r_model >= r_base   # calibration preserves ranking => parity is a pass
        table = pd.DataFrame(rows)
        if not table.empty:
            table["position"] = pd.Categorical(table["position"], categories=POSITIONS, ordered=True)
            table = table.sort_values("position").reset_index(drop=True)
        return GateResult(term=self.name, table=table, passed=passed)

    def diagnose(self, mart: pd.DataFrame) -> Diagnostics:
        """Residuals (worst-missed bonus rows) + the per-(position, gw) calibration coefficients."""
        target = self.model.target
        fitted = self.model.fit(mart)
        ev = self._scored_rows(mart, fitted).copy()
        ev["abs_resid"] = (ev[target] - ev[self.view_col]).abs()
        residuals = (ev.sort_values("abs_resid", ascending=False)
                       .loc[:, ["player_id", "gw", "position", target, self.view_col, "returns_pts", "abs_resid"]]
                       .head(20).reset_index(drop=True))
        # "ablation" here is the calibration itself — the fitted slope/intercept per position over time.
        return Diagnostics(term=self.name, residuals=residuals, ablation=fitted.meta["coefficients"])
