"""Wave 2 — Contract Enforcement.

FAILING TESTS committed before any fixes.

SC-8: 8 GW context columns absent from DTYPES — never cast or type-checked.
V-1:  validate_column_contract exists but is never called in the live build.
V-2:  validate_row_completeness exists but is never called in the live build.
V-3:  invariants.py imports from dal.curated.contracts — upward coupling.
SC-5: validate_bgw_correctness uses != 0 on nullable types — misses non-null 0.0.
SC-6: validate_no_future_data uses != 0 on nullable types — same bug.
"""

import sys
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from dal.curated.contracts import SPINE_COLS, DTYPES, NULL_RULES, PERFORMANCE_COLS
from dal.validation.semantics import validate_bgw_correctness
from dal.validation.invariants import validate_no_future_data
from dal.exceptions import DALContractViolation

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


# ---------------------------------------------------------------------------
# SC-8 — GW context columns must be in DTYPES
# ---------------------------------------------------------------------------

def test_all_spine_cols_present_in_dtypes():
    """SC-8 FAILING TEST: set(SPINE_COLS) must equal set(DTYPES.keys()).

    8 GW context columns are in SPINE_COLS but missing from DTYPES:
    deadline_time, finished, is_previous, is_live, is_next,
    average_entry_score, highest_score, transfers_made.

    FAILS before fix (8 columns missing). PASSES after fix.
    """
    missing = set(SPINE_COLS) - set(DTYPES)
    extra = set(DTYPES) - set(SPINE_COLS)
    assert missing == set(), f"Columns in SPINE_COLS but missing from DTYPES: {sorted(missing)}"
    assert extra == set(), f"Columns in DTYPES but not in SPINE_COLS: {sorted(extra)}"


def test_all_spine_cols_present_in_null_rules():
    """NULL_RULES already covers all SPINE_COLS — regression guard."""
    missing = set(SPINE_COLS) - set(NULL_RULES)
    assert missing == set(), f"Columns in SPINE_COLS but missing from NULL_RULES: {sorted(missing)}"


# ---------------------------------------------------------------------------
# V-1 — validate_column_contract must be called in the live build
# ---------------------------------------------------------------------------

def test_validate_column_contract_called_in_spine_build():
    """V-1 FAILING TEST: validate_column_contract must be called during spine build.

    FAILS before fix (function exists but is not called). PASSES after fix.
    """
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine

    call_count = []

    original = None
    import dal.curated.player_gameweek_spine as spine_mod

    original_fn = spine_mod.validate_column_contract if hasattr(spine_mod, "validate_column_contract") else None

    with patch(
        "dal.curated.player_gameweek_spine.validate_column_contract",
        side_effect=lambda *a, **kw: call_count.append(1),
    ):
        build_player_gameweek_spine(TEST_DB_PATH)

    assert len(call_count) >= 1, (
        "validate_column_contract was not called during build_player_gameweek_spine. "
        "V-1: this function exists but is uncalled in the live build path."
    )


# ---------------------------------------------------------------------------
# V-2 — validate_row_completeness must be called in the live build
# ---------------------------------------------------------------------------

def test_validate_row_completeness_called_in_spine_build():
    """V-2 FAILING TEST: validate_row_completeness must be called during spine build.

    FAILS before fix (function exists but is not called). PASSES after fix.
    """
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine

    call_count = []

    with patch(
        "dal.curated.player_gameweek_spine.validate_row_completeness",
        side_effect=lambda *a, **kw: call_count.append(1),
    ):
        build_player_gameweek_spine(TEST_DB_PATH)

    assert len(call_count) >= 1, (
        "validate_row_completeness was not called during build_player_gameweek_spine. "
        "V-2: this function exists but is uncalled in the live build path."
    )


# ---------------------------------------------------------------------------
# V-3 — invariants.py must not import from dal.curated
# ---------------------------------------------------------------------------

def test_invariants_module_has_no_curated_imports():
    """V-3 FAILING TEST: dal.validation.invariants must not import from dal.curated.

    The module currently contains 'from dal.curated.contracts import PERFORMANCE_COLS',
    creating upward layer coupling. After the fix, the source must contain no reference
    to dal.curated imports.

    Checked directly on source text — immune to import caching order.
    FAILS before fix (source contains curated import). PASSES after fix.
    """
    import inspect
    import dal.validation.invariants as inv_mod
    importlib.reload(inv_mod)
    source = inspect.getsource(inv_mod)
    # Check for actual import statements, not comments or docstrings
    import_lines = [
        line.strip() for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and "dal.curated" in line
    ]
    assert import_lines == [], (
        f"dal.validation.invariants contains dal.curated import statement(s): {import_lines}. "
        "V-3: the validation layer must not import from the curated layer."
    )


# ---------------------------------------------------------------------------
# SC-5 — validate_bgw_correctness must catch non-null 0.0 on BGW rows
# ---------------------------------------------------------------------------

