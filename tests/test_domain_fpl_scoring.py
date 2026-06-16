"""Regression guards for domain/fpl_scoring.py constants."""

import pytest

import domain.fpl_scoring as fpl

pytestmark = pytest.mark.unit


def test_clean_sheet_min_equals_full_appearance_min():
    # Same game rule — must stay in sync.
    assert fpl.CLEAN_SHEET_MIN_MINUTES == fpl.FULL_APPEARANCE_MIN_MINUTES


def test_appearance_thresholds_ordered():
    assert fpl.APPEARANCE_MIN_MINUTES < fpl.FULL_APPEARANCE_MIN_MINUTES


def test_full_appearance_points_exceed_short_appearance():
    assert fpl.FULL_APPEARANCE_POINTS > fpl.SHORT_APPEARANCE_POINTS


def test_clean_sheet_points_by_position():
    assert fpl.CLEAN_SHEET_POINTS_GK == fpl.CLEAN_SHEET_POINTS_DEF == 4
    assert fpl.CLEAN_SHEET_POINTS_MID == 1
    assert fpl.CLEAN_SHEET_POINTS_FWD == 0


def test_goal_points_decrease_with_attack():
    # GKP goals (10) are worth more than DEF (6) — FPL rule change for 2025/26.
    assert fpl.GOAL_POINTS_GK > fpl.GOAL_POINTS_DEF > fpl.GOAL_POINTS_MID > fpl.GOAL_POINTS_FWD


def test_goals_conceded_penalty_constants():
    assert fpl.GOALS_CONCEDED_PER_PENALTY > 0
    assert fpl.GOALS_CONCEDED_PENALTY_POINTS < 0


def test_dc_thresholds_and_points_positive():
    assert fpl.DC_CBIT_THRESHOLD_DEF > 0
    assert fpl.DC_CBIRT_THRESHOLD_MID_FWD > fpl.DC_CBIT_THRESHOLD_DEF
    assert fpl.DC_POINTS > 0


def test_defensive_contribution_points_by_position():
    assert fpl.defensive_contribution_points("DEF", fpl.DC_CBIT_THRESHOLD_DEF - 1) == 0
    assert fpl.defensive_contribution_points("DEF", fpl.DC_CBIT_THRESHOLD_DEF) == fpl.DC_POINTS
    assert fpl.defensive_contribution_points("MID", fpl.DC_CBIRT_THRESHOLD_MID_FWD - 1) == 0
    assert fpl.defensive_contribution_points("MID", fpl.DC_CBIRT_THRESHOLD_MID_FWD) == fpl.DC_POINTS
    assert fpl.defensive_contribution_points("FWD", fpl.DC_CBIRT_THRESHOLD_MID_FWD) == fpl.DC_POINTS
    assert fpl.defensive_contribution_points("GK", 999) == 0


def test_discipline_constants_are_negative():
    assert fpl.YELLOW_CARD_POINTS < 0
    assert fpl.RED_CARD_POINTS < 0
    assert fpl.PENALTY_MISS_POINTS < 0
    assert fpl.OWN_GOAL_POINTS < 0


def test_bps_bonus_tiers_descend():
    assert fpl.BPS_BONUS_FIRST > fpl.BPS_BONUS_SECOND > fpl.BPS_BONUS_THIRD > 0


def test_gk_saves_per_point_positive():
    assert fpl.GK_SAVES_PER_POINT > 0
    assert fpl.GK_PENALTY_SAVE_POINTS > 0
