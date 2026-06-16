"""Registry-build signal set — the controlled list of signals the registry characterizes.

The vocabulary of *which* signals the registry build consumes is ontology, not
construction, so it lives in ``domain/`` (the shared leaf). ``research`` builds
the finding from this set; the prepared-dataset output schema that wraps it is
``domain.registry.population.OUTPUT_COLUMNS``.
"""

from __future__ import annotations

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
    "own_goals",
    "penalties_missed",
    "penalties_saved",
    "tackles",
    "clearances_blocks_interceptions",
    "recoveries",
    "defensive_contribution",
)
