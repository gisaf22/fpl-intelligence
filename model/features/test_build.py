"""Tests for model.features.build — the leakage property + the team_gw->player_gw broadcast."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.features.build import broadcast

pytestmark = pytest.mark.unit


def _player_mart() -> pd.DataFrame:
    """Player-grain rows: 3 teams x 2 gws, a few players each (uneven, to exercise the fan-out)."""
    rows = []
    for team in (10, 20, 30):
        for gw in (1, 2):
            n_players = {10: 3, 20: 2, 30: 1}[team]
            for p in range(n_players):
                rows.append({"player_id": team * 100 + p, "team_id": team, "gw": gw, "minutes": 90})
    return pd.DataFrame(rows)


def _team_frame() -> pd.DataFrame:
    """Team-grain frame, unique on (team_id, gw), with one team-fixture deliberately missing (30, gw2)."""
    return pd.DataFrame([
        {"team_id": 10, "gw": 1, "p_cs": 0.4, "e_conceded_pts": -0.5},
        {"team_id": 10, "gw": 2, "p_cs": 0.5, "e_conceded_pts": -0.4},
        {"team_id": 20, "gw": 1, "p_cs": 0.2, "e_conceded_pts": -0.8},
        {"team_id": 20, "gw": 2, "p_cs": 0.3, "e_conceded_pts": -0.7},
        {"team_id": 30, "gw": 1, "p_cs": 0.6, "e_conceded_pts": -0.3},
        # (30, gw2) intentionally absent -> those player rows must broadcast to NaN
    ])


def test_broadcast_fans_out_one_to_many_without_multiplying_rows() -> None:
    mart = _player_mart()
    out = broadcast(mart, _team_frame(), ["p_cs", "e_conceded_pts"])
    # No row multiplication and index preserved (positional realignment is valid on a unique right side).
    assert len(out) == len(mart)
    assert out.index.equals(mart.index)
    assert list(out.columns) == ["p_cs", "e_conceded_pts"]
    # Every player of (team 10, gw 1) gets that fixture's value.
    joined = mart.join(out)
    t10g1 = joined[(joined["team_id"] == 10) & (joined["gw"] == 1)]
    assert (t10g1["p_cs"] == 0.4).all()
    assert len(t10g1) == 3  # all three players present, not collapsed


def test_broadcast_is_nan_where_the_team_fixture_is_absent() -> None:
    mart = _player_mart()
    out = broadcast(mart, _team_frame(), ["p_cs"])
    joined = mart.join(out)
    absent = joined[(joined["team_id"] == 30) & (joined["gw"] == 2)]
    assert len(absent) == 1
    assert absent["p_cs"].isna().all()


def test_broadcast_rejects_a_non_unique_team_frame() -> None:
    """A duplicated (team_id, gw) would silently multiply player rows — must raise, not fan out."""
    dup = pd.concat([_team_frame(), _team_frame().iloc[[0]]], ignore_index=True)
    with pytest.raises(AssertionError, match="not unique"):
        broadcast(_player_mart(), dup, ["p_cs"])


def test_broadcast_raises_on_missing_key_or_column() -> None:
    mart = _player_mart()
    with pytest.raises(KeyError, match="keys absent"):
        broadcast(mart.drop(columns=["team_id"]), _team_frame(), ["p_cs"])
    with pytest.raises(KeyError, match="columns absent"):
        broadcast(mart, _team_frame(), ["not_a_column"])


def test_broadcast_matches_a_plain_left_merge() -> None:
    """Golden: broadcast == the inline merge it replaces (points_model.walk_forward_points)."""
    mart, team = _player_mart(), _team_frame()
    ref = mart.merge(team[["team_id", "gw", "p_cs", "e_conceded_pts"]], on=["team_id", "gw"], how="left")
    out = broadcast(mart, team, ["p_cs", "e_conceded_pts"])
    np.testing.assert_array_equal(out["p_cs"].to_numpy(), ref["p_cs"].to_numpy())
    np.testing.assert_array_equal(out["e_conceded_pts"].to_numpy(), ref["e_conceded_pts"].to_numpy())
