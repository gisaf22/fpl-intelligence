"""The goals Model + Term (spec §2) — strangled from ``component_forecast.py``, no behaviour change.

``GoalsModel`` fits ``goals_scored`` one gameweek ahead with a Poisson GLM on lagged process stats,
expanding walk-forward (fit on ``gw < t``). Two draws from ``GOALS_POOL`` (spec §3):

* **minimal** — ``xgi_roll3 + minutes_roll3``, unregularized ``statsmodels`` GLM. This *is* the
  god-file's goals design; it is both the fast smoke-test and the comparison **bar**. The golden test
  pins its ``emit`` bit-identical to ``component_forecast`` on a fixed panel (the 4dp reproduction).
* **selected** — regularized (``fit_regularized``, elastic net) over the full materializable pool; the
  shipped model once the §3 opponent-forward / team-context features exist. Today only the two
  mechanistic columns are on the mart, so *selected draws the same design as minimal* and is not yet
  wired into ``compose`` — the frozen composed numbers are untouched.

``GoalsTerm`` scores the emitted E[goals] against the term's **own** baseline — a player's lagged
mean goals (spec §5, per-term level: "is this term predictable from signals?"), never the composed
points average.
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

from model.eval.metrics import grouped_spearman
from model.eval.walkforward import MIN_ROWS_PER_POS, POSITIONS, WARMUP_GW
from model.forecast.count_models import diagnose_overdispersion
from model.terms._base import (
    AssumptionReport,
    Diagnostics,
    Fitted,
    GateResult,
    Hypothesis,
)
from model.terms.goals.spec import GOALS_POOL, GRAIN

# Fit guards — carried over verbatim from the god-file so predictions reproduce to the bit.
_MIN_TRAIN_ROWS_PER_FIT = 30   # per (feature-complete) training slice, else emit NaN for that GW
_MIN_TRAIN_ROWS_TOTAL = 100    # skip an eval GW whose expanding train is still too small
# Detectability floor (pre-fit): a Poisson mean is only learnable away from zero with enough
# positive events; below this the slice is under-powered and a null would be *inconclusive*.
_MIN_POSITIVE_EVENTS = 10

_ELASTICNET_ALPHA = 0.0  # L1/L2 penalty for the selected draw; 0.0 ⇒ ≡ unregularized MLE today
_ELASTICNET_L1 = 0.5


def _design(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Intercept + features design matrix (float; NaNs handled by the caller's dropna)."""
    return sm.add_constant(df[features].to_numpy(dtype=float), has_constant="add")


