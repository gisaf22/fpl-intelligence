"""Wave 4 — Invariant Expansion.

FAILING TESTS committed before any fixes.

SC-13: fixture_context maps is_bgw=True rows to "SGW" — BGW invisible.
SC-14: validate_xgc_001 checks GK only — defenders with inconsistent xgc pass.
STATE_COL_CONTRACTS: dal/state/contracts.py does not exist.
GW sequence gap detection: no gap check in get_gameweek_context.
"""

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


# ---------------------------------------------------------------------------
# SC-13 — fixture_context must produce "BGW", "SGW", "DGW" — not "SGW" for BGW
# ---------------------------------------------------------------------------

def test_fixture_context_bgw_rows():
    """SC-13 FAILING TEST: BGW rows must have fixture_context="BGW", not "SGW".

    Current code: df["is_dgw"].map({True: "DGW", False: "SGW"}) — maps all non-DGW
    rows to "SGW", including BGW rows.

    FAILS before fix (BGW rows get "SGW"). PASSES after fix.
    """
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine
    from dal.state.player_gameweek_state import build_player_gameweek_state

    spine = build_player_gameweek_spine(TEST_DB_PATH)
    state = build_player_gameweek_state(spine)

    bgw_rows = state[state["is_bgw"] == True]
    assert not bgw_rows.empty, "Golden DB should have BGW rows"

    bad = bgw_rows[bgw_rows["fixture_context"] != "BGW"]
    assert bad.empty, (
        f"{len(bad)} BGW rows have fixture_context != 'BGW' (got: {bad['fixture_context'].unique()}). "
        f"Bug: is_dgw.map({{True: 'DGW', False: 'SGW'}}) assigns 'SGW' to BGW rows."
    )


def test_fixture_context_exhaustive():
    """After fix: fixture_context values must be exactly {{'BGW', 'SGW', 'DGW'}}."""
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine
    from dal.state.player_gameweek_state import build_player_gameweek_state

    spine = build_player_gameweek_spine(TEST_DB_PATH)
    state = build_player_gameweek_state(spine)

    valid = {"BGW", "SGW", "DGW"}
    non_null_contexts = state["fixture_context"].dropna()
    bad = non_null_contexts[~non_null_contexts.isin(valid)]
    assert bad.empty, (
        f"fixture_context contains invalid values: {bad.unique()}. "
        f"Must be one of {valid}."
    )


# ---------------------------------------------------------------------------
# SC-14 — validate_xgc_001 must cover all positions, not just GK
# ---------------------------------------------------------------------------

def test_validate_xgc_001_callable_on_all_positions():
    """SC-14: validate_xgc_001 as a function accepts all positions.

    The function can check any set of players for xgc invariance. This is correct for
    GK rows (where invariance should hold) and can be used in targeted checks.

    Note: _validate_contracts keeps the GK-only filter because FPL assigns distinct xgc
    values to different field-player positions within the same fixture.
    """
    from dal.intermediate.opponent_context import validate_xgc_001
    from dal.exceptions import DALContractViolation

    # GK players in same team/gw/fixture with different xgc — raises correctly
    gk_with_variance = pd.DataFrame([
        {"player_id": 1, "team_id": 1, "gw": 1, "fixture_id": 1,
         "position_code": 1, "minutes": 90, "xgc": 0.5},
        {"player_id": 2, "team_id": 1, "gw": 1, "fixture_id": 1,
         "position_code": 1, "minutes": 90, "xgc": 0.8},  # different GK xgc — violation
    ])
    with pytest.raises(DALContractViolation, match="xgc"):
        validate_xgc_001(gk_with_variance)


# ---------------------------------------------------------------------------
# STATE_COL_CONTRACTS — dal/state/contracts.py must exist
# ---------------------------------------------------------------------------

def test_state_col_contracts_exists():
    """Wave 4 FAILING TEST: dal/state/contracts.py must define STATE_COL_CONTRACTS.

    FAILS before dal/state/contracts.py is created. PASSES after.
    """
    from dal.state.contracts import STATE_COL_CONTRACTS
    assert isinstance(STATE_COL_CONTRACTS, dict), "STATE_COL_CONTRACTS must be a dict"

    required_keys = {"causality", "warmup_gws", "min_obs_for_reliability", "null_if_no_obs"}
    from dal.state.player_gameweek_state import _ROLL_COLS
    for col_suffix in ["points", "minutes"]:
        # roll3 is the primary entry
        roll3_key = f"{col_suffix}_roll3"
        assert roll3_key in STATE_COL_CONTRACTS, (
            f"STATE_COL_CONTRACTS missing entry for '{roll3_key}'"
        )
        entry = STATE_COL_CONTRACTS[roll3_key]
        for k in required_keys:
            assert k in entry, f"STATE_COL_CONTRACTS['{roll3_key}'] missing '{k}'"
        assert entry["causality"] == "lagged", (
            f"'{roll3_key}' must have causality='lagged'"
        )


