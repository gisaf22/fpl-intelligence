"""The ``assists`` term — E[assists] one gameweek ahead (spec §10 step 5, "repeat per model").

Strangled from ``model/forecast/component_forecast.py``: a Poisson GLM of ``assists`` on lagged process
stats, the same Poisson-player shape as ``goals`` (shared base in ``model/terms/_poisson_component.py``),
differing only in the target column and pool. See ``spec.py`` for the candidate pool, ``ASSUMPTIONS.md``
for the family / minutes-covariate decisions.
"""

from __future__ import annotations

from model.terms.assists.assists import AssistsModel, AssistsTerm

__all__ = ["AssistsModel", "AssistsTerm"]
