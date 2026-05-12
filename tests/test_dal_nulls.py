"""DAL integrity tests — null semantics. Contract: Section 5, Section 6, Section 9."""

from pathlib import Path

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.validation import validate_null_semantics
from dal.exceptions import DALContractViolation

DB_PATH = Path.home() / ".fpl" / "fpl.db"

_IDENTITY_COLS = ["player_id", "gw", "player_name", "team_id", "position_code"]
_SCHEDULE_COLS = ["fixture_count", "is_bgw", "is_dgw", "home_count", "away_count"]
_PERFORMANCE_COLS = [
    "total_points", "minutes", "goals_scored", "assists",
    "clean_sheets", "yellow_cards", "red_cards", "saves",
    "bonus", "bps", "xg", "xa", "xgi", "goals_conceded", "xgc",
    "starts", "penalties_saved", "penalties_missed", "own_goals",
    "influence", "creativity", "threat", "ict_index",
]
_FDR_COLS = ["fdr_avg", "fdr_min", "fdr_max"]
_MARKET_COLS = ["transfers_in", "transfers_out", "ownership_count", "transfers_balance"]


def test_identity_columns_never_null():
    """Identity columns (player_id, gw, player_name, team_id, position_code) have zero nulls. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    for col in _IDENTITY_COLS:
        if col not in spine.columns:
            raise KeyError(
                f"Identity column '{col}' missing from spine — "
                f"Contract Section 5 requires this column to be never-null."
            )
        null_count = spine[col].isna().sum()
        assert null_count == 0, (
            f"Identity column '{col}' has {null_count} nulls — must be never-null"
        )


def test_schedule_columns_never_null():
    """Schedule columns (fixture_count, is_bgw, is_dgw, home_count, away_count) have zero nulls. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    for col in _SCHEDULE_COLS:
        if col not in spine.columns:
            raise KeyError(
                f"Schedule column '{col}' missing from spine — "
                f"Contract Section 5 requires this column to be never-null."
            )
        null_count = spine[col].isna().sum()
        assert null_count == 0, (
            f"Schedule column '{col}' has {null_count} nulls — must be never-null"
        )


def test_performance_columns_null_for_bgw():
    """BGW rows have performance columns == NULL, not zero — null means no fixture context. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    bgw_rows = spine[spine["is_bgw"] == True]  # KeyError if is_bgw missing
    if bgw_rows.empty:
        return
    for col in _PERFORMANCE_COLS:
        if col not in bgw_rows.columns:
            raise KeyError(
                f"Performance column '{col}' missing from spine — "
                f"cannot verify BGW null semantics."
            )
        null_count = bgw_rows[col].isna().sum()
        assert null_count == len(bgw_rows), (
            f"BGW rows have {len(bgw_rows) - null_count} non-null values in '{col}' — "
            f"all BGW performance columns must be NULL"
        )


def test_fdr_columns_null_for_bgw():
    """BGW rows have fdr_avg, fdr_min, fdr_max == NULL — no fixture means no difficulty. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    bgw_rows = spine[spine["is_bgw"] == True]  # KeyError if is_bgw missing
    if bgw_rows.empty:
        return
    for col in _FDR_COLS:
        if col not in spine.columns:
            raise KeyError(
                f"FDR column '{col}' missing from spine — "
                f"Contract Section 5 requires this column."
            )
        bad = bgw_rows[bgw_rows[col].notna()]
        assert bad.empty, (
            f"BGW rows have {len(bad)} non-null values in '{col}' — must be NULL for BGW"
        )


def test_market_columns_never_null():
    """Market columns (transfers_in, ownership_count, transfers_balance) have zero nulls across all rows. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    for col in _MARKET_COLS:
        if col not in spine.columns:
            raise KeyError(
                f"Market column '{col}' missing from spine — "
                f"Contract Section 5 requires this column to be never-null."
            )
        null_count = spine[col].isna().sum()
        assert null_count == 0, (
            f"Market column '{col}' has {null_count} nulls — must be never-null"
        )