def test_bgw_validator_catches_float64_zero():
    """SC-5 FAILING TEST: validate_bgw_correctness must raise for Float64(0.0) on BGW row.

    Contract: performance columns on BGW rows must be NULL (pd.NA). Any non-null value,
    including 0.0, is a contract violation. The current check (col != 0) silently misses
    non-null 0.0 values.

    FAILS before fix (Float64(0.0) passes != 0 check). PASSES after fix (.notna()).
    """
    df = pd.DataFrame({
        "is_bgw": pd.array([True], dtype="boolean"),
        "is_dgw": pd.array([False], dtype="boolean"),
        "fixture_count": pd.array([0], dtype="int64"),
        "total_points": pd.array([None], dtype="Int64"),   # correct: null
        "minutes": pd.array([None], dtype="Int64"),        # correct: null
        "xg": pd.array([0.0], dtype="Float64"),            # WRONG: non-null 0.0 on BGW
        "xa": pd.array([None], dtype="Float64"),
        "xgi": pd.array([None], dtype="Float64"),
        "xgc": pd.array([None], dtype="Float64"),
        "goals_scored": pd.array([None], dtype="Int64"),
        "assists": pd.array([None], dtype="Int64"),
        "clean_sheets": pd.array([None], dtype="Int64"),
        "goals_conceded": pd.array([None], dtype="Int64"),
        "yellow_cards": pd.array([None], dtype="Int64"),
        "red_cards": pd.array([None], dtype="Int64"),
        "saves": pd.array([None], dtype="Int64"),
        "bonus": pd.array([None], dtype="Int64"),
        "bps": pd.array([None], dtype="Int64"),
        "starts": pd.array([None], dtype="Int64"),
        "penalties_saved": pd.array([None], dtype="Int64"),
        "penalties_missed": pd.array([None], dtype="Int64"),
        "own_goals": pd.array([None], dtype="Int64"),
        "influence": pd.array([None], dtype="Float64"),
        "creativity": pd.array([None], dtype="Float64"),
        "threat": pd.array([None], dtype="Float64"),
        "ict_index": pd.array([None], dtype="Float64"),
        "fdr_avg": pd.array([None], dtype="Float64"),
        "fdr_min": pd.array([None], dtype="Float64"),
        "fdr_max": pd.array([None], dtype="Float64"),
        "was_home": pd.array([None], dtype="boolean"),
    })
    with pytest.raises(DALContractViolation, match="xg"):
        validate_bgw_correctness(df, performance_cols=PERFORMANCE_COLS)


def test_bgw_validator_passes_for_pd_na():
    """SC-5: pd.NA on a BGW row must PASS — null is the correct BGW value.

    This must pass both before and after the fix.
    """
    df = pd.DataFrame({
        "is_bgw": pd.array([True], dtype="boolean"),
        "is_dgw": pd.array([False], dtype="boolean"),
        "fixture_count": pd.array([0], dtype="int64"),
        "total_points": pd.array([None], dtype="Int64"),
        "xg": pd.array([None], dtype="Float64"),
        "xa": pd.array([None], dtype="Float64"),
        "xgi": pd.array([None], dtype="Float64"),
        "xgc": pd.array([None], dtype="Float64"),
        "minutes": pd.array([None], dtype="Int64"),
        "goals_scored": pd.array([None], dtype="Int64"),
        "assists": pd.array([None], dtype="Int64"),
        "clean_sheets": pd.array([None], dtype="Int64"),
        "goals_conceded": pd.array([None], dtype="Int64"),
        "yellow_cards": pd.array([None], dtype="Int64"),
        "red_cards": pd.array([None], dtype="Int64"),
        "saves": pd.array([None], dtype="Int64"),
        "bonus": pd.array([None], dtype="Int64"),
        "bps": pd.array([None], dtype="Int64"),
        "starts": pd.array([None], dtype="Int64"),
        "penalties_saved": pd.array([None], dtype="Int64"),
        "penalties_missed": pd.array([None], dtype="Int64"),
        "own_goals": pd.array([None], dtype="Int64"),
        "influence": pd.array([None], dtype="Float64"),
        "creativity": pd.array([None], dtype="Float64"),
        "threat": pd.array([None], dtype="Float64"),
        "ict_index": pd.array([None], dtype="Float64"),
        "fdr_avg": pd.array([None], dtype="Float64"),
        "fdr_min": pd.array([None], dtype="Float64"),
        "fdr_max": pd.array([None], dtype="Float64"),
        "was_home": pd.array([None], dtype="boolean"),
    })
    validate_bgw_correctness(df, performance_cols=PERFORMANCE_COLS)  # must not raise


# ---------------------------------------------------------------------------
# SC-6 — validate_no_future_data must catch non-null 0.0 on future rows
# ---------------------------------------------------------------------------

