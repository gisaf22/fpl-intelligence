"""The ``goals`` term — E[goals_scored] one gameweek ahead (spec §10 step 3).

The first model strangled out of the former ``component_forecast`` god-file (since deleted): a Poisson GLM of
``goals_scored`` on lagged process stats, fit expanding walk-forward. Emits one term (``goals``);
composed into E[points] via the position goal weights. See ``ASSUMPTIONS.md`` for the family and
minutes-as-covariate decisions, ``spec.py`` for the candidate pool.
"""

from __future__ import annotations

from model.terms.goals.goals import GoalsModel, GoalsTerm

__all__ = ["GoalsModel", "GoalsTerm"]
