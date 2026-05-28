"""DAL integrity tests — DGW row semantics. Contract: Section 5, Section 6, Section 9."""

from pathlib import Path

import pytest
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.validation import validate_dgw_correctness
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_dgw_fixture_count_two():
    """All is_dgw=True rows have fixture_count=2 — two fixtures, exactly. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    dgw_rows = spine[spine["is_dgw"] == True]
    assert not dgw_rows.empty, "No DGW rows found — expected at least one DGW in season data"
    bad = dgw_rows[dgw_rows["fixture_count"] != 2]
    assert bad.empty, (
        f"DGW rows with fixture_count != 2: {len(bad)} violations. "
        f"Sample: {bad[['player_id', 'gw', 'fixture_count']].head(5).to_dict('records')}"
    )


def test_dgw_home_away_count_sums_to_two():
    """All is_dgw=True rows have home_count + away_count == 2. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    dgw_rows = spine[spine["is_dgw"] == True]
    assert not dgw_rows.empty, "No DGW rows found"
    bad = dgw_rows[(dgw_rows["home_count"] + dgw_rows["away_count"]) != 2]
    assert bad.empty, (
        f"DGW home+away sum violation: {len(bad)} rows have home_count + away_count != 2"
    )


def test_dgw_fdr_avg_not_null():
    """All is_dgw=True rows have fdr_avg not null — DGW rows have fixtures. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    dgw_rows = spine[spine["is_dgw"] == True]
    assert not dgw_rows.empty, "No DGW rows found"
    bad = dgw_rows[dgw_rows["fdr_avg"].isna()]
    assert bad.empty, f"DGW FDR violation: {len(bad)} rows have fdr_avg null"


def test_dgw_clean_sheet_count_in_bounds():
    """All is_dgw=True rows have clean_sheets in {0, 1, 2} — count not binary. Contract Section 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    dgw_rows = spine[spine["is_dgw"] == True]
    assert not dgw_rows.empty, "No DGW rows found"
    bad = dgw_rows[~dgw_rows["clean_sheets"].isin([0, 1, 2])]
    assert bad.empty, (
        f"DGW clean sheet out of bounds: {len(bad)} rows with clean_sheets not in {{0, 1, 2}}"
    )


def test_dgw_correctness_via_validator():
    """validate_dgw_correctness passes on curated spine — all DGW invariants hold. Contract Section 4, 9."""
    spine = build_player_gameweek_spine(DB_PATH)
    validate_dgw_correctness(spine)
