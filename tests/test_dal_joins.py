"""DAL integrity tests — join safety between layers. Contract: Section 4, Section 9."""

from pathlib import Path

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.state.player_gameweek_state import build_player_gameweek_state
from dal.validation import validate_grain_uniqueness
from dal.exceptions import DALContractViolation

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_spine_to_state_no_row_loss():
    """State layer has same row count as spine — derivation must not drop rows. Contract Section 4."""
    spine = build_player_gameweek_spine(DB_PATH)
    state = build_player_gameweek_state(spine)
    assert len(state) == len(spine), (
        f"Row count mismatch between spine and state: "
        f"spine={len(spine)}, state={len(state)}. "
        f"Derivation must not add or drop rows."
    )


def test_spine_to_state_no_fan_out():
    """State layer has unique (player_id, gw) grain — derivation must not produce duplicate rows. Contract Section 2, 4."""
    spine = build_player_gameweek_spine(DB_PATH)
    state = build_player_gameweek_state(spine)
    validate_grain_uniqueness(state, ["player_id", "gw"], "state")
