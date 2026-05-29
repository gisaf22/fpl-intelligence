"""Named entity accessors and StagedEntities loader — the DAL I/O boundary.

All DB reads happen here. Every function returns a DataFrame with canonical column
names and validated dtypes. Nothing above this layer touches db_path.

StagedEntities groups all six entities into one object so callers load once and
pass what they need downstream without re-reading the DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dal.staging.stg_schema import load_schema
from dal.staging.stg_transformer import stage


@dataclass
class StagedEntities:
    """All six staged entities loaded in a single DB pass.

    Produced by load_staged_entities(db_path). Pass this to intermediate and fct
    instead of passing db_path, so the DB is read exactly once per pipeline run.
    """

    player_histories: pd.DataFrame
    players: pd.DataFrame
    fixtures: pd.DataFrame
    teams: pd.DataFrame
    element_types: pd.DataFrame
    events: pd.DataFrame


def load_staged_entities(db_path: Path) -> StagedEntities:
    """Load all six staged entities from db_path and return them as StagedEntities.

    This is the single entry point for all DB I/O in the pipeline. Call once per run,
    then pass the returned object to get_player_fixture_base and build_player_gameweek_spine.
    """
    return StagedEntities(
        player_histories=get_staged_player_histories(db_path),
        players=get_staged_players(db_path),
        fixtures=get_staged_fixtures(db_path),
        teams=get_staged_teams(db_path),
        element_types=get_staged_element_types(db_path),
        events=get_staged_events(db_path),
    )


def get_staged_players(db_path: Path) -> pd.DataFrame:
    """Return the staged players frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "players")


def get_staged_player_histories(db_path: Path) -> pd.DataFrame:
    """Return the staged player histories frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "player_histories")


def get_staged_fixtures(db_path: Path) -> pd.DataFrame:
    """Return the staged fixtures frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "fixtures")


def get_staged_teams(db_path: Path) -> pd.DataFrame:
    """Return the staged teams frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "teams")


def get_staged_element_types(db_path: Path) -> pd.DataFrame:
    """Return the staged element types frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "element_types")


def get_staged_events(db_path: Path) -> pd.DataFrame:
    """Return the staged events frame with canonical columns and validated dtypes."""
    return _stage_entity(db_path, "events")


def _stage_entity(db_path: Path, entity: str) -> pd.DataFrame:
    """Load the schema contract for entity and run it through the staging transformer."""
    return stage(db_path, load_schema(entity))
