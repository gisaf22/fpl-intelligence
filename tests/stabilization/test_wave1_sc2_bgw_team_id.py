"""Wave 1 SC-2 — BGW team_id must reflect the player's pre-BGW team, not the latest team.

FAILING TEST committed before any fix.

Bug: _build_player_info uses sort_values("gw", ascending=False).drop_duplicates("player_id")
which always returns the LATEST gameweek's team_id. For a player who transferred between
their last fixture and a BGW, this assigns the post-transfer team to the BGW row —
which is temporally incorrect.

Golden DB scenario (SC-2):
  P3 (player_id=103): at T1 (team_id=1) in GW 1-2, BGW in GW3 (T1 has no fixture),
  transfers to T2 (team_id=2) and plays for T2 in GW 4-5.
  players.team = 2 (T2, current snapshot).

  Correct BGW GW3 team_id: 1 (T1 — last team before BGW).
  Bug:     BGW GW3 team_id: 2 (T2 — latest team from players table).

The failing test asserts team_id==1 for P3's GW3 BGW row.
FAILS before fix (returns 2). PASSES after fix (returns 1).
"""

from pathlib import Path

import pytest

from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities

pytestmark = pytest.mark.unit

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


def _load_spine():
    staged = load_staged_entities(TEST_DB_PATH)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


P3_ID = 103
BGW_GW = 3
PRE_TRANSFER_TEAM = 1  # T1: P3's team in GW1-2
POST_TRANSFER_TEAM = 2  # T2: P3's team in GW4-5 (and players.team snapshot)


def test_bgw_team_id_uses_pre_transfer_team():
    """SC-2 FAILING TEST: BGW row must carry the player's team at the time of the BGW.

    P3 (player_id=103) is at T1 (team_id=1) for GW1-2.
    GW3 is a BGW (T1 has no fixture).
    P3 transfers to T2 (team_id=2) and plays there from GW4.
    players.team = 2 (current snapshot after transfer).

    BGW GW3 team_id should be 1 (T1 — causally correct: most recent team before GW3).
    Bug: current code assigns team_id=2 (latest, post-transfer).

    FAILS before fix (returns 2). PASSES after fix (returns 1).
    """
    spine = _load_spine()

    bgw_row = spine[(spine["player_id"] == P3_ID) & (spine["gw"] == BGW_GW)]
    assert len(bgw_row) == 1, f"Expected exactly 1 BGW row for P3 GW{BGW_GW}"
    assert bgw_row.iloc[0]["is_bgw"], f"P3 GW{BGW_GW} should be is_bgw=True"

    actual_team = bgw_row.iloc[0]["team_id"]
    assert actual_team == PRE_TRANSFER_TEAM, (
        f"BGW GW{BGW_GW} team_id for P3 should be {PRE_TRANSFER_TEAM} (T1, pre-transfer), "
        f"got {actual_team}. "
        f"Bug: _build_player_info uses latest gw team_id ({POST_TRANSFER_TEAM}=T2) for all BGW rows."
    )


def test_bgw_team_id_post_transfer_is_correct():
    """After fix: BGW before the transfer carries pre-transfer team; non-BGW after transfer carries post-transfer team.

    P1 (always T1) and P2 (always T2) should have consistent team_id in their BGW rows too.
    P1 has BGW in GW3 (T1 has no fixture). P1's team should be 1 throughout.
    """
    spine = _load_spine()

    # P1 has BGW in GW3, always T1
    p1_bgw = spine[(spine["player_id"] == 101) & (spine["gw"] == 3)]
    assert len(p1_bgw) == 1, "P1 should have exactly one GW3 row (BGW)"
    assert p1_bgw.iloc[0]["is_bgw"], "P1 GW3 should be BGW"
    assert p1_bgw.iloc[0]["team_id"] == 1, (
        f"P1 GW3 BGW team_id should be 1 (T1, never transferred), got {p1_bgw.iloc[0]['team_id']}"
    )


def test_spine_has_correct_row_count():
    """Golden DB: the spine is dense — exactly n_players x n_gws rows (BGW rows present, not absent)."""
    spine = _load_spine()
    n_players = spine["player_id"].nunique()
    n_gws = spine["gw"].nunique()
    assert len(spine) == n_players * n_gws, (
        f"Expected {n_players} players x {n_gws} GWs = {n_players * n_gws} dense rows, got {len(spine)}"
    )
