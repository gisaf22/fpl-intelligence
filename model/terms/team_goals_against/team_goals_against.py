"""The team-goals-against joint Model (spec §2) — strangled from ``points_model.walk_forward_team_ga``.

``TeamGoalsAgainstModel`` fits **one** Poisson mean per team-fixture (``lambda_ga``) expanding
walk-forward, then derives the two mutually-consistent views D-D identified:

* ``clean_sheet`` = ``p_cs = P(GA=0) = exp(-lambda_ga)``
* ``conceded``    = ``e_conceded_pts = E[-floor(GA/2)]`` under ``GA ~ Poisson(lambda_ga)``

``emit`` returns **both** — this is the joint shape (a model emits many terms). Two draws from one pool
(locked decision B, both team_gw Poisson): ``minimal`` = ``ga_roll3`` only (mechanistic bar);
``selected`` = the full materializable pool (``= TEAM_GA_FEATURES``), which reproduces the frozen
``walk_forward_team_ga`` output to the bit (golden test). The clean_sheet / conceded **Terms** (which
broadcast these team-grain views to players and gate them) land in the next commit.
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import poisson

from model.eval.walkforward import WARMUP_GW
from model.forecast.count_models import diagnose_overdispersion
from model.terms._base import AssumptionReport, Fitted, Hypothesis
from model.terms.team_goals_against.spec import GRAIN, TEAM_GA_POOL

# Fit guards — carried over verbatim from points_model.walk_forward_team_ga so the selected draw
# reproduces the frozen p_cs / e_conceded_pts to the bit.
MIN_TEAM_TRAIN_ROWS = 40
# GA support for the penalty expectation — P(GA>14) is negligible at any realistic lambda.
_GA_SUPPORT = np.arange(0, 15)
_GA_PENALTY = -(_GA_SUPPORT // 2)  # FPL: -1 per 2 conceded = -floor(GA/2)
# Detectability floor (pre-fit): enough team-fixtures with a positive GA to learn a Poisson mean.
_MIN_POSITIVE_EVENTS = 20


def _lag_roll(df: pd.DataFrame, group: str, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per group (shift(1) BEFORE rolling -> excludes current row)."""
    return df.groupby(group)[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


def conceded_penalty_expectation(lam: np.ndarray) -> np.ndarray:
    """E[-floor(GA/2)] under GA ~ Poisson(lam); NaN-safe (NaN lambda -> NaN). Shared with the baseline."""
    lam = np.asarray(lam, dtype=float)
    safe = np.nan_to_num(lam, nan=0.0)
    pmf = poisson.pmf(_GA_SUPPORT[None, :], safe[:, None])  # (n, K)
    exp = (pmf * _GA_PENALTY).sum(axis=1)
    return np.where(np.isnan(lam), np.nan, exp)


class TeamGoalsAgainstModel:
    """Poisson GLM of team goals-against per fixture; emits clean_sheet + conceded (the fittable unit)."""

    grain = GRAIN
    pool = TEAM_GA_POOL
    family = staticmethod(sm.families.Poisson)

    def __init__(
        self, variant: Literal["minimal", "selected"] = "selected",
        feature_override: list[str] | None = None,
    ) -> None:
        if variant not in ("minimal", "selected"):
            raise ValueError(f"unknown variant {variant!r}")
        self.variant = variant
        self._feature_override = feature_override  # ablation uses this to fit on a feature subset
        self.name = "team_goals_against"
        self.hypotheses = (
            Hypothesis(
                claim="team-GA-derived P(CS) ranks realized clean sheets better than lagged clean_sheets_roll3",
                test="within-position Spearman of broadcast p_cs vs clean_sheets_roll3, GW>3, GK/DEF/MID",
                success_threshold="Δ Spearman > 0 at DEF (the primary clean-sheet position)",
                status="supported (phase3 team-GA layer, D-D joint)",
            ),
        )

    # -- feature resolution ------------------------------------------------------------------
    def features(self, panel: pd.DataFrame) -> list[str]:
        """Design columns this variant draws, restricted to what is materializable on the team panel.

        ``minimal`` = the mechanistic ``ga_roll3``. ``selected`` = the full pool present on the panel,
        which today is exactly ``TEAM_GA_FEATURES`` (the frozen design); ``team_xgc_minutes_aware`` is
        declared but unmaterialized, so it is not drawn until ``features/build.py`` builds it.
        """
        if self._feature_override is not None:
            return [f for f in self._feature_override if f in panel.columns]
        if self.variant == "minimal":
            return list(self.pool.minimal)
        return [f.name for f in self.pool.candidates if f.name in panel.columns]

    # -- population (team_gw aggregate) ------------------------------------------------------
    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """One row per (team_id, gw): team GA target + leakage-safe lagged features (DGW excluded).

        Team GA is the ``max goals_conceded`` among the team's players who appeared (a full-match player
        saw every goal); team xGC is the mean expected-goals-conceded over appearances. Mirrors
        ``points_model.build_team_ga_panel`` exactly so the selected draw reproduces its output.
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
        return team.reset_index(drop=True)

    # -- pre-fit (spec §4 stage 1) -----------------------------------------------------------
    def check_assumptions(self, panel: pd.DataFrame) -> AssumptionReport:
        """Dispersion (is Poisson justified on team GA?) + detectability floor (learnable at this N?)."""
        disp = dict(diagnose_overdispersion(panel["team_ga"]))
        disp["family_ok"] = not bool(disp.get("material_overdispersion", False))
        feats = self.features(panel)
        complete = panel.dropna(subset=[*feats, "team_ga"])
        events = int((complete["team_ga"] > 0).sum())
        detectable = len(complete) >= MIN_TEAM_TRAIN_ROWS and events >= _MIN_POSITIVE_EVENTS
        note = "" if detectable else f"under detectability floor: {events} positive-GA fixtures, {len(complete)} rows"
        return AssumptionReport(
            term=self.name, dispersion=disp, detectable=detectable, n_train=len(complete), notes=note
        )

    # -- fit + emit (spec §4 stages 2-3) -----------------------------------------------------
    def fit(self, mart: pd.DataFrame) -> Fitted:
        """Expanding walk-forward Poisson on team GA -> lambda_ga (+ derived p_cs, e_conceded_pts).

        Lag-safety is a build/CI property (``features.build.assert_lag_safe``), not a fit-time guard.
        ``minimal`` and ``selected`` share this loop; only the design columns differ.
        """
        team = self.population(mart)
        features = self.features(team)
        team["lambda_ga"] = np.nan
        for t in sorted(g for g in team["gw"].unique() if g > WARMUP_GW):
            tr = team[team["gw"] < t].dropna(subset=[*features, "team_ga"])
            te = team[team["gw"] == t]
            if len(tr) < MIN_TEAM_TRAIN_ROWS or te.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    x = sm.add_constant(tr[features].to_numpy(float), has_constant="add")
                    res = sm.GLM(tr["team_ga"].to_numpy(float), x, family=sm.families.Poisson()).fit()
                    xte = sm.add_constant(te[features].to_numpy(float), has_constant="add")
                    team.loc[te.index, "lambda_ga"] = res.predict(xte)
                except Exception:
                    continue
        lam = team["lambda_ga"].to_numpy(dtype=float)
        team["p_cs"] = np.exp(-lam)
        team["e_conceded_pts"] = conceded_penalty_expectation(lam)
        return Fitted(
            name=self.name, predictions=team["lambda_ga"], features=tuple(features),
            meta={"variant": self.variant,
                  "team_frame": team[["team_id", "gw", "lambda_ga", "p_cs", "e_conceded_pts"]]},
        )

    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]:
        """The two scored views this joint model produces — clean_sheet and conceded (team grain)."""
        team = fitted.meta["team_frame"]
        return {"clean_sheet": team["p_cs"].to_numpy(), "conceded": team["e_conceded_pts"].to_numpy()}
