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

import pandas as pd

from model.terms._base import Hypothesis
from model.terms._poisson_component import PlayerComponentTerm, PoissonPlayerComponentModel
from model.terms.saves.spec import SAVES_POOL


class SavesModel(PoissonPlayerComponentModel):
    """Poisson GLM of next-GW ``saves`` on lagged process stats, GK only (the fittable unit)."""

    name = "saves"
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
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """GK-only v1 population: ``position == GK``, ``minutes > 0``, DGW excluded, sorted (player, gw)."""
        df = mart[(mart["position"] == "GK") & (mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
        return df.sort_values(["player_id", "gw"]).reset_index(drop=True)


class SavesTerm(PlayerComponentTerm):
    """The ``saves`` term — E[saves] scored vs its own lagged-saves baseline (spec §5, per-term, GK)."""

    name = "saves"
    baseline_col = "saves_prior"
    view_col = "e_saves"
    _model_cls = SavesModel
