"""Shared machinery for per-position logistic binary components (spec §0-A: DRY).

``defensive_contribution`` and ``minutes`` are the same shape — a logistic GLM of a **derived binary**
target, fit **per position** expanding walk-forward, one term scored against a lagged baseline column.
The rule of three held once ``minutes`` confirmed it, so the shape is written once here; each subclass
declares only its ``target``/``pool``/``term`` (+ baseline / view columns) and, if a position needs a
non-logistic estimator (GK play60 is near-constant), overrides :meth:`_fill_special`.

Sibling of :mod:`model.terms._poisson_component` — a *different family* (binomial vs Poisson) with a
*different baseline convention* (an existing column vs the player's lagged mean of the target), which is
why the two are separate bases rather than one.
"""

from __future__ import annotations

import warnings
from typing import ClassVar, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

from model.eval.metrics import grouped_spearman
from model.eval.walkforward import MIN_ROWS_PER_POS, POSITIONS, WARMUP_GW
from model.features.spec import FeaturePool
from model.terms._base import (
    AssumptionReport,
    Diagnostics,
    Fitted,
    GateResult,
    Hypothesis,
)


def _design(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Intercept + features design matrix (float; NaNs handled by the caller's dropna)."""
    return sm.add_constant(df[features].to_numpy(dtype=float), has_constant="add")


class BinaryPerPositionComponent:
    """A per-position logistic GLM of a derived binary target (the fittable unit).

    Subclasses set ``name``/``target``/``term``/``pool`` and implement :meth:`population` (build the
    derived target + any lagged features). ``logit_positions`` are fit by logistic; any other position is
    handled by :meth:`_fill_special` (default no-op), the hook for a robust non-logistic estimator.
    """

    grain = "player_gw"
    family = staticmethod(sm.families.Binomial)

    # Guards carried from the god-files so predictions reproduce to the bit.
    min_train_rows: ClassVar[int] = 50
    min_positive_events: ClassVar[int] = 20     # detectability floor (positive class)
    logit_positions: ClassVar[tuple[str, ...]] = ("DEF", "MID", "FWD")

    # -- subclass declares these ------------------------------------------------------------
    name: ClassVar[str]
    target: ClassVar[str]
    term: ClassVar[str]
    pool: ClassVar[FeaturePool]
    hypotheses: ClassVar[tuple[Hypothesis, ...]] = ()

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
        """Design columns this variant draws (restricted to materializable columns after ``population``)."""
        if self._feature_override is not None:
            return [f for f in self._feature_override if f in df.columns]
        if self.variant == "minimal":
            return list(self.pool.minimal)
        return [f.name for f in self.pool.candidates if f.name in df.columns]

    # -- population + derived target (subclass) ---------------------------------------------
    @staticmethod
    def population(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:  # pragma: no cover - overridden
        """Build the derived target + lagged features. ``keep_all=True`` retains ``minutes==0`` rows for
        ex-ante scoring of the wider universe (train stays ``minutes>0`` in :meth:`fit`)."""
        raise NotImplementedError

    def _fill_special(self, df: pd.DataFrame, pred: pd.Series) -> None:
        """Hook: fill ``pred`` for positions NOT in ``logit_positions`` (default: none). Mutates ``pred``."""
        return

    # -- pre-fit (spec §4 stage 1) -----------------------------------------------------------
    def check_assumptions(self, prepared: pd.DataFrame) -> AssumptionReport:
        """Binary term: family is logistic by construction; the floor is class balance + enough events."""
        feats = self.features(prepared)
        complete = prepared.dropna(subset=[*feats, self.target])
        events = int((complete[self.target] > 0).sum())
        base_rate = float(complete[self.target].mean()) if len(complete) else float("nan")
        both_classes = complete[self.target].nunique() >= 2
        detectable = len(complete) >= self.min_train_rows and events >= self.min_positive_events and both_classes
        note = "" if detectable else f"under detectability floor: {events} events, {len(complete)} rows"
        disp = {"family": "binomial", "family_ok": both_classes, "base_rate": round(base_rate, 4), "n_events": events}
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    # -- fit + emit (spec §4 stages 2-3) -----------------------------------------------------
    def _fit_predict(self, train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Fit a logistic GLM on one position's train, predict P(target=1) for test. NaN on a thin slice."""
        tr = train.dropna(subset=[*features, self.target])
        if len(tr) < self.min_train_rows or tr[self.target].nunique() < 2 or test.empty:
            return np.full(len(test), np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = sm.GLM(tr[self.target].to_numpy(float), _design(tr, features),
                            family=sm.families.Binomial()).fit()
                return res.predict(_design(test, features))
            except Exception:
                return np.full(len(test), np.nan)

    def fit(self, mart: pd.DataFrame, keep_all: bool = False) -> Fitted:
        """Expanding walk-forward per position -> P(target=1) per row; special positions via the hook.

        ``keep_all=True`` widens the population to potential-blank (``minutes==0``) rows but keeps TRAIN
        filtered to ``minutes>0`` (the ``& (minutes>0)`` below) — the fit is identical to the default
        path and only the *prediction* set grows. The train filter is a no-op when ``keep_all=False``.
        """
        df = self.population(mart, keep_all=keep_all)
        features = self.features(df)
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        self._fill_special(df, pred)
        for pos in self.logit_positions:
            sdf = df[df["position"] == pos]
            for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
                train, test = sdf[(sdf["gw"] < t) & (sdf["minutes"] > 0)], sdf[sdf["gw"] == t]
                if test.empty:
                    continue
                pred.loc[test.index] = self._fit_predict(train, test, features)
        return Fitted(name=self.name, predictions=pred, features=tuple(features),
                      meta={"variant": self.variant, "population_index": df.index})

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The scored view — one term (``self.term``): P(target=1) per row (points mapping is compose-layer)."""
        return {self.term: fitted.predictions.to_numpy()}


class BinaryComponentTerm:
    """A binary term scored vs an existing lagged baseline column (spec §5), per position.

    Subclasses set ``name``/``baseline_col``/``view_col``/``_model_cls`` and may narrow ``positions``.
    """

    name: ClassVar[str]
    baseline_col: ClassVar[str]              # an existing lagged column (NOT lagged-mean-of-target)
    view_col: ClassVar[str]                  # the model-prediction column label in the gate table
    _model_cls: ClassVar[type[BinaryPerPositionComponent]]
    positions: ClassVar[tuple[str, ...]] = POSITIONS
    default_variant: ClassVar[Literal["minimal", "selected"]] = "selected"

    def __init__(self, model: BinaryPerPositionComponent | None = None) -> None:
        self.model = model or self._model_cls(variant=self.default_variant)

    def _scored_rows(self, mart: pd.DataFrame, fitted: Fitted) -> pd.DataFrame:
        df = self.model.population(mart)
        df[self.view_col] = fitted.predictions
        return df[(df["gw"] > WARMUP_GW) & df[self.view_col].notna()]

    def validate(self, mart: pd.DataFrame) -> GateResult:
        """Within-position Spearman of the model view vs the lagged baseline at ranking the binary target."""
        target = self.model.target
        fitted = self.model.fit(mart)
        ev = self._scored_rows(mart, fitted)
        rows, passed = [], {}
        for pos in self.positions:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            r_model = grouped_spearman(sub, self.view_col, target, ["gw"], MIN_ROWS_PER_POS)
            r_base = grouped_spearman(sub.dropna(subset=[self.baseline_col]), self.baseline_col, target,
                                      ["gw"], MIN_ROWS_PER_POS)
            rows.append({"position": pos, "baseline": round(r_base, 4), self.view_col: round(r_model, 4),
                         "delta": round(r_model - r_base, 4), "base_rate": round(float(sub[target].mean()), 3),
                         "n_gw": int(sub["gw"].nunique())})
            passed[pos] = r_model > r_base
        table = pd.DataFrame(rows)
        if not table.empty:
            table["position"] = pd.Categorical(table["position"], categories=POSITIONS, ordered=True)
            table = table.sort_values("position").reset_index(drop=True)
        return GateResult(term=self.name, table=table, passed=passed)

    def diagnose(self, mart: pd.DataFrame) -> Diagnostics:
        """Residuals (worst-missed rows) + per-feature ablation on the ranking (post-gate)."""
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
            m = type(self.model)(variant=self.model.variant, feature_override=kept)
            sub = self._scored_rows(mart, m.fit(mart))
            r = grouped_spearman(sub, self.view_col, target, ["gw", "position"], MIN_ROWS_PER_POS)
            rows.append({"dropped": drop, "spearman": round(r, 4)})
        return Diagnostics(term=self.name, residuals=residuals, ablation=pd.DataFrame(rows))
