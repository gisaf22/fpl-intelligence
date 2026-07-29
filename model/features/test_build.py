"""Tests for model.features.build — the leakage property + the team_gw->player_gw broadcast."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.features.build import (
    add_lagged_rolls,
    add_opponent_xgc_forward,
    assert_lag_safe,
    assert_lag_safe_team,
    broadcast,
)
from model.features.spec import FeaturePool, FeatureSpec

pytestmark = pytest.mark.unit


def test_add_lagged_rolls_is_strictly_prior_and_grouped() -> None:
    df = pd.DataFrame({
        "player_id": [1, 1, 1, 2, 2],
        "gw": [1, 2, 3, 1, 2],
        "xg": [0.2, 0.8, 0.5, 1.0, 0.0],
    })
    out = add_lagged_rolls(df, ["xg"], (2,))
    # First appearance of each player is NaN (shift(1) -> no prior); windows never cross the player boundary.
    assert pd.isna(out.loc[0, "xg_roll2"]) and pd.isna(out.loc[3, "xg_roll2"])
    assert out.loc[1, "xg_roll2"] == pytest.approx(0.2)          # prior of player 1 gw2 = [0.2]
    assert out.loc[2, "xg_roll2"] == pytest.approx((0.2 + 0.8) / 2)
    assert out.loc[4, "xg_roll2"] == pytest.approx(1.0)          # player 2 gw2 sees only player 2's gw1


def test_add_lagged_rolls_skips_absent_sources() -> None:
    df = pd.DataFrame({"player_id": [1, 1], "gw": [1, 2], "xg": [0.3, 0.4]})
    out = add_lagged_rolls(df, ["xg", "xa"], (2,))   # no xa column present
    assert "xg_roll2" in out.columns
    assert "xa_roll2" not in out.columns             # absent source is a no-op, not an error


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


# ---------------------------------------------------------------------------------------------
# opp_xgc_forward — the opponent-forward materialize path (mean-features step-2, REFUTED but kept as
# tested infra): a strictly-prior TEAM roll of conceded-xG, broadcast onto players by OPPONENT identity.
# ---------------------------------------------------------------------------------------------


def _opp_panel(*, drop_team20_gw3: bool = False) -> pd.DataFrame:
    """Two teams (10, 20) facing each other each gw, 2 players/side. ``xgc`` is a team's own conceded-xG.

    team_xgc per (team, gw): 10 -> {1:1.0, 2:3.0, 3:2.0}; 20 -> {1:2.0, 2:0.0, 3:4.0}.
    ``drop_team20_gw3`` removes team 20's gw3 fixture so team 10's gw3 opponent has no team row there
    (a coverage hole — an opponent playing a DGW is the real-world case)."""
    xgc = {10: {1: 1.0, 2: 3.0, 3: 2.0}, 20: {1: 2.0, 2: 0.0, 3: 4.0}}
    rows = []
    for team, opp in ((10, 20), (20, 10)):
        for gw in (1, 2, 3):
            if drop_team20_gw3 and team == 20 and gw == 3:
                continue
            for p in range(2):
                rows.append({"player_id": team * 100 + p, "team_id": team, "opponent_team_id": opp,
                             "gw": gw, "minutes": 90, "xgc": xgc[team][gw]})
    return pd.DataFrame(rows)


def test_add_opponent_xgc_forward_is_strictly_prior_and_opponent_keyed() -> None:
    """opp_xgc_forward on a player row == the OPPONENT's strictly-prior (window-2) conceded-xG roll."""
    out = add_opponent_xgc_forward(_opp_panel(), window=2).set_index(["team_id", "gw", "player_id"])
    # opponent rolls: team10 -> {g2:1.0, g3:2.0}; team20 -> {g2:2.0, g3:1.0}. A team-10 player faces 20.
    assert out.loc[(10, 2, 1000), "opp_xgc_forward"] == pytest.approx(2.0)   # opp 20 roll @ gw2
    assert out.loc[(10, 3, 1000), "opp_xgc_forward"] == pytest.approx(1.0)   # opp 20 roll @ gw3
    assert out.loc[(20, 2, 2000), "opp_xgc_forward"] == pytest.approx(1.0)   # opp 10 roll @ gw2
    assert out.loc[(20, 3, 2000), "opp_xgc_forward"] == pytest.approx(2.0)   # opp 10 roll @ gw3
    # gw1 faces an opponent with no prior fixture and there is no earlier gw to prior-fill -> NaN (pre-warmup).
    assert pd.isna(out.loc[(10, 1, 1000), "opp_xgc_forward"])


