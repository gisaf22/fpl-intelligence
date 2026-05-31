"""Registry population constants: position map, signal list, and output schema."""

from __future__ import annotations

from dal.mart.mart_analytical import POSITION_CODE_MAP

MINUTES_THRESHOLD: int = 60

REGISTRY_BUILD_INPUT_COLUMNS: tuple[str, ...] = (
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "goals_conceded",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "fdr_avg",
    "fixture_count",
    "was_home",
    "starts",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "ownership_count",
    "purchase_price",
    "transfers_in",
    "transfers_out",
)

OUTPUT_COLUMNS: tuple[str, ...] = (
    "player_id",
    "gw",
    "position",
    *REGISTRY_BUILD_INPUT_COLUMNS,
    "total_points",
)
