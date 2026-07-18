"""Shared machinery for single-term Poisson components at ``player_gw`` grain (spec §0-A: DRY).

``goals``, ``assists`` (and later ``saves``) are the *same model shape* — a Poisson GLM of a count
target on lagged process stats, fit expanding walk-forward, emitting one term scored against the
player's own lagged mean of that count. Rather than copy that shape per term, it is written **once**
here and each term subclass declares only what differs: its ``target`` column, ``pool``, emit ``term``
name, and (for the Term) its ``baseline_col`` / ``view_col``.

This keeps every count component byte-identical to the god-file it strangles (the subclasses add no
logic, only data), so the frozen-number golden tests keep passing across the refactor.
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
from model.forecast.count_models import diagnose_overdispersion
from model.terms._base import (
    AssumptionReport,
    Diagnostics,
    Fitted,
    GateResult,
    Hypothesis,
)

_ELASTICNET_ALPHA = 0.0  # L1/L2 penalty for the selected draw; 0.0 ⇒ ≡ unregularized MLE today
_ELASTICNET_L1 = 0.5


def _design(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Intercept + features design matrix (float; NaNs handled by the caller's dropna)."""
    return sm.add_constant(df[features].to_numpy(dtype=float), has_constant="add")


class PoissonPlayerComponentModel:
    """A Poisson GLM of one count target on lagged process stats, player-GW grain (the fittable unit).

    Subclasses set the class attributes ``name``, ``target``, ``term``, ``pool`` (and optionally
    ``hypotheses``); everything else — the minimal/selected draw, walk-forward fit, dispersion +
    detectability pre-fit, single-term emit — is shared.
    """

    grain = "player_gw"
    family = staticmethod(sm.families.Poisson)

    # Fit guards — carried over verbatim from the god-files so predictions reproduce to the bit. Class
    # attributes so a subclass whose population changes the row scale can adjust them (e.g. GK-only
    # ``saves`` lowers ``min_train_rows_total`` to match the god-file's effective inner GK guard).
    min_train_rows_per_fit: ClassVar[int] = 30   # per feature-complete training slice, else emit NaN
    min_train_rows_total: ClassVar[int] = 100    # skip an eval GW whose expanding train is still too small
    # Detectability floor (pre-fit): a Poisson mean is only learnable away from zero with enough positive
    # events; below this the slice is under-powered and a null is *inconclusive*, not a licence to abandon.
    min_positive_events: ClassVar[int] = 10

    # -- subclass declares these ------------------------------------------------------------
    name: ClassVar[str]
    target: ClassVar[str]                    # the count column to predict
    term: ClassVar[str]                      # the emit key (the single term this model produces)
    pool: ClassVar[FeaturePool]
    hypotheses: ClassVar[tuple[Hypothesis, ...]] = ()

    def __init__(
        self, variant: Literal["minimal", "selected"] = "minimal",
        feature_override: list[str] | None = None,
    ) -> None:
        if variant not in ("minimal", "selected"):
            raise ValueError(f"unknown variant {variant!r}")
        self.variant = variant
        self._feature_override = feature_override  # ablation uses this to fit on a feature subset

    # -- feature resolution ------------------------------------------------------------------
    def features(self, mart: pd.DataFrame) -> list[str]:
        """Design columns this variant draws — restricted to what is materializable today.

        ``minimal`` is the fixed mechanistic subset. ``selected`` regularizes over the full pool, but
        only materialized mart columns can be drawn (the §3 forward-agenda candidates raise in
        ``build.materialize`` until built). An explicit ``feature_override`` (ablation) wins.
        """
        if self._feature_override is not None:
            return [f for f in self._feature_override if f in mart.columns]
        if self.variant == "minimal":
            return list(self.pool.minimal)
        return [f.name for f in self.pool.candidates if f.name in mart.columns]

    # -- population --------------------------------------------------------------------------
    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """The v1 population: ``minutes > 0``, DGW excluded, sorted (player, gw) — shared contract."""
        df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
        return df.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # -- pre-fit (spec §4 stage 1) -----------------------------------------------------------
    def check_assumptions(self, train: pd.DataFrame) -> AssumptionReport:
        """Dispersion (is Poisson justified?) + detectability floor (learnable at this N?)."""
        disp = dict(diagnose_overdispersion(train[self.target]))
        # Poisson is justified on *material* dispersion (index ~1, "near-Poisson, Gate 1"), not on the
        # n-sensitive LRT — with thousands of rows the LRT recommends NB even at index ~1.06 (≈ Poisson).
        disp["family_ok"] = not bool(disp.get("material_overdispersion", False))
        feats = self.features(train)
        complete = train.dropna(subset=[*feats, self.target])
        events = int((complete[self.target] > 0).sum())
        detectable = len(complete) >= self.min_train_rows_per_fit and events >= self.min_positive_events
        note = "" if detectable else f"under detectability floor: {events} positive events, {len(complete)} rows"
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    # -- fit + emit (spec §4 stages 2-3) -----------------------------------------------------
    def _fit_predict(self, train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Fit on train, predict E[target] for test. NaN vector on a thin/degenerate slice.

        ``minimal`` fits an unregularized Poisson MLE (the frozen god-file path). ``selected`` uses
        ``fit_regularized`` (elastic net); with the penalty at 0 this is the same MLE, so nothing that
        is *shipped* moves — the regularized path is infrastructure for the future wider pool.
        """
        tr = train.dropna(subset=[*features, self.target])
        if len(tr) < self.min_train_rows_per_fit or tr[self.target].nunique() < 2:
            return np.full(len(test), np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                glm = sm.GLM(tr[self.target].to_numpy(dtype=float), _design(tr, features),
                             family=sm.families.Poisson())
                res = (glm.fit() if self.variant == "minimal"
                       else glm.fit_regularized(alpha=_ELASTICNET_ALPHA, L1_wt=_ELASTICNET_L1))
                return res.predict(_design(test, features))
            except Exception:
                return np.full(len(test), np.nan)

    def fit(self, mart: pd.DataFrame) -> Fitted:
        """Expanding walk-forward → E[target] per population row (NaN pre-warmup / on thin slices).

        Lag-safety is a **build/CI property** (``features.build.assert_lag_safe``, spec §4 stage 0), not
        a fit-time guard — the mart's declared ``*_roll`` inputs already exclude the current GW.
        """
        df = self.population(mart)
        features = self.features(df)
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
            train, test = df[df["gw"] < t], df[df["gw"] == t]
            if test.empty or len(train) < self.min_train_rows_total:
                continue
            pred.loc[test.index] = self._fit_predict(train, test, features)
        return Fitted(name=self.name, predictions=pred, features=tuple(features),
                      meta={"variant": self.variant, "population_index": df.index})

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The scored view this model produces — one term (``self.term``): E[target] per row."""
        return {self.term: fitted.predictions.to_numpy()}


class PlayerComponentTerm:
    """A count term scored vs its own lagged-mean baseline (spec §5, per-term level).

    Subclasses set ``name``, ``baseline_col`` and ``view_col``; the model supplies the ``target`` column.
    """

    name: ClassVar[str]
    baseline_col: ClassVar[str]              # the naive bar: the player's lagged expanding mean target
    view_col: ClassVar[str]                  # the model-prediction column label in the gate table
    _model_cls: ClassVar[type[PoissonPlayerComponentModel]]
    default_variant: ClassVar[Literal["minimal", "selected"]] = "minimal"

    def __init__(self, model: PoissonPlayerComponentModel | None = None) -> None:
        self.model = model or self._model_cls(variant=self.default_variant)

    def _with_baseline(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attach the per-term baseline: the player's strictly-prior expanding mean target (lag-safe)."""
        df = df.copy()
        df[self.baseline_col] = (
            df.groupby("player_id")[self.model.target].transform(lambda s: s.expanding().mean().shift(1))
        )
        return df

    def validate(self, mart: pd.DataFrame) -> GateResult:
        """Within-position Spearman of E[target] vs the lagged-mean baseline at ranking next-GW target.

        Per-term gate (spec §5): does the *signal-based* model out-rank the term's own naive history?
        Scored on the common eval set (both columns defined), per position.
        """
        target = self.model.target
        fitted = self.model.fit(mart)
        df = self._with_baseline(self.model.population(mart))
        df[self.view_col] = fitted.predictions
        ev = df[df["gw"] > WARMUP_GW].dropna(subset=[self.view_col, self.baseline_col])
        rows, passed = [], {}
        for pos in POSITIONS:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            r_base = grouped_spearman(sub, self.baseline_col, target, ["gw"], MIN_ROWS_PER_POS)
            r_model = grouped_spearman(sub, self.view_col, target, ["gw"], MIN_ROWS_PER_POS)
            rows.append({"position": pos, "baseline": round(r_base, 4), self.view_col: round(r_model, 4),
                         "delta": round(r_model - r_base, 4), "n_gw": int(sub["gw"].nunique())})
            passed[pos] = r_model > r_base
        table = pd.DataFrame(rows)
        if not table.empty:
            table["position"] = pd.Categorical(table["position"], categories=POSITIONS, ordered=True)
            table = table.sort_values("position").reset_index(drop=True)
        return GateResult(term=self.name, table=table, passed=passed)

    def diagnose(self, mart: pd.DataFrame) -> Diagnostics:
        """Post-gate residual + ablation report (spec §4 stage 5).

        Residuals: the worst-missed (player, GW) rows by abs(target - E[target]). Ablation: drop each
        design feature, re-score, and report the Spearman it cost — the *measured* contribution.
        """
        target = self.model.target
        fitted = self.model.fit(mart)
        df = self.model.population(mart)
        df[self.view_col] = fitted.predictions
        ev = df[df["gw"] > WARMUP_GW].dropna(subset=[self.view_col]).copy()
        ev["abs_resid"] = (ev[target] - ev[self.view_col]).abs()
        residuals = (ev.sort_values("abs_resid", ascending=False)
                       .loc[:, ["player_id", "gw", "position", target, self.view_col, "abs_resid"]]
                       .head(20).reset_index(drop=True))

        full_feats = self.model.features(mart)
        full = grouped_spearman(ev, self.view_col, target, ["gw", "position"], MIN_ROWS_PER_POS)
        abl_rows = []
        for drop in full_feats:
            kept = [f for f in full_feats if f != drop]
            if not kept:
                continue
            m = type(self.model)(variant=self.model.variant, feature_override=kept)
            sub = self.model.population(mart)
            sub[self.view_col] = m.fit(mart).predictions
            sub = sub[sub["gw"] > WARMUP_GW].dropna(subset=[self.view_col])
            r = grouped_spearman(sub, self.view_col, target, ["gw", "position"], MIN_ROWS_PER_POS)
            abl_rows.append({"dropped": drop, "spearman": round(r, 4), "delta_vs_full": round(r - full, 4)})
        return Diagnostics(term=self.name, residuals=residuals, ablation=pd.DataFrame(abl_rows))
