"""The ``saves`` term — E[saves] one gameweek ahead, GK only (spec §10 "repeat per model").

Strangled from the former ``component_forecast`` god-file (since deleted) (the GK-saves component, ~18% of GK points): a
Poisson GLM of ``saves`` on lagged process stats, restricted to goalkeepers. The same Poisson-player
shape as goals/assists (shared base in ``model/terms/_poisson_component.py``); it differs only in the
**GK-only population** and its pool. See ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.saves.saves import SavesModel, SavesTerm

__all__ = ["SavesModel", "SavesTerm"]
