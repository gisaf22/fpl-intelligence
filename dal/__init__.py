"""Public DAL package exports.

Primary consumer interface (replaces the deleted dal.access module):
    get_analytics_dataset(db_path, data_cutoff_gw) -> MartResult

Lower-level builders (pipeline internals, advanced callers, tests):
    build_player_gameweek_spine, build_player_gameweek_state,
    load_staged_entities, get_player_fixture_base
"""

# --- primary consumer interface ---
from dal.mart.mart_access import MartResult, get_analytics_dataset

# --- lower-level pipeline builders ---
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.intermediate.int_player_fixture import get_player_fixture_base

# --- staging ---
from dal.staging import (
    ColumnMapping,
    Schema,
    StagedEntities,
    get_staged_element_types,
    get_staged_events,
    get_staged_fixtures,
    get_staged_player_histories,
    get_staged_players,
    get_staged_teams,
    load_staged_entities,
    validate_data_freshness,
)

# --- exceptions ---
from dal.exceptions import DALError, DataFreshnessError

__all__ = [
    # primary interface
    "get_analytics_dataset",
    "MartResult",
    # pipeline builders
    "build_player_gameweek_spine",
    "build_player_gameweek_state",
    "get_player_fixture_base",
    # staging
    "StagedEntities",
    "load_staged_entities",
    "validate_data_freshness",
    "ColumnMapping",
    "Schema",
    "get_staged_element_types",
    "get_staged_events",
    "get_staged_fixtures",
    "get_staged_player_histories",
    "get_staged_players",
    "get_staged_teams",
    # exceptions
    "DALError",
    "DataFreshnessError",
]
