"""The ``assists`` term — E[assists] one gameweek ahead (spec §10 step 5, "repeat per model").

Strangled from the former ``component_forecast`` god-file (since deleted): a Poisson GLM of ``assists``
on lagged process stats, the same Poisson-player shape as ``goals`` (shared base in ``_poisson_component``),
differing only in the target column and pool. See ``spec.py`` for the candidate pool, ``ASSUMPTIONS.md``
for the family / minutes-covariate decisions.
"""

from __future__ import annotations

from model.terms.assists.assists import AssistsModel, AssistsTerm

__all__ = ["AssistsModel", "AssistsTerm"]
