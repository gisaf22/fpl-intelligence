"""Tests for weekly DB helpers — live DB."""

from pathlib import Path

import pytest

from dal.exceptions import DataFreshnessError
from dal.fct.fct_gameweek_context import resolve_target_gw
from dal.staging import validate_data_freshness

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_resolve_target_gw_returns_valid_gw():
    gw = resolve_target_gw(DB_PATH)
    assert isinstance(gw, int)
    assert 1 <= gw <= 38


def test_validate_data_freshness_passes_for_current_gw():
    gw = resolve_target_gw(DB_PATH)
    validate_data_freshness(DB_PATH, gw=gw)  # should not raise


def test_validate_data_freshness_raises_for_missing_gw():
    with pytest.raises(DataFreshnessError):
        validate_data_freshness(DB_PATH, gw=9999)
