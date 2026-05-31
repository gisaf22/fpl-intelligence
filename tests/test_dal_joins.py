"""DAL integrity tests — join safety between layers. Contract: Section 4, Section 9."""

from pathlib import Path

import pytest

from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import get_staged_player_histories, load_staged_entities
from dal.validation import validate_grain_uniqueness

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_staged():
    return load_staged_entities(DB_PATH)


def _load_spine():
    staged = _load_staged()
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


def test_staging_to_intermediate_no_row_loss():
    """Intermediate layer preserves all staging player history rows.

    get_player_fixture_base joins player_histories (left) against players, positions,
    and fixture context tables. A left join must never drop source rows — row count
    must equal the staging input. Fan-out would also be a violation and is caught by
    the grain uniqueness assertion inside get_player_fixture_base itself.
    Contract Section 4, Section 9 (join safety tests).
    """
    player_histories = get_staged_player_histories(DB_PATH)
    player_fixture_base = get_player_fixture_base(load_staged_entities(DB_PATH))
    assert len(player_fixture_base) == len(player_histories), (
        f"Row count mismatch: staging has {len(player_histories)} rows, "
        f"intermediate has {len(player_fixture_base)} rows. "
        f"All left joins from player_histories must preserve row count — "
        f"check for fan-out or row loss in player, position, or fixture joins."
    )


def test_intermediate_to_curated_no_player_loss():
    """Curated spine contains exactly the players present in the intermediate layer.

    build_player_gameweek_spine derives its player universe from get_player_fixture_base.
    No player in the intermediate layer should be absent from the curated spine, and
    no extra players should appear. Row count changes are expected (BGW rows added,
    DGW rows aggregated) — the invariant is player set equality, not row count equality.
    Contract Section 3 (aggregation boundary rule), Section 9 (join safety tests).
    """
    player_fixture_base = get_player_fixture_base(load_staged_entities(DB_PATH))
    spine = _load_spine()

    intermediate_players = set(player_fixture_base["player_id"].unique())
    spine_players = set(spine["player_id"].unique())

    dropped = intermediate_players - spine_players
    extra = spine_players - intermediate_players

    assert not dropped and not extra, (
        f"Player set mismatch between intermediate and curated layers. "
        f"Dropped from spine: {dropped}. "
        f"Extra in spine (not in intermediate): {extra}."
    )


def test_spine_to_state_no_row_loss():
    """State layer has same row count as spine — derivation must not drop rows. Contract Section 4."""
    spine = _load_spine()
    state = build_player_gameweek_state(spine)
    assert len(state) == len(spine), (
        f"Row count mismatch between spine and state: "
        f"spine={len(spine)}, state={len(state)}. "
        f"Derivation must not add or drop rows."
    )


def test_spine_to_state_no_fan_out():
    """State layer has unique (player_id, gw) grain — derivation must not produce duplicate rows.

    Contract Section 2, 4."""
    spine = _load_spine()
    state = build_player_gameweek_state(spine)
    validate_grain_uniqueness(state, ["player_id", "gw"], "state")
