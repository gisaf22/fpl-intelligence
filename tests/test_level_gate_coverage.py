"""Gate-completeness invariant: EVERY term runs the level gate, not only the ranking gate.

Ranking is invariant to a monotone level error, so a term can out-rank its baseline and still predict
the wrong AMOUNT — that is what ``GateResult.passed_calibration`` catches (spec §5). Three custom-
``validate`` terms (bonus, clean_sheet, conceded) used to return a ``GateResult`` with no calibration,
so ``passed_all`` silently defaulted their level verdict to ``True`` (``.get(p, True)``). This guard
fails if any term regresses to that ranking-only shape, or if a *future* term forgets the level gate.
"""

from __future__ import annotations

import pytest

from model.terms.assists import AssistsTerm
from model.terms.bonus import BonusTerm
from model.terms.defensive_contribution import DefensiveContributionTerm
from model.terms.goals import GoalsTerm
from model.terms.minutes import MinutesTerm
from model.terms.p_play import PlayTerm
from model.terms.saves import SavesTerm
from model.terms.team_goals_against import CleanSheetTerm, ConcededTerm
from tests._synthetic_mart import points_panel

pytestmark = pytest.mark.unit

# Every Term the registry produces (compose iterates these models; here we gate their views directly).
ALL_TERMS = [
    GoalsTerm, AssistsTerm, SavesTerm, CleanSheetTerm, ConcededTerm,
    DefensiveContributionTerm, MinutesTerm, BonusTerm, PlayTerm,
]


@pytest.mark.parametrize("term_cls", ALL_TERMS, ids=lambda c: c.__name__)
def test_every_ranked_position_carries_a_level_verdict(term_cls: type) -> None:
    """The invariant that matters: no position is RANKED without also being LEVELLED.

    A ranking-only term (the pre-fix bonus/clean_sheet/conceded shape) has non-empty ``passed`` and an
    empty ``passed_calibration`` — this fires on exactly that. ``p_play`` needs the blank-inclusive
    universe, so it makes no ranking claim on the conditional ``points_panel`` (empty ``passed`` →
    nothing to level, vacuously ok); its populated level gate is covered in ``test_p_play`` on its own
    panel. Level may cover MORE positions than ranking (e.g. a structural GK the ranking omits) — that
    is fine; the guard is one-directional.
    """
    res = term_cls().validate(points_panel(seed=0))
    missing = set(res.passed) - set(res.passed_calibration)
    assert not missing, f"{res.term}: ranks {sorted(res.passed)} but no level verdict for {sorted(missing)}"
