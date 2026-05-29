"""Tests for player-opponent-context state DAL dataset."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from dal.intermediate.int_opponent_context import (
    build_player_opponent_defensive_context,
    validate_xgc_001,
)
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_staged():
    return load_staged_entities(DB_PATH)

_REQUIRED_COLS = [
    "player_id",
    "gw",
    "opponent_goals_conceded_roll3",
    "opponent_goals_conceded_roll5",
    "opponent_xgc_roll3",
    "opponent_xgc_roll5",
    "fixture_difficulty_avg",
]


def _make_analytics(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal analytics DataFrame for injection tests."""
    defaults = {
        "player_id": 1,
        "gw": 1,
        "fixture_id": 1,
        "team_id": 1,
        "opponent_team_id": 2,
        "was_home": 1,
        "fixture_difficulty": 3,
        "minutes": 90,
        "goals_conceded": 1,
        "xgc": 0.5,
        "total_points": 5,
        "player_name": "Test",
        "position_code": 3,
        "position_label": "MID",
        "purchase_price": 5.0,
        "ownership_count": 100,
        "transfers_balance": 0,
        "xg": 0.1,
        "xa": 0.1,
        "xgi": 0.2,
        "goals_scored": 0,
        "assists": 0,
        "clean_sheets": 0,
    }
    result = []
    for r in rows:
        row = {**defaults, **r}
        result.append(row)
    return pd.DataFrame(result)


def test_build_player_opponent_defensive_context_column_presence():
    df = build_player_opponent_defensive_context(get_player_fixture_base(_load_staged()))
    for col in _REQUIRED_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_build_player_opponent_defensive_context_grain_unique():
    df = build_player_opponent_defensive_context(get_player_fixture_base(_load_staged()))
    assert not df.duplicated(subset=["player_id", "gw"]).any()


def test_contract_xgc_001_raises_on_variance():
    """CONTRACT-XGC-001: validate_xgc_001 raises GrainViolationError when xgc differs within a (team_id, gw) group."""
    good = _make_analytics([
        {"player_id": 1, "gw": 1, "team_id": 1, "minutes": 90, "xgc": 0.50},
        {"player_id": 2, "gw": 1, "team_id": 1, "minutes": 90, "xgc": 0.50},
    ])
    validate_xgc_001(good[good["minutes"] == 90])  # no raise

    bad = _make_analytics([
        {"player_id": 1, "gw": 1, "team_id": 1, "minutes": 90, "xgc": 0.50},
        {"player_id": 2, "gw": 1, "team_id": 1, "minutes": 90, "xgc": 1.50},
    ])
    with pytest.raises(DALContractViolation, match="CONTRACT-XGC-001"):
        validate_xgc_001(bad[bad["minutes"] == 90])


def test_contract_xgc_002_no_90min_players_yields_null():
    """CONTRACT-XGC-002: team-gw with no 90-min players yields null opponent_xgc rolls."""
    analytics = _make_analytics([
        # team 1 at GW 1: only partial-minute player → no 90-min coverage
        {"player_id": 1, "gw": 1, "fixture_id": 1, "team_id": 1, "opponent_team_id": 2,
         "minutes": 45, "xgc": 0.50, "goals_conceded": 1},
        # team 2 at GW 1: one 90-min player facing team 1
        {"player_id": 2, "gw": 1, "fixture_id": 1, "team_id": 2, "opponent_team_id": 1,
         "minutes": 90, "xgc": 0.30, "goals_conceded": 0},
        # team 1 at GW 2: player facing team 2 — opponent_xgc should be null (team 2 at GW 2 has no prior)
        # team 2 at GW 2: player facing team 1 — opponent_xgc_roll3 would use team 1 GW 1 (null xgc)
        {"player_id": 1, "gw": 2, "fixture_id": 2, "team_id": 1, "opponent_team_id": 2,
         "minutes": 90, "xgc": 0.40, "goals_conceded": 0},
        {"player_id": 2, "gw": 2, "fixture_id": 2, "team_id": 2, "opponent_team_id": 1,
         "minutes": 90, "xgc": 0.20, "goals_conceded": 1},
    ])
    result = build_player_opponent_defensive_context(analytics)
    # player 2 at GW 2 faces team 1; team 1 at GW 1 had no 90-min players → xgc null
    # rolling at GW 2 uses shift(1) of GW 1 xgc which is null → null roll
    row = result[(result["player_id"] == 2) & (result["gw"] == 2)]
    assert not row.empty
    assert pd.isna(row["opponent_xgc_roll3"].iloc[0])
    assert pd.isna(row["opponent_xgc_roll5"].iloc[0])


