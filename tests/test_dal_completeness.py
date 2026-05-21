"""DAL integrity tests — spine completeness. Contract: Section 2, Section 7, Section 9."""

from pathlib import Path

import pytest
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.validation import validate_row_count_invariant, validate_time_continuity
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_spine_row_count_invariant():
    """Spine has exactly n_players × n_gws rows — BGW rows must be present. Contract Section 2."""
    spine = build_player_gameweek_spine(DB_PATH)
    n_players = spine["player_id"].nunique()
    n_gws = spine["gw"].nunique()
    validate_row_count_invariant(spine, n_players, n_gws)


def test_spine_time_continuity():
    """Every player has a contiguous GW sequence with no gaps — BGW rows fill blanks. Contract Section 7."""
    spine = build_player_gameweek_spine(DB_PATH)
    validate_time_continuity(spine)


def test_spine_bgw_rows_present():
    """GWs with fewer than 20 active teams have explicit BGW rows (fixture_count=0) for all players. Contract Section 2, 9."""
    spine = build_player_gameweek_spine(DB_PATH)

    # Identify BGW candidate GWs: GWs where fewer than 20 teams have at least one fixture
    teams_per_gw = spine[spine["fixture_count"] > 0].groupby("gw")["team_id"].nunique()
    bgw_candidate_gws = teams_per_gw[teams_per_gw < 20].index.tolist()

    assert bgw_candidate_gws, (
        "No BGW candidate GWs found in data — cannot verify BGW row presence. "
        "Expected at least one GW where fewer than 20 teams have fixtures."
    )

    all_player_ids = set(spine["player_id"].unique())

    for gw in bgw_candidate_gws:
        gw_rows = spine[spine["gw"] == gw]
        players_in_gw = set(gw_rows["player_id"].unique())
        missing_players = all_player_ids - players_in_gw
        assert not missing_players, (
            f"BGW completeness violation at GW {gw}: "
            f"{len(missing_players)} players missing — "
            f"expected explicit BGW rows with fixture_count=0 for all players, "
            f"but {len(missing_players)} players have no row at all. "
            f"Sample missing player_ids: {sorted(missing_players)[:10]}"
        )
        bgw_rows = gw_rows[gw_rows["fixture_count"] == 0]
        assert not bgw_rows.empty, (
            f"BGW rows absent at GW {gw}: all players present but none have fixture_count=0. "
            f"BGW rows must be explicit, not inferred from absence."
        )
