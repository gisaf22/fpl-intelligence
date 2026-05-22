"""Unit tests for registry.builder._build_registry_population."""

from __future__ import annotations

import pandas as pd
import pytest

from signals.registry.builder import _build_registry_population as build_prepared_dataset
from signals.registry.population import (
    GOVERNED_SIGNAL_COLUMNS,
    MINUTES_THRESHOLD,
    OUTPUT_COLUMNS,
    POSITION_CODE_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_spine(
    n_players: int = 3,
    gws: list[int] | None = None,
    minutes_values: list[int] | None = None,
    position_code: int = 3,
) -> pd.DataFrame:
    """Build a minimal synthetic spine satisfying the curated spine contract."""
    if gws is None:
        gws = list(range(1, 6))

    rows = []
    for pid in range(1, n_players + 1):
        for gw in gws:
            minutes = 90 if minutes_values is None else minutes_values[(pid * len(gws) + gw) % len(minutes_values)]
            rows.append({
                "player_id": pid,
                "gw": gw,
                "position_code": position_code,
                "minutes": minutes,
                "total_points": pid + gw,
                # Signal columns — use simple deterministic values
                "goals_scored": 0,
                "assists": 0,
                "clean_sheets": 1 if pid == 1 else 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "saves": 0,
                "bonus": 0,
                "bps": pid,
                "goals_conceded": 0,
                "xg": float(pid) * 0.1,
                "xa": float(pid) * 0.05,
                "xgi": float(pid) * 0.15,
                "xgc": float(pid) * 0.2,
                "fdr_avg": 3.0,
                "fdr_min": 2.0,
                "fdr_max": 4.0,
                "transfers_balance": 0,
                "fixture_count": 1,
                "was_home": True,
                "starts": 1,
                "influence": float(pid) * 5.0,
                "creativity": float(pid) * 3.0,
                "threat": float(pid) * 4.0,
                "ict_index": float(pid) * 2.0,
                "ownership_count": pid * 1000,
                "purchase_price": 6.0 + pid * 0.5,
                "transfers_in": pid * 100,
                "transfers_out": pid * 50,
            })

    return pd.DataFrame(rows)


def _spine_with_bgw(n_players: int = 2) -> pd.DataFrame:
    """Spine with BGW rows (minutes=None) mixed with normal rows."""
    rows = []
    for pid in range(1, n_players + 1):
        for gw in range(1, 6):
            is_bgw = gw == 3
            minutes = None if is_bgw else 90
            rows.append({
                "player_id": pid,
                "gw": gw,
                "position_code": 2,
                "minutes": minutes,
                "total_points": None if is_bgw else pid + gw,
                "goals_scored": None if is_bgw else 0,
                "assists": None if is_bgw else 0,
                "clean_sheets": None if is_bgw else 0,
                "yellow_cards": None if is_bgw else 0,
                "red_cards": None if is_bgw else 0,
                "saves": None if is_bgw else 0,
                "bonus": None if is_bgw else 0,
                "bps": None if is_bgw else pid,
                "goals_conceded": None if is_bgw else 0,
                "xg": None if is_bgw else 0.1,
                "xa": None if is_bgw else 0.05,
                "xgi": None if is_bgw else 0.15,
                "xgc": None if is_bgw else 0.2,
                "fdr_avg": None if is_bgw else 3.0,
                "fdr_min": None if is_bgw else 2.0,
                "fdr_max": None if is_bgw else 4.0,
                "transfers_balance": 0,
                "fixture_count": 0 if is_bgw else 1,
                "was_home": None if is_bgw else True,
                "starts": None if is_bgw else 1,
                "influence": None if is_bgw else 5.0,
                "creativity": None if is_bgw else 3.0,
                "threat": None if is_bgw else 4.0,
                "ict_index": None if is_bgw else 2.0,
                "ownership_count": 1000,
                "purchase_price": 6.0,
                "transfers_in": 100,
                "transfers_out": 50,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Output column contract
# ---------------------------------------------------------------------------

def test_output_columns_include_required_fields():
    spine = _make_spine()
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    assert "player_id" in result.columns
    assert "gw" in result.columns
    assert "position" in result.columns
    assert "total_points" in result.columns


def test_output_includes_all_governed_signal_columns():
    spine = _make_spine()
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    for col in GOVERNED_SIGNAL_COLUMNS:
        assert col in result.columns, f"missing governed signal column: {col}"


def test_position_code_not_in_output():
    """position_code is mapped to position string and must not appear in output."""
    spine = _make_spine()
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    assert "position_code" not in result.columns


# ---------------------------------------------------------------------------
# Position code mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,expected", list(POSITION_CODE_MAP.items()))
def test_position_code_mapped_correctly(code: int, expected: str):
    spine = _make_spine(position_code=code)
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    assert set(result["position"].unique()) == {expected}


def test_unknown_position_code_raises():
    spine = _make_spine(position_code=99)
    with pytest.raises(ValueError, match="unrecognized position_code"):
        build_prepared_dataset(spine, data_cutoff_gw=5)


# ---------------------------------------------------------------------------
# Grain uniqueness
# ---------------------------------------------------------------------------

def test_grain_is_unique():
    spine = _make_spine(n_players=5, gws=list(range(1, 10)))
    result = build_prepared_dataset(spine, data_cutoff_gw=9)
    assert not result[["player_id", "gw"]].duplicated().any()


def test_grain_violation_raises():
    """If spine already has duplicate (player_id, gw) after filters, raise."""
    spine = _make_spine(n_players=2, gws=[1, 2])
    duplicated = pd.concat([spine, spine], ignore_index=True)
    with pytest.raises(ValueError, match="grain violation"):
        build_prepared_dataset(duplicated, data_cutoff_gw=2)


# ---------------------------------------------------------------------------
# Minutes filter enforcement
# ---------------------------------------------------------------------------

def test_rows_with_minutes_below_threshold_excluded():
    spine = _make_spine(n_players=3, gws=[1, 2, 3])
    # Set player 2, gw 2 to minutes = 30
    spine.loc[(spine["player_id"] == 2) & (spine["gw"] == 2), "minutes"] = 30
    result = build_prepared_dataset(spine, data_cutoff_gw=3)
    excluded = result[(result["player_id"] == 2) & (result["gw"] == 2)]
    assert len(excluded) == 0


def test_rows_at_threshold_boundary_included():
    spine = _make_spine(n_players=2, gws=[1])
    spine.loc[spine["player_id"] == 1, "minutes"] = MINUTES_THRESHOLD
    result = build_prepared_dataset(spine, data_cutoff_gw=1)
    included = result[result["player_id"] == 1]
    assert len(included) == 1


def test_bgw_rows_excluded_by_minutes_filter():
    """BGW rows have minutes=None. None >= 60 → False → excluded."""
    spine = _spine_with_bgw(n_players=2)
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    # GW 3 was a BGW; should not appear in output
    assert 3 not in result["gw"].values


def test_all_low_minutes_raises():
    spine = _make_spine(n_players=2, gws=[1, 2])
    spine["minutes"] = 30
    with pytest.raises(ValueError, match="no rows remain after filtering"):
        build_prepared_dataset(spine, data_cutoff_gw=2)


# ---------------------------------------------------------------------------
# GW bound enforcement
# ---------------------------------------------------------------------------

def test_rows_above_cutoff_excluded():
    spine = _make_spine(n_players=2, gws=list(range(1, 10)))
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    assert result["gw"].max() <= 5


def test_cutoff_gw_row_included():
    """Row exactly at data_cutoff_gw must be included."""
    spine = _make_spine(n_players=2, gws=[5])
    result = build_prepared_dataset(spine, data_cutoff_gw=5)
    assert 5 in result["gw"].values


def test_invalid_cutoff_gw_raises():
    spine = _make_spine()
    with pytest.raises(ValueError, match="data_cutoff_gw must be positive"):
        build_prepared_dataset(spine, data_cutoff_gw=0)


def test_cutoff_gw_before_all_data_raises():
    spine = _make_spine(gws=list(range(10, 16)))
    with pytest.raises(ValueError, match="no rows remain after applying data_cutoff_gw"):
        build_prepared_dataset(spine, data_cutoff_gw=5)


# ---------------------------------------------------------------------------
# Missing required columns
# ---------------------------------------------------------------------------

def test_raises_on_missing_spine_column():
    spine = _make_spine()
    spine = spine.drop(columns=["xg"])
    with pytest.raises(ValueError, match="spine missing required columns"):
        build_prepared_dataset(spine, data_cutoff_gw=5)
