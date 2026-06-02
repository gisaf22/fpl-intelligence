"""DAL integrity tests — system invariants. Contract: Section 7, Section 9."""

import pytest

from dal.fct.fct_contracts import SPINE_COLS
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.fct.validation import validate_no_future_data
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities

pytestmark = pytest.mark.unit


def _load_spine(db_path):
    staged = load_staged_entities(db_path)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


EXPECTED_COLS = set(SPINE_COLS)


def test_no_future_data(db_path):
    """No performance data exists for GWs beyond the max ingested GW — temporal causality. Contract Section 5, 7."""
    spine = _load_spine(db_path)
    max_ingested_gw = int(spine["gw"].max())
    validate_no_future_data(spine, reference_gw=max_ingested_gw)


def test_curated_column_set_exact(db_path):
    """Spine columns match dal/fct/fct_contracts.py SPINE_COLS exactly — no extras, no gaps.

    Any column addition or removal requires updating both EXPECTED_COLS here and fct_contracts.SPINE_COLS.
    """
    spine = _load_spine(db_path)
    actual = set(spine.columns)
    extra = actual - EXPECTED_COLS
    missing = EXPECTED_COLS - actual
    assert not extra, f"Spine has extra columns not in Section 5: {sorted(extra)}"
    assert not missing, f"Spine is missing Section 5 columns: {sorted(missing)}"
