"""DAL integrity tests — BGW row semantics. Contract: Section 5, Section 6, Section 9."""

from pathlib import Path

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.validation import validate_bgw_correctness
from dal.exceptions import DALContractViolation

DB_PATH = Path.home() / ".fpl" / "fpl.db"

_PERFORMANCE_COLS = [
    "total_points", "minutes", "goals_scored", "assists",
    "clean_sheets", "yellow_cards", "red_cards", "saves",
    "bonus", "bps", "xg", "xa", "xgi", "goals_conceded", "xgc",
    "starts", "penalties_saved", "penalties_missed", "own_goals",
    "influence", "creativity", "threat", "ict_index",
]


def test_bgw_fixture_count_zero():
    """All is_bgw=True rows have fixture_count=0 — no fixture, no count. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    bgw_rows = spine[spine["is_bgw"] == True]  # KeyError if is_bgw missing
    assert bgw_rows.empty or (bgw_rows["fixture_count"] == 0).all(), (
        f"BGW rows with fixture_count != 0: "
        f"{(bgw_rows['fixture_count'] != 0).sum()} violations"
    )


def test_bgw_performance_columns_zero():
    """All is_bgw=True rows have performance columns == 0 — zero not null. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    bgw_rows = spine[spine["is_bgw"] == True]  # KeyError if is_bgw missing
    if bgw_rows.empty:
        return
    for col in _PERFORMANCE_COLS:
        if col not in bgw_rows.columns:
            raise KeyError(
                f"Performance column '{col}' missing from spine — "
                f"cannot verify BGW zero semantics. Contract Section 5 requires this column."
            )
        bad = bgw_rows[bgw_rows[col] != 0]
        assert bad.empty, (
            f"BGW performance violation: {len(bad)} rows have {col} != 0"
        )


def test_bgw_fdr_columns_null():
    """All is_bgw=True rows have fdr_avg, fdr_min, fdr_max == NULL — no fixture, no difficulty. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    bgw_rows = spine[spine["is_bgw"] == True]  # KeyError if is_bgw missing
    if bgw_rows.empty:
        return
    for col in ("fdr_avg", "fdr_min", "fdr_max"):
        if col not in bgw_rows.columns:
            raise KeyError(
                f"FDR column '{col}' missing from spine — "
                f"cannot verify BGW null semantics. Contract Section 5 requires this column."
            )
        bad = bgw_rows[bgw_rows[col].notna()]
        assert bad.empty, (
            f"BGW FDR violation: {len(bad)} rows have {col} not null"
        )


def test_bgw_correctness_via_validator():
    """validate_bgw_correctness passes on curated spine — all BGW invariants hold. Contract Section 4, 9."""
    spine = build_player_gameweek_spine(DB_PATH)
    validate_bgw_correctness(spine)  # KeyError on is_bgw if missing; DALContractViolation if invariant violated
