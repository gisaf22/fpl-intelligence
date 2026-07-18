"""The ``bonus`` term — E[bonus] as a contemporaneous scoring-map (spec §10 "repeat per model").

Strangled from ``model/forecast/points_model.py`` (``walk_forward_bonus``). Unlike every other term this
is **not a lagged forecast**: bonus (top-3 BPS -> 3/2/1) is *caused by* the same-match performance, so it
is a per-position **OLS calibration** of realized ``bonus`` on ``returns_pts`` (the FPL value of the
modelled returns — the strong BPS proxy from D-B). A one-off shape (OLS, contemporaneous input), so it is
standalone — no shared base. It also exposes the fitted intercept/slope so the simulator can apply bonus
per draw (co-movement). See ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.bonus.bonus import BonusModel, BonusTerm

__all__ = ["BonusModel", "BonusTerm"]
