"""DAL integrity tests — grain uniqueness. Contract: Section 2, Section 9."""

from pathlib import Path

import pytest
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.state.player_gameweek_state import build_player_gameweek_state
from dal.validation import validate_grain_uniqueness
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def test_spine_grain_unique():
    """Curated spine has no duplicate (player_id, gw) pairs — Contract Section 2."""
    spine = build_player_gameweek_spine(DB_PATH)
    validate_grain_uniqueness(spine, ["player_id", "gw"], "curated")


def test_state_grain_unique():
    """State layer preserves (player_id, gw) uniqueness — no fan-out from derivation. Contract Section 2."""
    spine = build_player_gameweek_spine(DB_PATH)
    state = build_player_gameweek_state(spine)
    validate_grain_uniqueness(state, ["player_id", "gw"], "state")
