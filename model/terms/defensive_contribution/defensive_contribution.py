"""The defensive-contribution Model + Term (spec §2) — strangled from ``points_model.walk_forward_dc``.

DC scores +2 when a player clears their position's action threshold (DEF ≥ 10 CBIT; MID/FWD ≥ 12 CBIRT;
GK exempt). Per D-A, DC is conditionally independent of conceding/CS given minutes, so it is a
**standalone** component: a **logistic** GLM of the derived binary ``dc_hit`` on lagged DC-action form +
minutes + fixture context, fit **per position** (thresholds and dynamics differ), then
``E[DC points] = DC_POINTS x P(hit)``.

This is a different shape from the Poisson-player terms (binomial family, derived target, per-position
fit, baseline = a lagged action count), so it is written standalone here — cleanly factored (``_prepare``
/ ``_fit_predict`` / per-position loop) so a shared ``BinaryPerPositionComponent`` base can be lifted out
mechanically once ``minutes`` (the second logistic term) confirms the shape. ``selected`` (the full pool)
reproduces ``walk_forward_dc`` to the bit; the xDC_POINTS conversion is a compose-layer concern, so the
term emits the raw ``P(hit)``.
"""

from __future__ import annotations

import warnings
from typing import ClassVar, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

from domain.fpl_scoring import (
    DC_CBIRT_THRESHOLD_MID_FWD,
    DC_CBIT_THRESHOLD_DEF,
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
from model.terms.defensive_contribution.spec import DC_POOL, GRAIN

# Per-position DC-action thresholds (GK exempt — no DC term). Carried from the god-file verbatim.
_DC_THRESHOLD = {"DEF": DC_CBIT_THRESHOLD_DEF, "MID": DC_CBIRT_THRESHOLD_MID_FWD, "FWD": DC_CBIRT_THRESHOLD_MID_FWD}
_DC_POSITIONS = ("DEF", "MID", "FWD")

MIN_DC_TRAIN_ROWS = 50   # per-position expanding-train guard (else that GW is left NaN)
_MIN_DC_HITS = 20        # detectability floor: enough positive (threshold-clearing) events to learn P(hit)


def _lag_roll(df: pd.DataFrame, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per player (shift(1) before rolling -> excludes current row)."""
    return df.groupby("player_id")[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


def _design(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Intercept + features design matrix (float; NaNs handled by the caller's dropna)."""
    return sm.add_constant(df[features].to_numpy(dtype=float), has_constant="add")


class DefensiveContributionModel:
    """Per-position logistic GLM of ``dc_hit`` on lagged DC form + context (the fittable unit)."""

    grain = GRAIN
    pool = DC_POOL
    family = staticmethod(sm.families.Binomial)
    name = "defensive_contribution"
    term = "defensive_contribution"
    target = "dc_hit"                        # DERIVED binary target (built in _prepare)
    baseline_feature = "dc_roll3"            # the term's naive bar (a lagged action count, already a feature)
    hypotheses: ClassVar[tuple[Hypothesis, ...]] = (
        Hypothesis(
            claim="modelled P(DC hit) ranks realized DC hits better than the lagged DC-action count",
            test="within-position Spearman of p_dc_hit vs dc_hit beside dc_roll3, GW>3, DEF/MID/FWD",
            success_threshold="Δ Spearman > 0 at DEF (where DC is most material)",
            status="supported (phase3 DC component)",
        ),
    )

    def __init__(
        self, variant: Literal["minimal", "selected"] = "selected",
        feature_override: list[str] | None = None,
    ) -> None:
        if variant not in ("minimal", "selected"):
            raise ValueError(f"unknown variant {variant!r}")
        self.variant = variant
        self._feature_override = feature_override

    # -- feature resolution ------------------------------------------------------------------
    def features(self, df: pd.DataFrame) -> list[str]:
        """Design columns this variant draws (restricted to materializable columns after ``_prepare``)."""
        if self._feature_override is not None:
            return [f for f in self._feature_override if f in df.columns]
        if self.variant == "minimal":
            return list(self.pool.minimal)
        return [f.name for f in self.pool.candidates if f.name in df.columns]

    # -- population + derived target ---------------------------------------------------------
    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """DEF/MID/FWD rows (minutes>0, DGW excluded) with lagged DC form + the derived ``dc_hit`` target.

        Mirrors ``points_model._add_dc_columns`` exactly so the selected draw reproduces its output. GK are
        excluded (no DC term); the per-player rolls are unaffected by that filter.
        """
        df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))
                  & (mart["position"].isin(_DC_POSITIONS))].copy()
        df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
        for c in ["defensive_contribution", "minutes_roll3", "fdr_avg"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["was_home"] = df["was_home"].astype(float)
        for w in (3, 5):
            df[f"dc_roll{w}"] = _lag_roll(df, "defensive_contribution", w)
        df["dc_threshold"] = df["position"].map(_DC_THRESHOLD)
        df["dc_hit"] = (df["defensive_contribution"] >= df["dc_threshold"]).astype(float)
        return df

    # -- pre-fit (spec §4 stage 1) -----------------------------------------------------------
    def check_assumptions(self, prepared: pd.DataFrame) -> AssumptionReport:
        """Binary term: family is logistic by construction; the floor is class balance + enough hits."""
        feats = self.features(prepared)
        complete = prepared.dropna(subset=[*feats, self.target])
        hits = int((complete[self.target] > 0).sum())
        hit_rate = float(complete[self.target].mean()) if len(complete) else float("nan")
        both_classes = complete[self.target].nunique() >= 2
        detectable = len(complete) >= MIN_DC_TRAIN_ROWS and hits >= _MIN_DC_HITS and both_classes
        note = "" if detectable else f"under detectability floor: {hits} hits, {len(complete)} rows"
        disp = {"family": "binomial", "family_ok": both_classes, "hit_rate": round(hit_rate, 4), "n_hits": hits}
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    # -- fit + emit (spec §4 stages 2-3) -----------------------------------------------------
    def _fit_predict(self, train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Fit a logistic GLM on one position's train, predict P(hit) for test. NaN on a thin slice."""
        tr = train.dropna(subset=[*features, self.target])
        if len(tr) < MIN_DC_TRAIN_ROWS or tr[self.target].nunique() < 2 or test.empty:
            return np.full(len(test), np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = sm.GLM(tr[self.target].to_numpy(float), _design(tr, features),
                            family=sm.families.Binomial()).fit()
                return res.predict(_design(test, features))
            except Exception:
                return np.full(len(test), np.nan)

    def fit(self, mart: pd.DataFrame) -> Fitted:
        """Expanding walk-forward, **per position** -> P(DC hit) per row (NaN pre-warmup / thin slices)."""
        df = self.population(mart)
        features = self.features(df)
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        for pos in _DC_POSITIONS:
            sdf = df[df["position"] == pos]
            for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
                train, test = sdf[sdf["gw"] < t], sdf[sdf["gw"] == t]
                if test.empty:
                    continue
                pred.loc[test.index] = self._fit_predict(train, test, features)
        return Fitted(name=self.name, predictions=pred, features=tuple(features),
                      meta={"variant": self.variant, "population_index": df.index})

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The scored view — one term: ``P(DC hit)`` per row (xDC_POINTS is a compose-layer step)."""
        return {self.term: fitted.predictions.to_numpy()}


class DefensiveContributionTerm:
    """The DC term — P(hit) scored vs the lagged DC-action count baseline (spec §5, DEF/MID/FWD)."""

    name = "defensive_contribution"
    baseline_col = "dc_roll3"
    view_col = "p_dc_hit"

    def __init__(self, model: DefensiveContributionModel | None = None) -> None:
        self.model = model or DefensiveContributionModel(variant="selected")

    def _scored_rows(self, mart: pd.DataFrame, fitted: Fitted) -> pd.DataFrame:
        df = self.model.population(mart)
        df[self.view_col] = fitted.predictions
        return df[(df["gw"] > WARMUP_GW) & df[self.view_col].notna()]

    def validate(self, mart: pd.DataFrame) -> GateResult:
        """Within-position Spearman of P(hit) vs the lagged ``dc_roll3`` count at ranking realized hits."""
        target = self.model.target
        fitted = self.model.fit(mart)
        ev = self._scored_rows(mart, fitted)
        rows, passed = [], {}
        for pos in _DC_POSITIONS:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            r_model = grouped_spearman(sub, self.view_col, target, ["gw"], MIN_ROWS_PER_POS)
            r_base = grouped_spearman(sub.dropna(subset=[self.baseline_col]), self.baseline_col, target,
                                      ["gw"], MIN_ROWS_PER_POS)
            rows.append({"position": pos, "baseline": round(r_base, 4), self.view_col: round(r_model, 4),
                         "delta": round(r_model - r_base, 4), "hit_rate": round(float(sub[target].mean()), 3),
                         "n_gw": int(sub["gw"].nunique())})
            passed[pos] = r_model > r_base
        table = pd.DataFrame(rows)
        if not table.empty:
            table["position"] = pd.Categorical(table["position"], categories=POSITIONS, ordered=True)
            table = table.sort_values("position").reset_index(drop=True)
        return GateResult(term=self.name, table=table, passed=passed)

    def diagnose(self, mart: pd.DataFrame) -> Diagnostics:
        """Residuals (worst-missed hits) + per-feature ablation on the DC ranking (post-gate)."""
        target = self.model.target
        fitted = self.model.fit(mart)
        ev = self._scored_rows(mart, fitted).copy()
        ev["abs_resid"] = (ev[target] - ev[self.view_col]).abs()
        residuals = (ev.sort_values("abs_resid", ascending=False)
                       .loc[:, ["player_id", "gw", "position", target, self.view_col, "abs_resid"]]
                       .head(20).reset_index(drop=True))
        full_feats = self.model.features(self.model.population(mart))
        rows = []
        for drop in full_feats:
            kept = [f for f in full_feats if f != drop]
            if not kept:
                continue
            m = DefensiveContributionModel(variant=self.model.variant, feature_override=kept)
            sub = self._scored_rows(mart, m.fit(mart))
            r = grouped_spearman(sub, self.view_col, target, ["gw", "position"], MIN_ROWS_PER_POS)
            rows.append({"dropped": drop, "spearman": round(r, 4)})
        return Diagnostics(term=self.name, residuals=residuals, ablation=pd.DataFrame(rows))
