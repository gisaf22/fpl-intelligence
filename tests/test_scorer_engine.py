"""Tests for scorer.engine — scoring logic correctness."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dal.access import get_curated_spine, get_state_features
from intelligence.scoring.contracts import ConfirmedSignal, SignalManifest
from intelligence.scoring.engine import NoDataForGameweek, score

TEST_DB = Path(__file__).parent / "fixtures" / "test.db"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def state():
    spine = get_curated_spine(TEST_DB)
    return get_state_features(spine)


@pytest.fixture(scope="module")
def minimal_manifest():
    """A two-signal manifest covering GK (one positive, one negative rho)."""
    return SignalManifest(
        confirmed=[
            ConfirmedSignal(
                signal="goals_scored",
                position="GK",
                rho_pooled=0.32,
                direction=1,
                promotion_class="core_signal",
            ),
            ConfirmedSignal(
                signal="goals_conceded",
                position="GK",
                rho_pooled=-0.79,
                direction=-1,
                promotion_class="review_signal",
            ),
        ],
        caveated=[],
        positions_covered={"GK": ["goals_scored", "goals_conceded"]},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_data_for_gameweek_raises(state):
    """Engine raises NoDataForGameweek when the GW has no rows."""
    manifest = SignalManifest(confirmed=[], caveated=[], positions_covered={})
    with pytest.raises(NoDataForGameweek, match="99"):
        score(state, manifest, gw=99)


def test_composite_score_between_zero_and_one(state, minimal_manifest):
    """Composite scores are in [0, 1] before rendering."""
    output = score(state, minimal_manifest, gw=1)
    for p in output.players:
        assert 0.0 <= p.composite_score <= 1.0, (
            f"player {p.player_id} composite_score={p.composite_score} out of range"
        )


def test_negative_rho_inverts_rank(state):
    """A signal with negative rho should rank the player with the lowest raw value first."""
    # goals_conceded direction=-1: lower raw goals_conceded → better → rank 1
    manifest = SignalManifest(
        confirmed=[
            ConfirmedSignal(
                signal="goals_conceded",
                position="GK",
                rho_pooled=-0.79,
                direction=-1,
                promotion_class="review_signal",
            ),
        ],
        caveated=[],
        positions_covered={"GK": ["goals_conceded"]},
    )
    gw_data = state[state["gw"] == 1].copy()
    from dal.prepared import POSITION_CODE_MAP
    gw_data["_position"] = gw_data["position_code"].map(POSITION_CODE_MAP)
    gk_data = gw_data[gw_data["_position"] == "GK"]

    if len(gk_data) < 2:
        pytest.skip("Need at least two GK players to verify rank inversion")

    output = score(state, manifest, gw=1)
    gk_scores = [p for p in output.players if p.position == "GK"]

    # Player with lowest goals_conceded should have the best (lowest) rank number
    rank1 = next(p for p in gk_scores if p.rank == 1)
    rank_last = max(gk_scores, key=lambda p: p.rank)
    assert rank1.signal_normalised["goals_conceded"] >= rank_last.signal_normalised["goals_conceded"]


def test_players_ranked_within_position(state):
    """Ranks are assigned per position, not globally across all positions."""
    manifest = SignalManifest(
        confirmed=[
            ConfirmedSignal("goals_scored", "GK", 0.32, 1, "core_signal"),
            ConfirmedSignal("goals_scored", "MID", 0.58, 1, "review_signal"),
        ],
        caveated=[],
        positions_covered={"GK": ["goals_scored"], "MID": ["goals_scored"]},
    )
    output = score(state, manifest, gw=1)
    for position in ("GK", "MID"):
        pos_players = [p for p in output.players if p.position == position]
        if not pos_players:
            continue
        ranks = sorted(p.rank for p in pos_players)
        # ranks must start at 1 and stay within [1, n_players] — ties are allowed
        assert ranks[0] == 1, f"{position}: lowest rank is {ranks[0]}, expected 1"
        n = len(pos_players)
        assert all(1 <= r <= n for r in ranks), (
            f"{position}: rank out of bounds in {ranks} for {n} players"
        )


def test_excluded_signals_absent_from_composite(state):
    """bonus and bps must not appear in signal_normalised of any player score."""
    from signals.lifecycle.loader import load_registry
    from intelligence.scoring.signals import load_manifest

    registry = load_registry(Path("studies/eda/findings/eda_03_joint_registry.csv"))
    manifest = load_manifest(registry)

    output = score(state, manifest, gw=1)
    for p in output.players:
        assert "bonus" not in p.signal_normalised, (
            f"player {p.player_id}: 'bonus' found in signal_normalised "
            "(leakage signal should be excluded)"
        )
        assert "bps" not in p.signal_normalised, (
            f"player {p.player_id}: 'bps' found in signal_normalised "
            "(outcome-component signal should be excluded)"
        )
