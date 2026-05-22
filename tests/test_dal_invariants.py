"""DAL integrity tests — system invariants. Contract: Section 7, Section 9."""

from pathlib import Path

import pytest
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.curated.contracts import SPINE_COLS, DTYPES
from dal.validation import validate_no_future_data, validate_column_contract
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"

EXPECTED_COLS = set(SPINE_COLS)

# Dtype strings must match str(df[col].dtype) — use pandas canonical names.
EXPECTED_DTYPES = {col: str(dtype) for col, dtype in DTYPES.items()}


def test_fixture_count_in_bounds():
    """Every row has fixture_count in {0, 1, 2} — no value outside this set is permitted. Contract Section 5."""
    spine = build_player_gameweek_spine(DB_PATH)
    bad = spine[~spine["fixture_count"].isin([0, 1, 2])]
    assert bad.empty, (
        f"fixture_count out of bounds: {len(bad)} rows with value outside {{0, 1, 2}}. "
        f"Sample: {bad[['player_id', 'gw', 'fixture_count']].head(5).to_dict('records')}"
    )


def test_no_future_data():
    """No performance data exists for GWs beyond the max ingested GW — temporal causality. Contract Section 5, 7."""
    spine = build_player_gameweek_spine(DB_PATH)
    max_ingested_gw = int(spine["gw"].max())
    validate_no_future_data(spine, reference_gw=max_ingested_gw)


def test_curated_column_set_exact():
    """Spine columns match Section 5 of DAL_CONTRACT.md exactly — no extras, no gaps.

    This is the permanent column contract enforcement test. Any column addition
    or removal requires updating both EXPECTED_COLS here and DAL_CONTRACT.md Section 5.
    """
    spine = build_player_gameweek_spine(DB_PATH)
    actual = set(spine.columns)
    extra = actual - EXPECTED_COLS
    missing = EXPECTED_COLS - actual
    assert not extra, f"Spine has extra columns not in Section 5: {sorted(extra)}"
    assert not missing, f"Spine is missing Section 5 columns: {sorted(missing)}"


def test_curated_column_dtypes_exact():
    """Every Section 5 column has the declared dtype — no silent coercions.

    This is the permanent dtype contract enforcement test. Any dtype change
    requires updating both EXPECTED_DTYPES here and DAL_CONTRACT.md Section 5.
    """
    spine = build_player_gameweek_spine(DB_PATH)
    validate_column_contract(spine, list(EXPECTED_COLS), EXPECTED_DTYPES)
