"""Track-0 verification: domain scoring constants match the FPL bootstrap-static scoring config.

Hermetic by design: the API's ``game_config.scoring`` block is captured as a FROZEN SNAPSHOT
below (fetched 2026-07-08, season 2025/26) rather than fetched live, so the test guards our
constants against drift without a network dependency in CI. To refresh: re-fetch
``https://fantasy.premierleague.com/api/bootstrap-static/`` -> ``game_config['scoring']`` and
update the snapshot (and the VERIFIED annotations in domain/fpl_scoring.py).

Only the point COEFFICIENTS and their position applicability are exposed by this endpoint. The
"per 2" goals-conceded divisor, the "per 3" saves divisor, and the DC action thresholds
(10 CBIT / 12 CBIRT) are NOT in bootstrap-static and are intentionally NOT asserted here.
"""

from __future__ import annotations

import pytest

from domain import fpl_scoring as fs

pytestmark = pytest.mark.unit

# --- Frozen snapshot: game_config['scoring'] from bootstrap-static (2025/26, fetched 2026-07-08) ---
SCORING_SNAPSHOT = {
    "long_play": 2,
    "short_play": 1,
    "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
    "assists": 3,
    "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
    "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
    "saves": 1,
    "penalties_saved": 5,
    "penalties_missed": -2,
    "yellow_cards": -1,
    "red_cards": -3,
    "own_goals": -2,
    "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
}


def test_appearance_points_match_snapshot() -> None:
    assert fs.FULL_APPEARANCE_POINTS == SCORING_SNAPSHOT["long_play"]
    assert fs.SHORT_APPEARANCE_POINTS == SCORING_SNAPSHOT["short_play"]


def test_goal_points_match_snapshot() -> None:
    g = SCORING_SNAPSHOT["goals_scored"]
    assert (fs.GOAL_POINTS_GK, fs.GOAL_POINTS_DEF, fs.GOAL_POINTS_MID, fs.GOAL_POINTS_FWD) == (
        g["GKP"], g["DEF"], g["MID"], g["FWD"],
    )


def test_clean_sheet_points_match_snapshot() -> None:
    c = SCORING_SNAPSHOT["clean_sheets"]
    assert (
        fs.CLEAN_SHEET_POINTS_GK, fs.CLEAN_SHEET_POINTS_DEF,
        fs.CLEAN_SHEET_POINTS_MID, fs.CLEAN_SHEET_POINTS_FWD,
    ) == (c["GKP"], c["DEF"], c["MID"], c["FWD"])


def test_goals_conceded_coefficient_and_applicability() -> None:
    gc = SCORING_SNAPSHOT["goals_conceded"]
    # coefficient verified for the positions it applies to (GK/DEF); MID/FWD exempt (0 in the API).
    assert fs.GOALS_CONCEDED_PENALTY_POINTS == gc["GKP"] == gc["DEF"]
    assert gc["MID"] == gc["FWD"] == 0


def test_defensive_contribution_points_and_applicability() -> None:
    dc = SCORING_SNAPSHOT["defensive_contribution"]
    assert fs.DC_POINTS == dc["DEF"] == dc["MID"] == dc["FWD"]
    assert dc["GKP"] == 0  # GK do not earn DC


def test_assist_penalty_card_owngoal_points_match_snapshot() -> None:
    assert fs.ASSIST_POINTS == SCORING_SNAPSHOT["assists"]
    assert fs.GK_PENALTY_SAVE_POINTS == SCORING_SNAPSHOT["penalties_saved"]
    assert fs.PENALTY_MISS_POINTS == SCORING_SNAPSHOT["penalties_missed"]
    assert fs.YELLOW_CARD_POINTS == SCORING_SNAPSHOT["yellow_cards"]
    assert fs.RED_CARD_POINTS == SCORING_SNAPSHOT["red_cards"]
    assert fs.OWN_GOAL_POINTS == SCORING_SNAPSHOT["own_goals"]


def test_by_rule_params_are_documented_not_asserted() -> None:
    # These are NOT exposed by bootstrap-static; kept as by-rule constants. This test pins their
    # current values so a change is deliberate, and documents that they are not API-verified.
    assert fs.GOALS_CONCEDED_PER_PENALTY == 2      # -1 per 2 conceded (divisor by-rule)
    assert fs.GK_SAVES_PER_POINT == 3              # 1 point per 3 saves (divisor by-rule)
    assert fs.DC_CBIT_THRESHOLD_DEF == 10          # DEF CBIT threshold (by-rule)
    assert fs.DC_CBIRT_THRESHOLD_MID_FWD == 12     # MID/FWD CBIRT threshold (by-rule)
