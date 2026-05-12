"""Named entity accessors — one function per staged DAL entity."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.staging.schema import load_schema
from dal.staging.transformer import stage


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
