"""Named analytical populations for FPL signal characterisation.

Two populations are defined here. All registry build, lens study, and scoring
engine code must use one of these functions rather than inlining a minutes
filter directly.

Performance population (filter_performance):
    minutes >= 60. FPL's scoring formula has a structural break at 60 minutes:
    clean sheet eligibility, the additional appearance point, and the BPS
    minutes baseline all change at this boundary. Pooling rows from both scoring
    regimes produces a target variable (total_points) whose generating process
    differs across observations, making signal-target rho estimates incoherent
    unless restricted to one regime. The 60-minute threshold is currently
    EVALUATION-DEFERRED (threshold-registry.md §REG-T-01 / AVAIL-T-02); see
    research/foundation/scope/population_threshold_study.py (Change 3) for validation.

Participation population (filter_participation):
    minutes >= 1. Used by availability signals and rotation risk studies where
    the analytical question is "did the player participate at all" rather than
    "did they play enough to enter the performance scoring regime."
"""

from __future__ import annotations

import pandas as pd

from domain.fpl_scoring import APPEARANCE_MIN_MINUTES, CLEAN_SHEET_MIN_MINUTES


def filter_performance(mart: pd.DataFrame) -> pd.DataFrame:
    """Return rows where minutes >= CLEAN_SHEET_MIN_MINUTES (currently 60).

    Use for all signal characterisation, registry population construction, and
    scoring engine evaluation. See module docstring for analytical justification.
    """
    return mart.loc[mart["minutes"] >= CLEAN_SHEET_MIN_MINUTES].copy()


def filter_participation(mart: pd.DataFrame) -> pd.DataFrame:
    """Return rows where minutes >= APPEARANCE_MIN_MINUTES (currently 1).

    Use for availability signal studies and rotation risk analysis where the
    question is participation, not scoring-regime membership.
    """
    return mart.loc[mart["minutes"] >= APPEARANCE_MIN_MINUTES].copy()
