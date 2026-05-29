"""DAL integrity tests — BGW/DGW row semantics and null contracts. Contract: Sections 5, 6, 9."""

from pathlib import Path

import pytest
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.fct.validation import validate_bgw_correctness
from dal.exceptions import DALContractViolation
from dal.staging import load_staged_entities
from dal.intermediate.int_player_fixture import get_player_fixture_base

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_spine():
    staged = load_staged_entities(DB_PATH)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)

_IDENTITY_COLS = ["player_id", "gw", "player_name", "team_id", "position_code"]
_SCHEDULE_COLS = ["fixture_count", "is_bgw", "is_dgw", "home_count", "away_count"]
_PERFORMANCE_COLS = [
    "total_points", "minutes", "goals_scored", "assists",
    "clean_sheets", "yellow_cards", "red_cards", "saves",
    "bonus", "bps", "xg", "xa", "xgi", "goals_conceded", "xgc",
    "starts", "penalties_saved",
    "influence", "creativity", "threat", "ict_index",
]
_MARKET_COLS = ["transfers_in", "transfers_out", "ownership_count"]


def test_identity_columns_never_null():
    """Identity columns (player_id, gw, player_name, team_id, position_code) have zero nulls. Contract Section 5."""
    spine = _load_spine()
    for col in _IDENTITY_COLS:
        if col not in spine.columns:
            raise KeyError(f"Identity column '{col}' missing from spine.")
        null_count = spine[col].isna().sum()
        assert null_count == 0, f"Identity column '{col}' has {null_count} nulls — must be never-null"


def test_schedule_columns_never_null():
    """Schedule columns (fixture_count, is_bgw, is_dgw, home_count, away_count) have zero nulls. Contract Section 5."""
    spine = _load_spine()
    for col in _SCHEDULE_COLS:
        if col not in spine.columns:
            raise KeyError(f"Schedule column '{col}' missing from spine.")
        null_count = spine[col].isna().sum()
        assert null_count == 0, f"Schedule column '{col}' has {null_count} nulls — must be never-null"


def test_market_columns_never_null():
    """Market columns (transfers_in, transfers_out, ownership_count) have zero nulls. Contract Section 5."""
    spine = _load_spine()
    for col in _MARKET_COLS:
        if col not in spine.columns:
            raise KeyError(f"Market column '{col}' missing from spine.")
        null_count = spine[col].isna().sum()
        assert null_count == 0, f"Market column '{col}' has {null_count} nulls — must be never-null"


def test_bgw_fixture_count_zero():
    """All is_bgw=True rows have fixture_count=0 — no fixture, no count. Contract Section 5."""
    spine = _load_spine()
    bgw_rows = spine[spine["is_bgw"] == True]
    assert bgw_rows.empty or (bgw_rows["fixture_count"] == 0).all(), (
        f"BGW rows with fixture_count != 0: {(bgw_rows['fixture_count'] != 0).sum()} violations"
    )


def test_bgw_performance_columns_null():
    """BGW rows have performance columns == NULL — NULL means no fixture context, not zero. Contract Section 5, 6."""
    spine = _load_spine()
    bgw_rows = spine[spine["is_bgw"] == True]
    if bgw_rows.empty:
        return
    for col in _PERFORMANCE_COLS:
        if col not in bgw_rows.columns:
            raise KeyError(f"Performance column '{col}' missing from spine.")
        bad = bgw_rows[bgw_rows[col].notna()]
        assert bad.empty, f"BGW null violation: {len(bad)} rows have {col} not null"


def test_bgw_fdr_avg_null():
    """All is_bgw=True rows have fdr_avg == NULL — no fixture, no difficulty. Contract Section 5, 6."""
    spine = _load_spine()
    bgw_rows = spine[spine["is_bgw"] == True]
    if bgw_rows.empty:
        return
    bad = bgw_rows[bgw_rows["fdr_avg"].notna()]
    assert bad.empty, f"BGW FDR violation: {len(bad)} rows have fdr_avg not null"


def test_bgw_correctness_via_validator():
    """validate_bgw_correctness passes on fct spine — all BGW invariants hold. Contract Section 4, 9."""
    spine = _load_spine()
    validate_bgw_correctness(spine)