def test_future_data_validator_catches_float64_zero():
    """SC-6 FAILING TEST: validate_no_future_data must raise for Float64(0.0) future rows.

    A future row with xg=0.0 is non-null — data exists for a future GW.
    The current check (col != 0) silently misses Float64(0.0).

    FAILS before fix (0.0 passes != 0 check). PASSES after fix (.notna()).
    """
    df = pd.DataFrame({
        "player_id": [1],
        "gw": [5],  # future GW (reference_gw=4)
        "total_points": pd.array([None], dtype="Int64"),
        "minutes": pd.array([None], dtype="Int64"),
        "xg": pd.array([0.0], dtype="Float64"),    # non-null 0.0 = data exists for future GW
        "xa": pd.array([None], dtype="Float64"),
        "xgi": pd.array([None], dtype="Float64"),
        "xgc": pd.array([None], dtype="Float64"),
        "goals_scored": pd.array([None], dtype="Int64"),
        "assists": pd.array([None], dtype="Int64"),
        "clean_sheets": pd.array([None], dtype="Int64"),
        "goals_conceded": pd.array([None], dtype="Int64"),
        "yellow_cards": pd.array([None], dtype="Int64"),
        "red_cards": pd.array([None], dtype="Int64"),
        "saves": pd.array([None], dtype="Int64"),
        "bonus": pd.array([None], dtype="Int64"),
        "bps": pd.array([None], dtype="Int64"),
        "starts": pd.array([None], dtype="Int64"),
        "penalties_saved": pd.array([None], dtype="Int64"),
        "penalties_missed": pd.array([None], dtype="Int64"),
        "own_goals": pd.array([None], dtype="Int64"),
        "influence": pd.array([None], dtype="Float64"),
        "creativity": pd.array([None], dtype="Float64"),
        "threat": pd.array([None], dtype="Float64"),
        "ict_index": pd.array([None], dtype="Float64"),
    })
    from dal.curated.contracts import PERFORMANCE_COLS
    with pytest.raises(DALContractViolation):
        validate_no_future_data(df, reference_gw=4, performance_cols=PERFORMANCE_COLS)


def test_future_data_validator_passes_for_all_null():
    """SC-6: future rows with all-null performance must pass."""
    df = pd.DataFrame({
        "player_id": [1],
        "gw": [5],
        "total_points": pd.array([None], dtype="Int64"),
        "xg": pd.array([None], dtype="Float64"),
        "xa": pd.array([None], dtype="Float64"),
        "xgi": pd.array([None], dtype="Float64"),
        "xgc": pd.array([None], dtype="Float64"),
        "minutes": pd.array([None], dtype="Int64"),
        "goals_scored": pd.array([None], dtype="Int64"),
        "assists": pd.array([None], dtype="Int64"),
        "clean_sheets": pd.array([None], dtype="Int64"),
        "goals_conceded": pd.array([None], dtype="Int64"),
        "yellow_cards": pd.array([None], dtype="Int64"),
        "red_cards": pd.array([None], dtype="Int64"),
        "saves": pd.array([None], dtype="Int64"),
        "bonus": pd.array([None], dtype="Int64"),
        "bps": pd.array([None], dtype="Int64"),
        "starts": pd.array([None], dtype="Int64"),
        "penalties_saved": pd.array([None], dtype="Int64"),
        "penalties_missed": pd.array([None], dtype="Int64"),
        "own_goals": pd.array([None], dtype="Int64"),
        "influence": pd.array([None], dtype="Float64"),
        "creativity": pd.array([None], dtype="Float64"),
        "threat": pd.array([None], dtype="Float64"),
        "ict_index": pd.array([None], dtype="Float64"),
    })
    from dal.curated.contracts import PERFORMANCE_COLS
    validate_no_future_data(df, reference_gw=4, performance_cols=PERFORMANCE_COLS)  # must not raise


# ---------------------------------------------------------------------------
# GRAIN_CONTRACTS registry
# ---------------------------------------------------------------------------

def test_grain_contracts_registry_exists():
    """Wave 2: dal/contracts.py must define GRAIN_CONTRACTS registry.

    FAILS before dal/contracts.py is created. PASSES after.
    """
    from dal.contracts import GRAIN_CONTRACTS
    assert isinstance(GRAIN_CONTRACTS, dict), "GRAIN_CONTRACTS must be a dict"
    required = {
        "player_gameweek_spine", "player_gameweek_state",
        "player_fixture_base", "player_opponent_context",
    }
    missing = required - set(GRAIN_CONTRACTS)
    assert not missing, f"GRAIN_CONTRACTS missing entries: {missing}"


def test_validate_grain_uniqueness_accepts_dataset_name():
    """Wave 2: validate_grain_uniqueness must accept dataset_name resolved from GRAIN_CONTRACTS.

    FAILS before the interface is updated. PASSES after.
    """
    from dal.validation.grain import validate_grain_uniqueness
    df = pd.DataFrame({"player_id": [1, 2], "gw": [1, 1]})
    # Should work by resolving grain from registry
    validate_grain_uniqueness(df, "player_gameweek_spine")
