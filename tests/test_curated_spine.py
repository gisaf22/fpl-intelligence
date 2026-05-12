"""Tests for pipeline/dal/curated/player_gameweek_spine.py — live DB."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.curated.contracts import SPINE_COLS
from dal.intermediate.player_fixture import get_player_fixture_base
from dal.exceptions import DALContractViolation

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_spine_column_presence():
    """Spine returns exactly the columns declared in SPINE_COLS — no more, no fewer."""
    df = build_player_gameweek_spine(DB_PATH)
    assert set(df.columns) == set(SPINE_COLS), (
        f"Column mismatch. Extra: {set(df.columns) - set(SPINE_COLS)}. "
        f"Missing: {set(SPINE_COLS) - set(df.columns)}"
    )
    assert len(df.columns) == len(SPINE_COLS), f"Expected {len(SPINE_COLS)} columns, got {len(df.columns)}"


def test_spine_grain_violation_raises(monkeypatch):
    """Patching the aggregation step to return duplicate (player_id, gw) raises GrainViolationError."""
    import dal.curated.player_gameweek_spine as spine_mod

    real_aggregate = spine_mod._aggregate_to_gw_grain

    def patched_aggregate(df):
        result = real_aggregate(df)
        return pd.concat([result, result.iloc[[0]]], ignore_index=True)

    monkeypatch.setattr(spine_mod, "_aggregate_to_gw_grain", patched_aggregate)

    with pytest.raises(DALContractViolation):
        spine_mod.build_player_gameweek_spine(DB_PATH)


def test_spine_dgw_aggregation():
    """GW 26 DGW players have fixture_count == 2 and is_dgw == True; no (player_id, gw) duplicates."""
    spine = build_player_gameweek_spine(DB_PATH)
    gw26 = spine[spine["gw"] == 26]

    assert not gw26.empty, "Expected GW 26 rows in spine"
    assert not gw26.duplicated(subset=["player_id", "gw"]).any(), "Duplicate (player_id, gw) in GW 26"

    dgw_rows = gw26[gw26["fixture_count"] >= 2]
    sgw_rows = gw26[gw26["fixture_count"] < 2]

    assert not dgw_rows.empty, "Expected some DGW players in GW 26"
    assert (dgw_rows["is_dgw"] == True).all(), "DGW players must have is_dgw == True"
    assert (sgw_rows["is_dgw"] == False).all(), "SGW players in GW 26 must have is_dgw == False"


def test_spine_total_points_sum_correctness():
    """For a known GW 26 player, spine total_points equals sum of per-fixture total_points."""
    analytics_gw26 = get_player_fixture_base(DB_PATH, gw=26)
    first_player_id = int(analytics_gw26["player_id"].iloc[0])

    player_fixtures = analytics_gw26[analytics_gw26["player_id"] == first_player_id]
    expected_points = int(player_fixtures["total_points"].sum())

    spine = build_player_gameweek_spine(DB_PATH)
    spine_row = spine[(spine["player_id"] == first_player_id) & (spine["gw"] == 26)]

    assert len(spine_row) == 1, f"Expected one spine row for player {first_player_id} in GW 26"
    actual_points = int(spine_row["total_points"].iloc[0])

    assert actual_points == expected_points, (
        f"Player {first_player_id} GW 26: spine total_points={actual_points}, "
        f"expected sum={expected_points}"
    )


def test_home_away_count_correctness():
    """home_count + away_count == fixture_count for DGW rows; both sum to 1 for GW 1."""
    spine = build_player_gameweek_spine(DB_PATH)

    dgw_rows = spine[(spine["gw"] == 26) & (spine["is_dgw"] == True)]
    assert not dgw_rows.empty, "Expected DGW rows in GW 26"
    assert ((dgw_rows["home_count"] + dgw_rows["away_count"]) == dgw_rows["fixture_count"]).all()

    gw1_played = spine[(spine["gw"] == 1) & (spine["fixture_count"] == 1)]
    assert not gw1_played.empty, "Expected played GW 1 rows in spine"
    assert ((gw1_played["home_count"] + gw1_played["away_count"]) == 1).all()
    assert gw1_played["home_count"].isin([0, 1]).all()
    assert gw1_played["away_count"].isin([0, 1]).all()


def test_spine_sgw_rows_unaffected():
    """GW 1 played rows must have fixture_count == 1 and is_dgw == False."""
    spine = build_player_gameweek_spine(DB_PATH)
    gw1_played = spine[(spine["gw"] == 1) & (~spine["is_bgw"])]

    assert not gw1_played.empty, "Expected played GW 1 rows in spine"
    assert (gw1_played["fixture_count"] == 1).all(), "All GW 1 played rows should have fixture_count == 1"
    assert (gw1_played["is_dgw"] == False).all(), "All GW 1 played rows should have is_dgw == False"
