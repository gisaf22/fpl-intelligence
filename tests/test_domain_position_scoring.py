"""Track-1 tests: the declarative per-position scoring equation (domain.fpl_scoring).

Covers the arithmetic engine (each term kind), position applicability (which terms qualify),
and that ``decompose_total_points`` delegates to the spec. The full 100%-exact reconstruction of
real ``total_points`` on single-GW rows is validated against the mart in
docs/studies/results (Track-1 gate); here we pin the equation hermetically with hand-computed cases.
"""

from __future__ import annotations

import pytest

from domain.fpl_scoring import (
    POSITION_SCORING,
    decompose_total_points,
    position_components,
    score_components,
)

pytestmark = pytest.mark.unit


def _stats(**kw: int) -> dict[str, int]:
    base = dict.fromkeys(
        ["minutes", "goals_scored", "assists", "clean_sheets", "goals_conceded", "saves",
         "penalties_saved", "bonus", "yellow_cards", "red_cards", "own_goals",
         "penalties_missed", "defensive_contribution"], 0,
    )
    base.update(kw)
    return base


def test_reconstruction_def_known_example() -> None:
    # DEF, 90' (+2), 1 goal (+6), 1 assist (+3), clean sheet (+4), 10 CBIT (+2), 2 bonus (+2),
    # 1 yellow (-1) -> 18.
    comps = score_components("DEF", _stats(minutes=90, goals_scored=1, assists=1, clean_sheets=1,
                                           defensive_contribution=10, bonus=2, yellow_cards=1))
    assert sum(comps.values()) == 18
    assert comps["goals"] == 6 and comps["defensive_contribution"] == 2 and comps["cards"] == -1


def test_reconstruction_gk_known_example() -> None:
    # GK, 90' (+2), 7 saves (7//3=2 -> +2), clean sheet (+4), 3 conceded (3//2=1 -> -1),
    # 1 pen save (+5), 3 bonus (+3) -> 15.
    comps = score_components("GK", _stats(minutes=90, saves=7, clean_sheets=1, goals_conceded=3,
                                          penalties_saved=1, bonus=3))
    assert sum(comps.values()) == 15
    assert comps["saves"] == 2 and comps["goals_conceded"] == -1 and comps["penalties_saved"] == 5


def test_rate_and_threshold_kinds() -> None:
    # rate: conceded is -1 per 2 (floor); threshold: DC awards once at/above the count.
    assert score_components("DEF", _stats(minutes=90, goals_conceded=1))["goals_conceded"] == 0
    assert score_components("DEF", _stats(minutes=90, goals_conceded=5))["goals_conceded"] == -2
    assert score_components("DEF", _stats(minutes=90, defensive_contribution=9))["defensive_contribution"] == 0
    assert score_components("DEF", _stats(minutes=90, defensive_contribution=10))["defensive_contribution"] == 2
    assert score_components("MID", _stats(minutes=90, defensive_contribution=11))["defensive_contribution"] == 0
    assert score_components("MID", _stats(minutes=90, defensive_contribution=12))["defensive_contribution"] == 2


def test_appearance_tiers() -> None:
    assert score_components("MID", _stats(minutes=0))["appearance"] == 0
    assert score_components("MID", _stats(minutes=45))["appearance"] == 1
    assert score_components("MID", _stats(minutes=90))["appearance"] == 2


def test_position_applicability() -> None:
    # FWD: no clean sheet, no conceded penalty, no saves; GK: no DC; MID: no conceded/saves.
    fwd = score_components("FWD", _stats(minutes=90, clean_sheets=1, goals_conceded=4, saves=5))
    assert fwd["clean_sheets"] == 0 and fwd["goals_conceded"] == 0 and fwd["saves"] == 0
    gk = score_components("GK", _stats(minutes=90, defensive_contribution=20))
    assert gk["defensive_contribution"] == 0
    mid = score_components("MID", _stats(minutes=90, goals_conceded=4, saves=5))
    assert mid["goals_conceded"] == 0 and mid["saves"] == 0


def test_position_components_modelled_roster() -> None:
    assert "clean_sheets" not in position_components("FWD")
    assert "defensive_contribution" not in position_components("GK")
    assert "saves" in position_components("GK")
    assert set(position_components("DEF")) == {"assists", "bonus", "goals", "clean_sheets",
                                               "goals_conceded", "defensive_contribution"}


def test_decompose_delegates_to_spec() -> None:
    s = _stats(minutes=72, goals_scored=1, assists=1, clean_sheets=1, goals_conceded=2,
               defensive_contribution=10, bonus=1, red_cards=1)
    viaspec = score_components("DEF", s)
    viadecomp = decompose_total_points(
        "DEF", s["minutes"], s["goals_scored"], s["assists"], s["clean_sheets"],
        s["goals_conceded"], s["saves"], s["penalties_saved"], s["bonus"], s["yellow_cards"],
        s["red_cards"], s["own_goals"], s["penalties_missed"], s["defensive_contribution"],
    )
    assert viaspec == viadecomp


def test_every_position_has_goals_and_appearance() -> None:
    for pos in ("GK", "DEF", "MID", "FWD"):
        keys = {t.out_key() for t in POSITION_SCORING[pos]}
        assert {"goals", "appearance", "assists", "bonus"} <= keys
