"""Fixture-grain enrichment — joins team strength context onto staged fixtures.

Pure transform: accepts staged fixtures and teams frames, returns one enriched row
per fixture_id. No I/O — db_path never enters this module.
"""

from __future__ import annotations

import logging

import pandas as pd

from dal.validation import validate_join_safety
from dal.validation.grain import validate_grain_uniqueness

logger = logging.getLogger(__name__)


def get_fixture_context(
    fixtures: pd.DataFrame,
    teams: pd.DataFrame,
    gw: int | None = None,
) -> pd.DataFrame:
    """Return one enriched row per fixture_id with home and away team strength context."""
    home_teams, away_teams = _prepare_team_strength_views(teams)
    result = fixtures.merge(home_teams, on="home_team_id", how="left")
    validate_join_safety(
        left_n=len(fixtures),
        right_n=len(home_teams),
        result_n=len(result),
        join_type="left",
        description="fixtures x home teams",
    )
    n_before_away_join = len(result)
    result = result.merge(away_teams, on="away_team_id", how="left")
    validate_join_safety(
        left_n=n_before_away_join,
        right_n=len(away_teams),
        result_n=len(result),
        join_type="left",
        description="fixtures x away teams",
    )

    # FPL API returns unscheduled fixtures (gw is null) for future matches not yet assigned to a
    # gameweek. These are intentionally excluded — they have no analytical use at this stage and
    # would break downstream grain checks. They are logged at debug level for observability.
    unscheduled_mask = result["gw"].isna()
    if unscheduled_mask.any():
        fixture_ids = sorted(result.loc[unscheduled_mask, "fixture_id"].tolist())
        logger.warning(
            "Excluding %d unscheduled fixture(s) with null gw: %s",
            len(fixture_ids),
            fixture_ids,
        )
    result = result.dropna(subset=["gw"])
    if gw is not None:
        result = result[result["gw"] == gw].reset_index(drop=True)
    validate_grain_uniqueness(result, ["fixture_id"], "get_fixture_context")
    return result


def _prepare_team_strength_views(teams: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the teams frame into home-keyed and away-keyed lookup views."""
    home_teams = teams[
        [
            "team_id",
            "name",
            "team_strength_overall_home",
            "team_strength_attack_home",
            "team_strength_defence_home",
        ]
    ].rename(
        columns={
            "team_id": "home_team_id",
            "name": "home_team_name",
            "team_strength_overall_home": "home_team_strength_overall",
            "team_strength_attack_home": "home_team_strength_attack",
            "team_strength_defence_home": "home_team_strength_defence",
        }
    )
    away_teams = teams[
        [
            "team_id",
            "name",
            "team_strength_overall_away",
            "team_strength_attack_away",
            "team_strength_defence_away",
        ]
    ].rename(
        columns={
            "team_id": "away_team_id",
            "name": "away_team_name",
            "team_strength_overall_away": "away_team_strength_overall",
            "team_strength_attack_away": "away_team_strength_attack",
            "team_strength_defence_away": "away_team_strength_defence",
        }
    )
    return home_teams, away_teams
