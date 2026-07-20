"""The term registry — the single list ``compose``/``simulate`` iterate (spec §2, §7).

Adding a term = adding its model here (and a folder), never editing a god-file. Each entry is a fitted
**model** (the fittable unit); a joint model emits several terms (``team_goals_against`` → clean_sheet +
conceded), so the registry is keyed by model, not term.

``bonus`` is deliberately **not** in ``TERM_MODELS``: it is a contemporaneous scoring-map that consumes
the *other* terms' expected returns, so ``compose`` fits it last, after the returns are assembled. Order
in ``TERM_MODELS`` also matters for one gate: ``minutes`` (``p60``) gates ``clean_sheet``.

``p_play`` is likewise **held out** of ``TERM_MODELS``: it is not a decomposition component but the
**unconditional factor out front** (``E[points]_uncond = P(play) * E[points | played]``). ``compose``
consumes it only in its ``keep_all`` (blank-inclusive) mode, so the default conditional composition — and
every existing golden — is untouched.
"""

from __future__ import annotations

from model.terms.assists import AssistsModel
from model.terms.bonus import BonusModel
from model.terms.defensive_contribution import DefensiveContributionModel
from model.terms.goals import GoalsModel
from model.terms.minutes import MinutesHurdleModel
from model.terms.p_play import PlayModel
from model.terms.saves import SavesModel
from model.terms.team_goals_against import TeamGoalsAgainstModel

# The independent term models, fit first (each runs its own walk-forward and emits >=1 term view).
TERM_MODELS = (
    GoalsModel(variant="selected"),
    AssistsModel(variant="selected"),
    SavesModel(variant="selected"),
    TeamGoalsAgainstModel(variant="selected"),   # joint: emits clean_sheet + conceded
    DefensiveContributionModel(variant="selected"),
    MinutesHurdleModel(variant="selected"),
)

# Bonus depends on the assembled expected returns of the models above — fit last (see compose).
BONUS_MODEL = BonusModel()

# P(play) is the unconditional factor out front, not a decomposition term — held out of TERM_MODELS and
# consumed by compose only in keep_all (blank-inclusive) mode (E[points]_uncond = P(play) * conditional).
PLAY_MODEL = PlayModel(variant="selected")

# Every scored view the registry produces (for validation that compose covers them all).
REGISTERED_TERMS = ("goals", "assists", "saves", "clean_sheet", "conceded", "defensive_contribution",
                    "p60", "bonus")

__all__ = ["BONUS_MODEL", "PLAY_MODEL", "REGISTERED_TERMS", "TERM_MODELS"]