def test_add_opponent_xgc_forward_fills_coverage_hole_with_league_prior() -> None:
    """A missing opponent team-fixture (e.g. a DGW opponent) is filled with the strictly-prior league mean,
    NOT left NaN — so no attacking row is silently dropped vs the fdr-only design (same n)."""
    out = add_opponent_xgc_forward(_opp_panel(drop_team20_gw3=True), window=2)
    hole = out[(out["team_id"] == 10) & (out["gw"] == 3)]
    # league prior @ gw3 = mean of all team_xgc with gw<3 = mean(1.0, 3.0, 2.0, 0.0) = 1.5
    assert hole["opp_xgc_forward"].notna().all()
    assert hole["opp_xgc_forward"].unique() == pytest.approx([1.5])


def test_add_opponent_xgc_forward_is_noop_without_opponent_identity() -> None:
    """No opponent_team_id on the frame (the raw, un-enriched mart) -> the opponent build is skipped."""
    panel = _opp_panel().drop(columns=["opponent_team_id"])
    out = add_opponent_xgc_forward(panel, window=2)
    assert "opp_xgc_forward" not in out.columns  # a no-op, not an error (like add_lagged_rolls)


def test_assert_lag_safe_team_passes_on_a_strictly_prior_roll() -> None:
    team = pd.DataFrame({
        "team_id": [10, 10, 10, 20, 20],
        "gw": [1, 2, 3, 1, 2],
        "roll": [np.nan, 1.0, 2.0, np.nan, 2.0],  # shift(1) -> each team's first fixture is NaN
    })
    assert_lag_safe_team(team, "roll")  # must not raise


def test_assert_lag_safe_team_catches_a_missing_shift_leak() -> None:
    """A forward-window / missing-shift roll is defined on a team's first fixture -> caught at team grain."""
    leaky = pd.DataFrame({
        "team_id": [10, 10, 20, 20],
        "gw": [1, 2, 1, 2],
        "roll": [1.0, 2.0, 2.0, 0.0],  # first fixture NOT NaN -> the current match leaked in
    })
    with pytest.raises(AssertionError, match="first fixture"):
        assert_lag_safe_team(leaky, "roll")


def test_assert_lag_safe_skips_team_grain_broadcast_feature() -> None:
    """The player-grain pool canary must NOT false-flag an opponent-broadcast (team-grain) feature: it is
    legitimately defined on a player's debut because the OPPONENT already has history (checked at team
    grain instead). A genuinely leaked player-grain feature in the same pool still raises."""
    mart = pd.DataFrame({
        "player_id": [1, 1, 2, 2],
        "gw": [1, 2, 1, 2],
        "opp_xgc_forward": [0.9, 1.1, 0.8, 1.2],   # team-grain: NOT NaN on the player's first appearance
        "xgi_roll3": [np.nan, 0.3, np.nan, 0.4],   # player-grain: correctly NaN on first appearance
    })
    team_feat = FeatureSpec(name="opp_xgc_forward", source="opponent_xgc", grain="team_gw", window=5)
    player_feat = FeatureSpec(name="xgi_roll3", source="xgi", grain="player_gw", window=3)
    ok_pool = FeaturePool(name="t", candidates=(team_feat, player_feat), minimal=("xgi_roll3",))
    assert_lag_safe(mart, ok_pool)  # team-grain feature is skipped; player-grain one is lag-safe -> no raise

    leaked = mart.copy()
    leaked.loc[leaked["gw"] == 1, "xgi_roll3"] = 0.5  # a real player-grain leak
    with pytest.raises(AssertionError, match="xgi_roll3"):
        assert_lag_safe(leaked, ok_pool)
