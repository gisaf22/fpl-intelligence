"""The saves Model + Term (spec §2) — strangled from ``component_forecast.py``, no behaviour change.

``SavesModel`` fits ``saves`` one gameweek ahead with a Poisson GLM on lagged process stats, **restricted
to goalkeepers**, expanding walk-forward. It reuses the shared Poisson-player machinery
(:class:`~model.terms._poisson_component.PoissonPlayerComponentModel`) and changes exactly two things:

* **population** → GK only (saves are a keeper term; ~18% of GK points);
* **min_train_rows_total** → 30, matching the god-file's *effective* gate. The god-file fits saves inside
  the all-position loop whose outer guard (all-position train ≥ 100) is non-binding for GW>3, so the real
  constraint is the inner **GK train ≥ 30**; lowering the total-rows guard to 30 reproduces that exactly
  on the GK-only population (golden test pins ``emit`` bit-identical to ``component_forecast``).

``SavesTerm`` scores E[saves] against the term's own lagged-saves baseline (spec §5). The saves→points
conversion (÷3) is a compose-layer concern, so the term emits the raw expected count.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

from domain.fpl_scoring import GK_SAVES_PER_POINT
from model.terms._base import Hypothesis
from model.terms._poisson_component import PlayerComponentTerm, PoissonPlayerComponentModel
from model.terms.saves.spec import SAVES_POOL

# Saves support for the points expectation. FPL pays 1 pt per 3 saves = floor(S/3); P(S>=40) is
# negligible for any realistic keeper lambda (~2.6, rarely >8), mirroring team_goals_against's _GA_SUPPORT.
_SAVES_SUPPORT = np.arange(0, 40)
_SAVES_POINTS = _SAVES_SUPPORT // GK_SAVES_PER_POINT  # floor(S/3) — the actual FPL payout per save count


def saves_points_expectation(e_saves: np.ndarray) -> np.ndarray:
    """E[floor(S/3)] under S ~ Poisson(e_saves) — the EXACT expected saves points, NaN-safe.

    FPL pays ``floor(S/3)``, a concave step function, so the expectation of the payout is **not** the
    payout of the expectation: ``E[floor(S/3)] < E[S]/3`` by ~0.33 pt at a typical keeper rate (a Jensen
    gap the naive ``e_saves / 3`` conversion ignored). Same construction as
    :func:`model.terms.team_goals_against.conceded_penalty_expectation` (``E[-floor(GA/2)]``) — the shared
    shape is ``E[floor(Poisson/k)]`` summed over the count support.
    """
    e_saves = np.asarray(e_saves, dtype=float)
    safe = np.nan_to_num(e_saves, nan=0.0)
    pmf = poisson.pmf(_SAVES_SUPPORT[None, :], safe[:, None])  # (n, K)
    exp = (pmf * _SAVES_POINTS).sum(axis=1)
    return np.where(np.isnan(e_saves), np.nan, exp)


class SavesModel(PoissonPlayerComponentModel):
    """Poisson GLM of next-GW ``saves`` on lagged process stats, GK only (the fittable unit)."""

    name = "saves"
    fit_positions = ("GK",)   # GK-only: one level => no dummies, design unchanged
    target = "saves"
    term = "saves"
    pool = SAVES_POOL
    # GK train reaches the god-file's effective inner guard (>=30) well before an all-position >=100
    # would; match the effective gate so the GK-only population reproduces the god-file to the bit.
    min_train_rows_total = 30
    hypotheses = (
        Hypothesis(
            claim="lagged xGC (shots-faced proxy) ranks next-GW GK saves better than a keeper's lagged saves mean",
            test="within-position Spearman of emitted E[saves] vs saves_prior, GW>3, GK",
            success_threshold="Δ Spearman > 0 at GK (saves lift GK toward parity — an honest ceiling)",
            status="supported-weakly (phase2: GK reaches parity with saves added; ranking near-chance)",
        ),
    )

    @staticmethod
    def population(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
        """GK-only v1 population: ``position == GK``, ``minutes > 0``, DGW excluded, sorted (player, gw).

        ``keep_all=True`` retains 0-minute GK rows for ex-ante scoring of the wider universe (train stays
        ``minutes>0`` in :meth:`fit`); default is the conditional-on-appearance GK population. The
        ``keep_all`` universe is fixtures-only (NaN-minutes no-fixture rows excluded — not appearances).
        """
        gk = (mart["position"] == "GK") & (~mart["is_dgw"].astype(bool))
        keep = gk & mart["minutes"].notna() if keep_all else gk & (mart["minutes"] > 0)
        df = mart[keep].copy()
        return df.sort_values(["player_id", "gw"]).reset_index(drop=True)


class SavesTerm(PlayerComponentTerm):
    """The ``saves`` term — E[saves] scored vs its own lagged-saves baseline (spec §5, per-term, GK)."""

    name = "saves"
    baseline_col = "saves_prior"
    view_col = "e_saves"
    _model_cls = SavesModel
