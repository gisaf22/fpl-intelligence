"""Wave 3 — Determinism Hardening.

FAILING TESTS committed before any fixes.

D-1:  No ORDER BY in staging SQL — row order is filesystem-defined.
SC-9: FIRST_COLS aggregation result depends on staging row order.
F-1:  FIRST_COLS semantic type undeclared — hidden aggregation policy.
F-2:  invariant_per_gw columns not asserted for within-GW invariance.
Reproducibility: two spine builds must produce byte-identical output.
"""

import pandas as pd
import pytest
from pathlib import Path

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


# ---------------------------------------------------------------------------
# D-1 — ORDER BY must appear in all 6 staging SQL queries
# ---------------------------------------------------------------------------

def test_staging_sql_contains_order_by_players():
    """D-1 FAILING TEST: staging SQL for players must contain ORDER BY.

    FAILS before fix (no ORDER BY). PASSES after fix.
    """
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("players"))
    assert "ORDER BY" in query, (
        f"players staging query has no ORDER BY — row order is filesystem-defined.\n{query}"
    )


def test_staging_sql_contains_order_by_player_histories():
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("player_histories"))
    assert "ORDER BY" in query, f"player_histories staging query has no ORDER BY.\n{query}"


def test_staging_sql_contains_order_by_fixtures():
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("fixtures"))
    assert "ORDER BY" in query, f"fixtures staging query has no ORDER BY.\n{query}"


def test_staging_sql_contains_order_by_teams():
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("teams"))
    assert "ORDER BY" in query, f"teams staging query has no ORDER BY.\n{query}"


def test_staging_sql_contains_order_by_events():
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("events"))
    assert "ORDER BY" in query, f"events staging query has no ORDER BY.\n{query}"


def test_staging_sql_contains_order_by_element_types():
    from dal.staging.transformer import _build_query
    from dal.staging.schema import load_schema
    query = _build_query(load_schema("element_types"))
    assert "ORDER BY" in query, f"element_types staging query has no ORDER BY.\n{query}"


# ---------------------------------------------------------------------------
# F-1 — FIRST_COL_SEMANTICS registry must exist in curated contracts
# ---------------------------------------------------------------------------

def test_first_col_semantics_registry_exists():
    """F-1 FAILING TEST: FIRST_COL_SEMANTICS must be defined in dal/curated/contracts.py.

    Every FIRST_COLS entry must be classified as one of:
    invariant_per_gw, canonical_first_fixture, temporally_first, representative_arbitrary.

    FAILS before fix (FIRST_COL_SEMANTICS not defined). PASSES after fix.
    """
    from dal.curated.contracts import FIRST_COL_SEMANTICS, FIRST_COLS
    valid_types = {"invariant_per_gw", "canonical_first_fixture", "temporally_first",
                   "representative_arbitrary"}
    for col in FIRST_COLS:
        assert col in FIRST_COL_SEMANTICS, (
            f"FIRST_COLS column '{col}' is not classified in FIRST_COL_SEMANTICS. "
            f"Every FIRST_COLS entry must have a declared semantic type."
        )
        assert FIRST_COL_SEMANTICS[col] in valid_types, (
            f"FIRST_COLS column '{col}' has invalid semantic type "
            f"'{FIRST_COL_SEMANTICS[col]}'. Must be one of {valid_types}."
        )


# ---------------------------------------------------------------------------
# F-2 — invariant_per_gw assertion must fire on violation
# ---------------------------------------------------------------------------

def test_invariant_per_gw_assertion_catches_violation():
    """F-2 FAILING TEST: invariant_per_gw columns must be asserted before aggregation.

    Construct a fixture-grain frame where purchase_price differs across two fixtures
    for the same (player_id, gw). Assert DALContractViolation raised before aggregation.

    FAILS before fix (no assertion). PASSES after fix.
    """
    from dal.curated.player_gameweek_spine import _aggregate_to_gw_grain
    from dal.exceptions import DALContractViolation

    df = pd.DataFrame([
        # Same player/gw, two fixtures, different purchase_price — violates invariant_per_gw
        {"player_id": 1, "gw": 1, "fixture_id": 10, "was_home": 1,
         "player_name": "Test", "position_code": 4, "position_label": "FWD",
         "team_id": 1, "purchase_price": 7.5, "ownership_count": 1000,
         "transfers_in": 100, "transfers_out": 50, "transfers_balance": 50,
         "total_points": 6, "minutes": 90, "goals_scored": 1, "assists": 0,
         "clean_sheets": 0, "yellow_cards": 0, "red_cards": 0, "saves": 0,
         "bonus": 2, "bps": 20, "goals_conceded": 1, "xg": 0.5, "xa": 0.1,
         "xgi": 0.6, "xgc": 0.3, "home_count": 1, "away_count": 0,
         "starts": 1, "penalties_saved": 0, "penalties_missed": 0, "own_goals": 0,
         "influence": 30.0, "creativity": 20.0, "threat": 40.0, "ict_index": 9.0,
         "in_dreamteam": 0, "fixture_difficulty": 3},
        {"player_id": 1, "gw": 1, "fixture_id": 11, "was_home": 0,
         "player_name": "Test", "position_code": 4, "position_label": "FWD",
         "team_id": 1, "purchase_price": 8.0,  # DIFFERENT — violates invariant_per_gw
         "ownership_count": 1000,
         "transfers_in": 100, "transfers_out": 50, "transfers_balance": 50,
         "total_points": 4, "minutes": 90, "goals_scored": 0, "assists": 1,
         "clean_sheets": 0, "yellow_cards": 0, "red_cards": 0, "saves": 0,
         "bonus": 1, "bps": 15, "goals_conceded": 2, "xg": 0.2, "xa": 0.4,
         "xgi": 0.6, "xgc": 0.5, "home_count": 0, "away_count": 1,
         "starts": 1, "penalties_saved": 0, "penalties_missed": 0, "own_goals": 0,
         "influence": 20.0, "creativity": 25.0, "threat": 30.0, "ict_index": 7.5,
         "in_dreamteam": 0, "fixture_difficulty": 4},
    ])

    with pytest.raises(DALContractViolation):
        _aggregate_to_gw_grain(df)


# ---------------------------------------------------------------------------
# Reproducibility — two runs must produce byte-identical output
# ---------------------------------------------------------------------------

def test_full_pipeline_is_reproducible():
    """Primary determinism regression test: two spine builds must be identical.

    FAILS if any non-determinism exists (e.g. unordered aggregation, random hashing).
    This test runs on every PR.
    """
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine

    result1 = build_player_gameweek_spine(TEST_DB_PATH)
    result2 = build_player_gameweek_spine(TEST_DB_PATH)

    pd.testing.assert_frame_equal(result1, result2, check_like=False)