def test_xgc_correctness_uses_only_90min_players():
    """xGC rolling reflects only 90-min player values, not a blend with partial-minute values."""
    # team 1 at GW 1: one 90-min player (xgc=1.52) + one partial player (xgc=0.30)
    # team 2 at GW 1: 90-min player, and at GW 2 faces team 1
    analytics = _make_analytics([
        {"player_id": 1, "gw": 1, "fixture_id": 1, "team_id": 1, "opponent_team_id": 2,
         "minutes": 90, "xgc": 1.52, "goals_conceded": 2},
        {"player_id": 2, "gw": 1, "fixture_id": 1, "team_id": 1, "opponent_team_id": 2,
         "minutes": 30, "xgc": 0.30, "goals_conceded": 2},
        # team 2 players at GW 1 (facing team 1)
        {"player_id": 3, "gw": 1, "fixture_id": 1, "team_id": 2, "opponent_team_id": 1,
         "minutes": 90, "xgc": 0.80, "goals_conceded": 0},
        # GW 2: player 3 (team 2) faces team 1 again; roll3 at GW 2 = GW 1 value only
        {"player_id": 3, "gw": 2, "fixture_id": 2, "team_id": 2, "opponent_team_id": 1,
         "minutes": 90, "xgc": 0.60, "goals_conceded": 1},
        # player 1 also plays GW 2
        {"player_id": 1, "gw": 2, "fixture_id": 2, "team_id": 1, "opponent_team_id": 2,
         "minutes": 90, "xgc": 0.90, "goals_conceded": 1},
        {"player_id": 2, "gw": 2, "fixture_id": 2, "team_id": 1, "opponent_team_id": 2,
         "minutes": 45, "xgc": 0.20, "goals_conceded": 1},
    ])
    result = build_player_opponent_defensive_context(analytics)

    # player 3 at GW 2 faces team 1; team 1's xgc at GW 1 = 1.52 (90-min only)
    # roll3 at GW 2 = shift(1) of GW 1 = 1.52
    row = result[(result["player_id"] == 3) & (result["gw"] == 2)]
    assert not row.empty
    actual = row["opponent_xgc_roll3"].iloc[0]
    assert abs(actual - 1.52) < 1e-6, (
        f"Expected opponent_xgc_roll3=1.52 (90-min only), got {actual}"
    )


def test_build_player_opponent_defensive_context_no_look_ahead():
    """Roll3 stat at GW 4 for any team must not include GW 4 data (reflects GWs 1-3 only)."""
    analytics = get_player_fixture_base(_load_staged())

    team_def = (
        analytics.groupby(["team_id", "gw"], as_index=False)
        .agg(goals_conceded=("goals_conceded", "sum"))
        .sort_values(["team_id", "gw"])
        .reset_index(drop=True)
    )

    result = build_player_opponent_defensive_context(analytics)

    for team_id in team_def["team_id"].unique():
        team_rows = team_def[team_def["team_id"] == team_id].sort_values("gw")
        gws_with_data = team_rows["gw"].tolist()
        if 1 in gws_with_data and 2 in gws_with_data and 3 in gws_with_data and 4 in gws_with_data:
            expected = team_rows[team_rows["gw"].isin([1, 2, 3])]["goals_conceded"].mean()

            players_facing = analytics[
                (analytics["opponent_team_id"] == team_id) & (analytics["gw"] == 4)
            ]["player_id"].unique()
            if len(players_facing) == 0:
                continue

            player_row = result[
                (result["player_id"] == players_facing[0]) & (result["gw"] == 4)
            ]
            if player_row.empty:
                continue

            actual = player_row["opponent_goals_conceded_roll3"].iloc[0]
            assert abs(actual - expected) < 1e-6, (
                f"Look-ahead detected for team {team_id} at GW 4: "
                f"expected {expected:.4f} (GWs 1-3), got {actual:.4f}"
            )
            return

    pytest.skip("No team with data at GWs 1-4 found — cannot verify no look-ahead")