class GoalsModel:
    """Poisson GLM of next-GW ``goals_scored`` on lagged process stats (the fittable unit)."""

    grain = GRAIN
    pool = GOALS_POOL
    family = staticmethod(sm.families.Poisson)

    def __init__(
        self, variant: Literal["minimal", "selected"] = "minimal",
        feature_override: list[str] | None = None,
    ) -> None:
        if variant not in ("minimal", "selected"):
            raise ValueError(f"unknown variant {variant!r}")
        self.variant = variant
        self._feature_override = feature_override  # ablation uses this to fit on a feature subset
        self.name = "goals"
        self.hypotheses = (
            Hypothesis(
                claim="lagged xG+xA ranks next-GW goals better than a player's lagged goals mean",
                test="within-position Spearman of emitted E[goals] vs goals_prior, GW>3, common eval set",
                success_threshold="Δ Spearman > 0 at DEF and MID (the rankable attacking positions)",
                status="supported (phase2: DEF +0.026, MID +0.043, FWD +0.013)",
            ),
        )

    # -- feature resolution ------------------------------------------------------------------
    def features(self, mart: pd.DataFrame) -> list[str]:
        """The design columns this variant draws — restricted to what is materializable today.

        ``minimal`` is the fixed mechanistic pair. ``selected`` would regularize over the whole pool,
        but only materialized mart columns can be drawn, so today it resolves to the same two columns
        (the §3 opponent-forward / team-context candidates raise in ``build.materialize`` until built).
        An explicit ``feature_override`` (ablation) wins, restricted to materializable columns.
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
        disp = dict(diagnose_overdispersion(train["goals_scored"]))
        # Poisson is justified on *material* dispersion (index ~1, "near-Poisson, Gate 1"), not on the
        # n-sensitive LRT — with thousands of rows the LRT recommends NB even at index ~1.06 (≈ Poisson).
        disp["family_ok"] = not bool(disp.get("material_overdispersion", False))
        feats = self.features(train)
        complete = train.dropna(subset=[*feats, "goals_scored"])
        events = int((complete["goals_scored"] > 0).sum())
        detectable = len(complete) >= _MIN_TRAIN_ROWS_PER_FIT and events >= _MIN_POSITIVE_EVENTS
        note = "" if detectable else f"under detectability floor: {events} positive events, {len(complete)} rows"
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    # -- fit + emit (spec §4 stages 2-3) -----------------------------------------------------
    def _fit_predict(self, train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Fit on train, predict E[goals] for test. NaN vector on a thin/degenerate slice.

        ``minimal`` fits an unregularized Poisson MLE (the frozen god-file path). ``selected`` uses
        ``fit_regularized`` (elastic net); with the penalty at 0 this is the same MLE, so nothing that
        is *shipped* moves — the regularized path is infrastructure for the future wider pool.
        """
        tr = train.dropna(subset=[*features, "goals_scored"])
        if len(tr) < _MIN_TRAIN_ROWS_PER_FIT or tr["goals_scored"].nunique() < 2:
            return np.full(len(test), np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                glm = sm.GLM(tr["goals_scored"].to_numpy(dtype=float), _design(tr, features),
                             family=sm.families.Poisson())
                res = (glm.fit() if self.variant == "minimal"
                       else glm.fit_regularized(alpha=_ELASTICNET_ALPHA, L1_wt=_ELASTICNET_L1))
                return res.predict(_design(test, features))
            except Exception:
                return np.full(len(test), np.nan)

    def fit(self, mart: pd.DataFrame) -> Fitted:
        """Expanding walk-forward → E[goals] per population row (NaN pre-warmup / on thin slices).

        Lag-safety is a **build/CI property** (:func:`model.features.build.assert_lag_safe`, spec §4
        stage 0), not a fit-time guard — the mart's declared ``*_roll`` inputs are already verified to
        exclude the current GW, so ``fit`` trusts them and does not re-derive the check per call.
        """
        df = self.population(mart)
        features = self.features(df)
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
            train, test = df[df["gw"] < t], df[df["gw"] == t]
            if test.empty or len(train) < _MIN_TRAIN_ROWS_TOTAL:
                continue
            pred.loc[test.index] = self._fit_predict(train, test, features)
        return Fitted(name=self.name, predictions=pred, features=tuple(features),
                      meta={"variant": self.variant, "population_index": df.index})

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The scored views this model produces — one term (``goals``): E[goals] per row."""
        return {"goals": fitted.predictions.to_numpy()}


class GoalsTerm:
    """The ``goals`` term — E[goals] scored vs its own lagged-goals baseline (spec §5, per-term)."""

    name = "goals"
    baseline_col = "goals_prior"

    def __init__(self, model: GoalsModel | None = None) -> None:
        self.model = model or GoalsModel(variant="minimal")

    @staticmethod
    def _with_baseline(df: pd.DataFrame) -> pd.DataFrame:
        """Attach the per-term baseline: a player's strictly-prior expanding mean goals (lag-safe)."""
        df = df.copy()
        df["goals_prior"] = (
            df.groupby("player_id")["goals_scored"].transform(lambda s: s.expanding().mean().shift(1))
        )
        return df

    def validate(self, mart: pd.DataFrame) -> GateResult:
        """Within-position Spearman of E[goals] vs ``goals_prior`` at ranking next-GW goals (GW>3).

        Per-term gate (spec §5): does the *signal-based* model out-rank the term's own naive history?
        Scored on the common eval set (both columns defined), the rankable attacking positions.
        """
        fitted = self.model.fit(mart)
        df = self.model.population(mart)
        df = self._with_baseline(df)
        df["e_goals"] = fitted.predictions
        ev = df[df["gw"] > WARMUP_GW].dropna(subset=["e_goals", "goals_prior"])
        rows, passed = [], {}
        for pos in POSITIONS:
            sub = ev[ev["position"] == pos]
            if sub.empty:
                continue
            r_base = grouped_spearman(sub, "goals_prior", "goals_scored", ["gw"], MIN_ROWS_PER_POS)
            r_model = grouped_spearman(sub, "e_goals", "goals_scored", ["gw"], MIN_ROWS_PER_POS)
            rows.append({"position": pos, "baseline": round(r_base, 4), "e_goals": round(r_model, 4),
                         "delta": round(r_model - r_base, 4), "n_gw": int(sub["gw"].nunique())})
            passed[pos] = r_model > r_base
        table = pd.DataFrame(rows)
        if not table.empty:
            table["position"] = pd.Categorical(table["position"], categories=POSITIONS, ordered=True)
            table = table.sort_values("position").reset_index(drop=True)
        return GateResult(term=self.name, table=table, passed=passed)

    def diagnose(self, mart: pd.DataFrame) -> Diagnostics:
        """Post-gate residual + ablation report (spec §4 stage 5).

        Residuals: the worst-missed (player, GW) rows by abs(goals - E[goals]). Ablation: drop each design
        feature, re-score, and report the Spearman it cost — the *measured* contribution (vs inferred).
        """
        fitted = self.model.fit(mart)
        df = self.model.population(mart)
        df["e_goals"] = fitted.predictions
        ev = df[df["gw"] > WARMUP_GW].dropna(subset=["e_goals"]).copy()
        ev["abs_resid"] = (ev["goals_scored"] - ev["e_goals"]).abs()
        residuals = (ev.sort_values("abs_resid", ascending=False)
                       .loc[:, ["player_id", "gw", "position", "goals_scored", "e_goals", "abs_resid"]]
                       .head(20).reset_index(drop=True))

        full_feats = self.model.features(mart)
        full = grouped_spearman(ev.dropna(subset=["e_goals"]), "e_goals", "goals_scored",
                                ["gw", "position"], MIN_ROWS_PER_POS)
        abl_rows = []
        for drop in full_feats:
            kept = [f for f in full_feats if f != drop]
            if not kept:
                continue
            m = GoalsModel(variant=self.model.variant, feature_override=kept)
            sub = self.model.population(mart)
            sub["e_goals"] = m.fit(mart).predictions
            sub = sub[sub["gw"] > WARMUP_GW].dropna(subset=["e_goals"])
            r = grouped_spearman(sub, "e_goals", "goals_scored", ["gw", "position"], MIN_ROWS_PER_POS)
            abl_rows.append({"dropped": drop, "spearman": round(r, 4), "delta_vs_full": round(r - full, 4)})
        ablation = pd.DataFrame(abl_rows)
        return Diagnostics(term=self.name, residuals=residuals, ablation=ablation)
