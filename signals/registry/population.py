"""Registry population constants: position map, signal list, and output schema."""

from __future__ import annotations


POSITION_CODE_MAP: dict[int, str] = {
    1: "GK",
    2: "DEF",
    3: "MID",
    4: "FWD",
}

MINUTES_THRESHOLD: int = 60

GOVERNED_SIGNAL_COLUMNS: tuple[str, ...] = (
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
    *GOVERNED_SIGNAL_COLUMNS,
    "total_points",
)
