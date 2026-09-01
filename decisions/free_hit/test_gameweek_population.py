"""Tests for the club-schedule-level gameweek population utility -- `DESIGN.md` §2.

`mart` is built so the row-level and club-schedule-level DGW/BGW definitions disagree at GW1: a
not-yet-debuted player's row carries the same `fixture_count == 0` shape a real blank would, the
exact pre-registration-prefix artefact `INVENTORY.md` §1 and `decisions/starting_xi/INVENTORY.md`
§2.5 document. `schedule_clean_gameweeks` must side with the club-schedule-level (registered-only)
definition, not the row-level one.

These tests target `schedule_clean_gameweeks` (`METRIC.md` §3.2's axis) rather than
`qualifying_gameweeks`, which composes that axis with §3.3's warm-up exclusion. Both are asserted
here, separately, so a change to either axis fails on its own.
"""

from __future__ import annotations

import pandas as pd
import pytest

from decisions.free_hit.gameweek_population import (
    WARM_UP_EXCLUDED,
    qualifying_gameweeks,
    schedule_clean_gameweeks,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mart() -> pd.DataFrame:
    """2 teams x 4 gameweeks.

    Team 1: player 1 and player 4 are both registered from GW1 and mirror each other's
    `fixture_count` (a real blank, 0, at GW2) -- modelling two team-mates whose schedule fact
    must agree. Player 2 does not debut until GW4; his GW1/GW2 rows carry `fixture_count == 0`
    purely because he has not played yet, not because his team had no fixture.

    Team 2: player 3 is registered from GW1 and carries a real double (`fixture_count == 2`) at
    GW3.

    GW1 and GW4 are clean for both teams' *registered* players and must qualify; GW2 (team 1's
    real blank) and GW3 (team 2's real double) must not.
    """
    rows = [
        {"player_id": 1, "gw": 1, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 1, "gw": 2, "team_id": 1, "fixture_count": 0, "minutes": None},
        {"player_id": 1, "gw": 3, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 1, "gw": 4, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 2, "gw": 1, "team_id": 1, "fixture_count": 0, "minutes": None},
        {"player_id": 2, "gw": 2, "team_id": 1, "fixture_count": 0, "minutes": None},
        {"player_id": 2, "gw": 3, "team_id": 1, "fixture_count": 1, "minutes": None},
        {"player_id": 2, "gw": 4, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 3, "gw": 1, "team_id": 2, "fixture_count": 1, "minutes": 90},
        {"player_id": 3, "gw": 2, "team_id": 2, "fixture_count": 1, "minutes": 90},
        {"player_id": 3, "gw": 3, "team_id": 2, "fixture_count": 2, "minutes": 90},
        {"player_id": 3, "gw": 4, "team_id": 2, "fixture_count": 1, "minutes": 90},
        {"player_id": 4, "gw": 1, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 4, "gw": 2, "team_id": 1, "fixture_count": 0, "minutes": None},
        {"player_id": 4, "gw": 3, "team_id": 1, "fixture_count": 1, "minutes": 90},
        {"player_id": 4, "gw": 4, "team_id": 1, "fixture_count": 1, "minutes": 90},
    ]
    df = pd.DataFrame(rows)
    df["minutes"] = df["minutes"].astype("Int64")
    return df


def test_schedule_axis_excludes_only_the_real_blank_and_the_real_double(mart: pd.DataFrame) -> None:
    assert schedule_clean_gameweeks(mart) == frozenset({1, 4})


def test_qualifying_composes_the_schedule_axis_with_the_warm_up_exclusion(mart: pd.DataFrame) -> None:
    """`METRIC.md` §3.3: GW1 is schedule-clean in this fixture and still excluded, on the second,
    independent axis."""
    assert 1 in schedule_clean_gameweeks(mart)
    assert qualifying_gameweeks(mart) == frozenset({4})
    assert qualifying_gameweeks(mart) == schedule_clean_gameweeks(mart) - WARM_UP_EXCLUDED


def test_the_row_level_definition_would_wrongly_exclude_gw1(mart: pd.DataFrame) -> None:
    """The counterfactual, executed: any `fixture_count`-anomalous row anywhere in the gameweek,
    counted without the registration filter, disqualifies GW1 -- which is why
    `schedule_clean_gameweeks` must apply registration rather than skip it as a simplification."""
    any_row_anomalous_at_gw1 = mart.loc[mart["gw"] == 1, "fixture_count"].isin([0, 2]).any()
    assert any_row_anomalous_at_gw1  # the row-level definition WOULD flag GW1
    assert 1 in schedule_clean_gameweeks(mart)  # the registered-only definition does not


def test_an_inconsistent_fixture_count_within_a_registered_team_gameweek_raises(mart: pd.DataFrame) -> None:
    corrupted = mart.copy()
    corrupted.loc[(corrupted["player_id"] == 4) & (corrupted["gw"] == 1), "fixture_count"] = 2
    with pytest.raises(ValueError, match="not constant"):
        schedule_clean_gameweeks(corrupted)
