"""DAL integrity tests — DGW row semantics. Contract: Section 5, Section 6, Section 9."""

from pathlib import Path

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.validation import validate_dgw_correctness
from dal.exceptions import DALContractViolation

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


def test_dgw_fdr_ordering():
    """All is_dgw=True rows satisfy fdr_min <= fdr_avg <= fdr_max. Contract Section 5, 6."""
    spine = build_player_gameweek_spine(DB_PATH)
    dgw_rows = spine[spine["is_dgw"] == True]
    assert not dgw_rows.empty, "No DGW rows found"

    for col in ("fdr_min", "fdr_avg", "fdr_max"):
        if col not in dgw_rows.columns:
            raise KeyError(
                f"FDR column '{col}' missing from spine — "
                f"cannot verify DGW FDR ordering. Contract Section 5 requires this column."
            )

    bad = dgw_rows[
        (dgw_rows["fdr_min"] > dgw_rows["fdr_avg"]) |
        (dgw_rows["fdr_avg"] > dgw_rows["fdr_max"])
    ]
    assert bad.empty, (
        f"DGW FDR ordering violation: {len(bad)} rows have fdr_min > fdr_avg or fdr_avg > fdr_max"
    )


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
