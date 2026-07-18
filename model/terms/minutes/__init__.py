"""The ``minutes`` term — P(>=60' | played) one gameweek ahead (spec §10 "repeat per model").

Strangled from ``model/forecast/points_model.py`` (``walk_forward_minutes_hurdle``). The second logistic
term, so it confirms the per-position-logistic shape and rides the shared
:class:`~model.terms._binary_component.BinaryPerPositionComponent` base — with a GK override (GK play
>=60' ~99% of the time, so the logistic is degenerate; GK use a robust lagged rate instead). The emitted
``p60`` feeds appearance points (``1 + p60``) and gates the clean-sheet term downstream — both compose
concerns. See ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.minutes.minutes import MinutesHurdleModel, MinutesTerm

__all__ = ["MinutesHurdleModel", "MinutesTerm"]
