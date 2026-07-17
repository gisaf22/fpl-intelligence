"""The ``team_goals_against`` joint model — emits ``clean_sheet`` + ``conceded`` (spec §2, §10 step 4).

D-D proved ``clean_sheet = 1{GA=0}`` and the conceded penalty ``-floor(GA/2)`` are the **same random
variable** (team goals-against): one Poisson mean per team-fixture derives *both* ``p_cs = P(GA=0)`` and
``e_conceded_pts = E[-floor(GA/2)]``, internally consistent by construction. This is the joint shape the
Model/Term split (a model emits many terms) was designed for. Strangled from
``model/forecast/points_model.py`` (``walk_forward_team_ga``); see ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.team_goals_against.team_goals_against import TeamGoalsAgainstModel

__all__ = ["TeamGoalsAgainstModel"]