def test_build_player_opponent_defensive_context_dgw_max_aggregation():
    """For a DGW player, opponent_goals_conceded_roll3 equals max across fixtures, not mean."""
    analytics = get_player_fixture_base(_load_staged())
    result = build_player_opponent_defensive_context(analytics)

    fixture_counts = analytics.groupby(["player_id", "gw"])["fixture_id"].count()
    dgw = fixture_counts[fixture_counts >= 2]
    if dgw.empty:
        pytest.skip("No DGW players found in DB")

    player_id, gw = dgw.index[0]

    fixtures = analytics[(analytics["player_id"] == player_id) & (analytics["gw"] == gw)]
    opponent_ids = fixtures["opponent_team_id"].tolist()

    team_def = (
        analytics.groupby(["team_id", "gw"], as_index=False)
        .agg(goals_conceded=("goals_conceded", "sum"))
        .sort_values(["team_id", "gw"])
        .reset_index(drop=True)
    )

    def rolling_shifted_val(tid, gw_val, window):
        rows = team_def[team_def["team_id"] == tid].sort_values("gw")
        shifted = rows["goals_conceded"].shift(1).rolling(window, min_periods=1).mean()
        rows = rows.copy()
        rows["rolled"] = shifted.values
        val = rows[rows["gw"] == gw_val]["rolled"]
        return float(val.iloc[0]) if not val.empty else float("nan")

    vals = [rolling_shifted_val(opp, gw, 3) for opp in opponent_ids]
    expected_max = max(v for v in vals if not pd.isna(v))

    actual = result[(result["player_id"] == player_id) & (result["gw"] == gw)][
        "opponent_goals_conceded_roll3"
    ].iloc[0]

    assert abs(actual - expected_max) < 1e-6, (
        f"DGW max aggregation failed: expected {expected_max:.4f}, got {actual:.4f}"
    )


def test_team_id_resolution_igor_loan():
    """Igor played on loan at West Ham (19) in GWs 4-23; Brighton (6) before and after."""
    df = get_player_fixture_base(_load_staged())
    igor = df[df["player_name"] == "Igor"]
    assert not igor.empty, "Igor not found in analytics"

    gw4_row = igor[igor["gw"] == 4]
    assert not gw4_row.empty, "Igor has no GW4 row"
    assert gw4_row["team_id"].iloc[0] == 19, (
        f"Igor GW4: expected West Ham (19), got {gw4_row['team_id'].iloc[0]}"
    )

    gw24_row = igor[igor["gw"] == 24]
    assert not gw24_row.empty, "Igor has no GW24 row"
    assert gw24_row["team_id"].iloc[0] == 6, (
        f"Igor GW24: expected Brighton (6), got {gw24_row['team_id'].iloc[0]}"
    )


def test_team_id_resolution_guehi_january_transfer():
    """Guéhi was at Crystal Palace (8) through GW22; Man City (13) from GW23."""
    df = get_player_fixture_base(_load_staged())
    guehi = df[df["player_name"] == "Guéhi"]
    assert not guehi.empty, "Guéhi not found in analytics"

    gw15_row = guehi[guehi["gw"] == 15]
    assert not gw15_row.empty, "Guéhi has no GW15 row"
    assert gw15_row["team_id"].iloc[0] == 8, (
        f"Guéhi GW15: expected Crystal Palace (8), got {gw15_row['team_id'].iloc[0]}"
    )

    gw23_row = guehi[guehi["gw"] == 23]
    assert not gw23_row.empty, "Guéhi has no GW23 row"
    assert gw23_row["team_id"].iloc[0] == 13, (
        f"Guéhi GW23: expected Man City (13), got {gw23_row['team_id'].iloc[0]}"
    )


