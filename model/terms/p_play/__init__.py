"""The ``p_play`` term — P(play) = P(minutes>0) one gameweek ahead (spec X1 blank-tail).

The appearance gate *before* the ``minutes`` term's P(>=60' | played). It rides the shared
:class:`~model.terms._binary_component.BinaryPerPositionComponent` but is the one binary term that keeps
the blank (``minutes==0``) rows in **both** its population and its TRAIN set — because its target
``played`` is defined by those rows. ``compose`` (keep_all mode) multiplies P(play) onto the conditional
decomposition to score the ex-ante universe including potential blanks. See ``ASSUMPTIONS.md``.
"""

from __future__ import annotations

from model.terms.p_play.p_play import PlayModel, PlayTerm

__all__ = ["PlayModel", "PlayTerm"]
