"""The ``defensive_contribution`` term — P(DC hit) one gameweek ahead (spec §10 "repeat per model").

Strangled from ``model/forecast/points_model.py`` (``walk_forward_dc``). Unlike goals/assists/saves this
is a **logistic** term with a **derived binary** target (``dc_hit = 1{defensive_contribution >=
position_threshold}``) fit **per position** — a different shape, so it is standalone for now; a shared
``BinaryPerPositionComponent`` base is extracted once ``minutes`` (the second logistic term) confirms the
shape (rule of three). See ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.defensive_contribution.defensive_contribution import (
    DefensiveContributionModel,
    DefensiveContributionTerm,
)

__all__ = ["DefensiveContributionModel", "DefensiveContributionTerm"]