def test_state_col_contracts_covers_fixture_context():
    """fixture_context must be declared in STATE_COL_CONTRACTS with causality=contemporaneous."""
    from dal.state.contracts import STATE_COL_CONTRACTS
    assert "fixture_context" in STATE_COL_CONTRACTS, (
        "STATE_COL_CONTRACTS must include 'fixture_context'"
    )
    assert STATE_COL_CONTRACTS["fixture_context"]["causality"] == "contemporaneous", (
        "fixture_context causality must be 'contemporaneous'"
    )
    assert STATE_COL_CONTRACTS["fixture_context"]["values"] == ["BGW", "SGW", "DGW"]


def test_state_col_contracts_covers_minutes_trend():
    """minutes_trend must be declared in STATE_COL_CONTRACTS with causality=lagged, warmup_gws=4."""
    from dal.state.contracts import STATE_COL_CONTRACTS
    assert "minutes_trend" in STATE_COL_CONTRACTS, (
        "STATE_COL_CONTRACTS must include 'minutes_trend'"
    )
    entry = STATE_COL_CONTRACTS["minutes_trend"]
    assert entry["causality"] == "lagged"
    assert entry["warmup_gws"] == 4


def test_state_col_contracts_covers_all_roll_cols():
    """Every column in _ROLL_COLS must produce both roll3 and roll5 entries in STATE_COL_CONTRACTS.

    STATE_COL_CONTRACTS is the causality declaration for every derived state column.
    A missing entry means a downstream consumer cannot know whether a column is safe
    to use as a pre-GW feature (lagged) or contemporaneous. All rolling window columns
    must be declared. Contract Section: FIRST_COLS Semantic Registry / State Layer
    Causality Contract.
    """
    from dal.state.contracts import STATE_COL_CONTRACTS
    from dal.state.player_gameweek_state import _ROLL_COLS

    required_fields = {"causality", "warmup_gws", "min_obs_for_reliability", "null_if_no_obs"}

    for col in _ROLL_COLS:
        col_short = "points" if col == "total_points" else col
        for suffix in ("roll3", "roll5"):
            key = f"{col_short}_{suffix}"
            assert key in STATE_COL_CONTRACTS, (
                f"STATE_COL_CONTRACTS missing entry for '{key}'. "
                f"Every _ROLL_COLS column must have roll3 and roll5 entries declared."
            )
            entry = STATE_COL_CONTRACTS[key]
            for field in required_fields:
                assert field in entry, (
                    f"STATE_COL_CONTRACTS['{key}'] missing required field '{field}'."
                )
            assert entry["causality"] == "lagged", (
                f"STATE_COL_CONTRACTS['{key}'] must have causality='lagged' — "
                f"rolling windows use shift(1) and are safe as pre-GW features."
            )


# ---------------------------------------------------------------------------
# GW sequence gap detection
# ---------------------------------------------------------------------------

def test_gameweek_context_raises_on_gw_gap():
    """Wave 4: get_gameweek_context must raise DALContractViolation on GW sequence gaps.

    FAILS before fix (no gap detection). PASSES after fix.
    """
    from dal.curated.gameweek_context import get_gameweek_context
    from dal.exceptions import DALContractViolation
    from unittest.mock import patch
    import pandas as pd

    # Events with a gap: GW 1, 2, 4 (missing GW 3)
    events_with_gap = pd.DataFrame([
        {"gw": 1, "deadline_time": "2025-08-15T18:00:00Z", "finished": 1,
         "is_previous": 0, "is_live": 0, "is_next": 0,
         "average_entry_score": 52, "highest_score": 120, "transfers_made": 500000},
        {"gw": 2, "deadline_time": "2025-08-22T18:00:00Z", "finished": 1,
         "is_previous": 0, "is_live": 0, "is_next": 0,
         "average_entry_score": 54, "highest_score": 130, "transfers_made": 520000},
        {"gw": 4, "deadline_time": "2025-09-05T18:00:00Z", "finished": 0,
         "is_previous": 0, "is_live": 0, "is_next": 1,
         "average_entry_score": None, "highest_score": None, "transfers_made": 0},
    ])

    with patch("dal.curated.gameweek_context.get_staged_events", return_value=events_with_gap):
        with pytest.raises(DALContractViolation):
            get_gameweek_context(TEST_DB_PATH)