def test_team_id_resolution_brentford_gw26():
    """Brentford player at GW26 has team_id == 5 (fixture_id join, not dict snapshot)."""
    df = get_player_fixture_base(_load_staged())
    brentford_gw26 = df[(df["gw"] == 26) & (df["team_id"] == 5)]
    assert not brentford_gw26.empty, "No Brentford (team_id=5) players found at GW26"
    assert (brentford_gw26["team_id"] == 5).all(), (
        "Not all Brentford GW26 players have team_id == 5"
    )


def test_team_id_resolution_column_contract():
    """Output columns are identical to pre-enrichment contract; no intermediate columns leak."""
    df = get_player_fixture_base(_load_staged())
    for col in [
        "player_id", "player_name", "gw", "fixture_id", "position_code", "position_label",
        "team_id", "opponent_team_id", "was_home", "fixture_difficulty", "total_points",
        "minutes", "goals_scored", "assists", "clean_sheets", "goals_conceded",
        "xg", "xa", "xgi", "xgc", "purchase_price", "ownership_count", "transfers_balance",
    ]:
        assert col in df.columns, f"Required output column missing: {col}"
    for bad_col in ["home_team_id", "away_team_id", "true_team_id"]:
        assert bad_col not in df.columns, f"Intermediate column leaked to output: {bad_col}"


def test_team_id_resolution_stable_player_unaffected():
    """A player who never transferred keeps the same team_id across all GWs."""
    df = get_player_fixture_base(_load_staged())
    # Raya (player_id=1) has been at Arsenal (team_id=1) all season
    raya = df[df["player_id"] == 1]
    assert not raya.empty, "Raya (player_id=1) not found in analytics"
    assert (raya["team_id"] == 1).all(), (
        f"Raya team_id should always be 1 (Arsenal), got: {raya['team_id'].unique().tolist()}"
    )


def test_team_id_resolution_discrepancy_logging(caplog):
    """get_player_fixture_base emits at least one [team_id resolution] log on real data."""
    with caplog.at_level("INFO", logger="dal.intermediate.int_player_fixture"):
        get_player_fixture_base(_load_staged())

    assert any("[AUDIT]" in message and "team_id" in message for message in caplog.messages), (
        "Expected at least one [AUDIT] team_id correction log message"
    )


def test_contract_xgc_001_raises_in_build_player_opponent_defensive_context():
    """Test 7 — CONTRACT-XGC-001 now raises rather than warns inside build_player_opponent_defensive_context()."""
    analytics = _make_analytics([
        # Two 90-min GK rows (position_code=1) in the same (team_id=1, gw=1) with different xgc
        {"player_id": 1, "gw": 1, "fixture_id": 1, "team_id": 1, "opponent_team_id": 2,
         "minutes": 90, "xgc": 0.50, "goals_conceded": 1, "position_code": 1},
        {"player_id": 2, "gw": 1, "fixture_id": 1, "team_id": 1, "opponent_team_id": 2,
         "minutes": 90, "xgc": 1.50, "goals_conceded": 1, "position_code": 1},
    ])
    with pytest.raises(DALContractViolation, match="CONTRACT-XGC-001"):
        build_player_opponent_defensive_context(analytics)


def test_build_player_opponent_defensive_context_dgw_fixture_difficulty_avg():
    """For a DGW player, fixture_difficulty_avg equals mean of FDR values across fixtures."""
    analytics = get_player_fixture_base(_load_staged())
    result = build_player_opponent_defensive_context(analytics)

    fixture_counts = analytics.groupby(["player_id", "gw"])["fixture_id"].count()
    dgw = fixture_counts[fixture_counts >= 2]
    if dgw.empty:
        pytest.skip("No DGW players found in DB")

    player_id, gw = dgw.index[0]

    fixtures = analytics[(analytics["player_id"] == player_id) & (analytics["gw"] == gw)]
    expected_mean = fixtures["fixture_difficulty"].mean()

    actual = result[(result["player_id"] == player_id) & (result["gw"] == gw)][
        "fixture_difficulty_avg"
    ].iloc[0]

    assert abs(actual - expected_mean) < 1e-6, (
        f"DGW mean FDR failed: expected {expected_mean:.4f}, got {actual:.4f}"
    )
