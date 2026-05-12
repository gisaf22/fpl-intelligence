"""Tests for pipeline DAL support helpers — live DB."""

from pathlib import Path

import pytest

from weekly.db import (
    get_fixtures_for_pipeline,
    get_player_histories_for_pipeline,
    get_players_for_pipeline,
    resolve_target_gw,
    validate_data_freshness,
)
from dal.exceptions import DataFreshnessError

DB_PATH = Path.home() / ".fpl" / "fpl.db"

_PIPELINE_REQUIRED_COLS = [
    "player_id",
    "player_name",
    "team_id",
    "position_code",
    "purchase_price",
    "total_points",
    "minutes",
    "status",
    "selected_by_percent",
    "transfers_in_event",
    "transfers_out_event",
]


def test_get_players_for_pipeline_returns_dataframe():
    df = get_players_for_pipeline(DB_PATH)
    assert not df.empty


def test_get_players_for_pipeline_no_unavailable():
    df = get_players_for_pipeline(DB_PATH)
    assert (df["status"] == "u").sum() == 0


def test_get_players_for_pipeline_required_cols_present():
    df = get_players_for_pipeline(DB_PATH)
    for col in _PIPELINE_REQUIRED_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_get_players_for_pipeline_no_nulls_in_required():
    df = get_players_for_pipeline(DB_PATH)
    for col in _PIPELINE_REQUIRED_COLS:
        assert df[col].isna().sum() == 0, f"Nulls found in {col}"


def test_get_fixtures_for_pipeline_returns_correct_gw():
    df = get_fixtures_for_pipeline(DB_PATH, gw=1)
    assert not df.empty
    assert (df["gw"] == 1).all()


def test_get_fixtures_for_pipeline_raises_for_missing_gw():
    with pytest.raises(ValueError, match="No fixtures found for GW 9999"):
        get_fixtures_for_pipeline(DB_PATH, gw=9999)


def test_get_player_histories_for_pipeline_window():
    df = get_player_histories_for_pipeline(DB_PATH, gw_from=5, gw_to=10)
    assert not df.empty
    assert df["gw"].min() >= 5
    assert df["gw"].max() <= 10


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
