"""Tests for research.kernels.diagnostic.serial (within-player serial dependence)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.kernels.diagnostic.serial import (
    MIN_N_EVENTS,
    MIN_N_PAIRS,
    MIN_N_PLAYERS,
    post_event_outcome_rate,
    within_player_autocorr,
)

pytestmark = pytest.mark.unit


def _player_series(player: int, gws: list[int], values: list[float]) -> pd.DataFrame:
    """One player's gameweek rows for a single value column."""
    return pd.DataFrame({"player_id": player, "gw": gws, "v": values})


def _panel(n_players: int, n_gws: int, value_fn) -> pd.DataFrame:
    """Balanced panel: every player appears in gw 1..n_gws; ``value_fn(player, gw)`` sets v."""
    frames = [
        _player_series(p, list(range(1, n_gws + 1)), [value_fn(p, gw) for gw in range(1, n_gws + 1)])
        for p in range(n_players)
    ]
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- #
# within_player_autocorr
# --------------------------------------------------------------------------- #


def test_autocorr_missing_column_raises() -> None:
    df = pd.DataFrame({"player_id": [1, 1], "gw": [1, 2]})
    with pytest.raises(ValueError, match="missing required columns"):
        within_player_autocorr(df, "v")


def test_autocorr_non_positive_lag_raises() -> None:
    df = _panel(5, 6, lambda p, gw: gw)
    with pytest.raises(ValueError, match="positive gameweek offset"):
        within_player_autocorr(df, "v", lag=0)


def test_autocorr_monotone_value_is_perfectly_persistent() -> None:
    """v increases with gw for every player → each lag-1 pair is (t, t+something larger) → rho = 1."""
    df = _panel(n_players=10, n_gws=8, value_fn=lambda p, gw: gw)
    out = within_player_autocorr(df, "v", min_n_pairs=5, min_n_players=5)
    assert out["rho"] == 1.0
    assert out["support_flag"] == ""
    assert out["n_pairs"] == 10 * 7  # 7 adjacent pairs per player


def test_autocorr_oscillating_value_is_negative() -> None:
    """v alternates high/low each gw → each lag-1 pair reverses → rho = -1.

    (A *monotone* series, even a decreasing one, has autocorrelation +1: consecutive
    values move together. Negative serial dependence requires oscillation.)
    """
    df = _panel(n_players=10, n_gws=8, value_fn=lambda p, gw: 1.0 if gw % 2 == 0 else -1.0)
    out = within_player_autocorr(df, "v", min_n_pairs=5, min_n_players=5)
    assert out["rho"] == -1.0


def test_autocorr_gap_in_appearances_drops_spanning_pair() -> None:
    """A player missing gw 3 contributes (1,2) and (4,5) but never a pair spanning the gap."""
    df = _player_series(100, gws=[1, 2, 4, 5], values=[10.0, 11.0, 12.0, 13.0])  # id disjoint from the padding
    # Pad with other players (ids 0..9) so the slice clears the floor while we assert the count.
    others = _panel(n_players=10, n_gws=6, value_fn=lambda p, gw: gw)
    out = within_player_autocorr(pd.concat([df, others], ignore_index=True), "v", min_n_pairs=5, min_n_players=5)
    # The gapped player yields exactly 2 adjacent-gw pairs: (gw1,gw2) and (gw4,gw5).
    player1_pairs = within_player_autocorr(df, "v", min_n_pairs=1)
    assert player1_pairs["n_pairs"] == 2
    assert out["support_flag"] == ""


def test_autocorr_thin_slice_is_insufficient() -> None:
    df = _player_series(1, gws=[1, 2], values=[5.0, 6.0])
    out = within_player_autocorr(df, "v")  # default MIN_N_PAIRS = 30, only 1 pair
    assert np.isnan(out["rho"])
    assert out["support_flag"] == "insufficient_support"
    assert out["n_pairs"] == 1


def test_autocorr_constant_series_is_insufficient() -> None:
    df = _panel(n_players=20, n_gws=6, value_fn=lambda p, gw: 7.0)  # never varies
    out = within_player_autocorr(df, "v", min_n_pairs=5)
    assert np.isnan(out["rho"])
    assert out["support_flag"] == "insufficient_support"


def test_autocorr_raw_mode_invariant_to_monotone_rescale() -> None:
    """Without demeaning, Spearman is rank-based: exp() of the column must not change rho.

    (With demean=True this invariance does not hold — demeaning is an affine op applied
    before ranking — so this property is asserted on the raw mode only.)
    """
    rng = np.random.default_rng(0)
    df = _panel(n_players=30, n_gws=10, value_fn=lambda p, gw: rng.normal())
    out_raw = within_player_autocorr(df, "v", demean=False, min_n_pairs=5)
    df_t = df.assign(v=np.exp(df["v"]))
    out_t = within_player_autocorr(df_t, "v", demean=False, min_n_pairs=5)
    assert out_raw["rho"] == pytest.approx(out_t["rho"], abs=1e-9)


def test_autocorr_demean_removes_between_player_identity() -> None:
    """The motivating fix: two level groups with i.i.d. (non-persistent) within-player
    noise. The raw pooled rho is inflated purely by the between-player level gap; demeaning
    by each player's own mean collapses it toward zero (true within-player persistence)."""
    rng = np.random.default_rng(0)
    frames = []
    for p in range(40):
        level = 10.0 if p < 20 else 2.0
        vals = level + rng.normal(size=12)  # white noise around the level -> no serial dependence
        frames.append(_player_series(p, list(range(1, 13)), list(vals)))
    df = pd.concat(frames, ignore_index=True)
    raw = within_player_autocorr(df, "v", demean=False, min_n_pairs=5)
    dem = within_player_autocorr(df, "v", demean=True, min_n_pairs=5)
    assert raw["rho"] > 0.3  # between-player identity inflates the raw pooled rho
    assert abs(dem["rho"]) < 0.15  # within-player series is white noise -> ~0


def test_autocorr_default_is_demeaned() -> None:
    rng = np.random.default_rng(3)
    df = _panel(n_players=30, n_gws=10, value_fn=lambda p, gw: rng.normal())
    assert within_player_autocorr(df, "v", min_n_pairs=5) == within_player_autocorr(df, "v", demean=True, min_n_pairs=5)


def test_autocorr_kendall_method_is_supported() -> None:
    rng = np.random.default_rng(5)
    df = _panel(n_players=30, n_gws=10, value_fn=lambda p, gw: rng.normal())
    out = within_player_autocorr(df, "v", method="kendall", min_n_pairs=5)
    assert out["support_flag"] == ""
    assert -1.0 <= out["rho"] <= 1.0


def test_autocorr_invalid_method_raises() -> None:
    df = _panel(n_players=20, n_gws=8, value_fn=lambda p, gw: gw)
    with pytest.raises(ValueError, match="method must be one of"):
        within_player_autocorr(df, "v", method="pearson", min_n_pairs=5)


def test_autocorr_uses_module_default_floor() -> None:
    assert MIN_N_PAIRS == 30  # guards against silent default drift


def test_autocorr_uses_module_default_player_floor() -> None:
    assert MIN_N_PLAYERS == 20  # guards against silent default drift


def test_autocorr_duplicate_grain_raises() -> None:
    """A duplicate (player_id, gw) row would Cartesian-explode the self-join; reject it."""
    df = _player_series(1, gws=[1, 2, 2, 3], values=[10.0, 11.0, 99.0, 12.0])  # two gw2 rows
    with pytest.raises(ValueError, match="must be unique"):
        within_player_autocorr(df, "v", min_n_pairs=1, min_n_players=1)


def test_autocorr_too_few_players_is_insufficient() -> None:
    """Pairs floor clears but the player floor binds: a rho resting on 2 players is suppressed.

    Two players on near-perfect trends produce ~0.99 pooled rho off 38 pairs — exactly the
    leverage the player floor exists to catch.
    """
    rng = np.random.default_rng(0)
    frames = [
        _player_series(p, list(range(1, 21)), list(np.arange(20, dtype=float) + rng.normal(scale=0.01, size=20)))
        for p in range(2)
    ]
    df = pd.concat(frames, ignore_index=True)
    out = within_player_autocorr(df, "v")  # default min_n_players = 20
    assert out["n_pairs"] >= MIN_N_PAIRS  # the pair floor is NOT what suppressed it
    assert out["n_players"] == 2
    assert np.isnan(out["rho"])
    assert out["support_flag"] == "insufficient_support"


def test_autocorr_reports_distinct_player_count() -> None:
    df = _panel(n_players=30, n_gws=10, value_fn=lambda p, gw: gw)
    out = within_player_autocorr(df, "v", min_n_pairs=5, min_n_players=5)
    assert out["n_players"] == 30


def test_autocorr_lag_two_spans_two_gameweeks() -> None:
    """lag=2 pairs gw t with gw t+2; a monotone series is still perfectly persistent."""
    df = _panel(n_players=10, n_gws=8, value_fn=lambda p, gw: gw)
    out = within_player_autocorr(df, "v", lag=2, min_n_pairs=5, min_n_players=5)
    assert out["lag"] == 2
    assert out["rho"] == 1.0
    assert out["n_pairs"] == 10 * 6  # gw(1,3)..(6,8) = 6 spanning pairs per player


def test_autocorr_nan_values_drop_only_their_pairs() -> None:
    """A NaN at gw3 removes the two pairs touching it ((2,3) and (3,4)), not the whole player."""
    df = _player_series(1, gws=[1, 2, 3, 4, 5, 6], values=[1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    out = within_player_autocorr(df, "v", min_n_pairs=1, min_n_players=1)
    assert out["n_pairs"] == 3  # (1,2), (4,5), (5,6) survive
    assert out["support_flag"] == ""


# --------------------------------------------------------------------------- #
# post_event_outcome_rate
# --------------------------------------------------------------------------- #


def _event_panel(n_players: int, n_gws: int, event_fn, outcome_fn) -> pd.DataFrame:
    frames = []
    for p in range(n_players):
        gws = list(range(1, n_gws + 1))
        frames.append(
            pd.DataFrame(
                {
                    "player_id": p,
                    "gw": gws,
                    "event": [bool(event_fn(p, gw)) for gw in gws],
                    "outcome": [int(outcome_fn(p, gw)) for gw in gws],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_transition_missing_column_raises() -> None:
    df = pd.DataFrame({"player_id": [1], "gw": [1], "event": [True]})
    with pytest.raises(ValueError, match="missing required columns"):
        post_event_outcome_rate(df, "event", "outcome")


def test_transition_event_always_followed_by_outcome_lifts_above_base() -> None:
    # Outcome fires only on even gameweeks; event fires only on odd gameweeks.
    # Every odd-gw event is therefore followed by an even-gw outcome → conditional = 1.0.
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome", min_n_events=5)
    assert out["conditional_rate"] == 1.0
    assert out["base_rate"] < 1.0
    assert out["lift"] == pytest.approx(out["conditional_rate"] - out["base_rate"], abs=1e-9)
    assert out["support_flag"] == ""


def test_transition_no_relationship_has_zero_lift() -> None:
    # Outcome constant at 1 everywhere → conditional and base both 1.0 → lift 0.
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: 1,
    )
    out = post_event_outcome_rate(df, "event", "outcome", min_n_events=5)
    assert out["base_rate"] == 1.0
    assert out["conditional_rate"] == 1.0
    assert out["lift"] == 0.0


def test_transition_thin_events_are_insufficient() -> None:
    # Only one player has the event; far below the default floor.
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: p == 0 and gw == 1,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome")  # default MIN_N_EVENTS = 30
    assert np.isnan(out["conditional_rate"])
    assert out["support_flag"] == "insufficient_support"
    assert out["n_event"] == 1


def test_transition_last_gw_event_has_no_next_row() -> None:
    # Event only on the final gameweek → no +lag counterpart → zero usable events.
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw == 6,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome", min_n_events=1)
    assert out["n_event"] == 0
    assert out["support_flag"] == "insufficient_support"


def test_transition_is_deterministic() -> None:
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: gw % 3 == 0,
    )
    assert post_event_outcome_rate(df, "event", "outcome", min_n_events=5) == post_event_outcome_rate(
        df, "event", "outcome", min_n_events=5
    )


def test_transition_uses_module_default_floor() -> None:
    assert MIN_N_EVENTS == 30


def test_transition_duplicate_grain_raises() -> None:
    df = pd.DataFrame({"player_id": [1, 1, 1], "gw": [1, 2, 2], "event": [True, False, True], "outcome": [1, 0, 1]})
    with pytest.raises(ValueError, match="must be unique"):
        post_event_outcome_rate(df, "event", "outcome", min_n_events=1, min_n_players=1)


def test_transition_non_binary_event_raises() -> None:
    df = pd.DataFrame({"player_id": [1, 1], "gw": [1, 2], "event": [2.0, 0.0], "outcome": [1, 0]})
    with pytest.raises(ValueError, match="boolean or 0/1"):
        post_event_outcome_rate(df, "event", "outcome")


def test_transition_non_binary_outcome_raises() -> None:
    df = pd.DataFrame({"player_id": [1, 1], "gw": [1, 2], "event": [True, False], "outcome": [2, 0]})
    with pytest.raises(ValueError, match="boolean or 0/1"):
        post_event_outcome_rate(df, "event", "outcome")


def test_transition_too_few_players_is_insufficient() -> None:
    """Events clear the event floor but come from only 3 players → suppressed by player floor."""
    df = _event_panel(
        n_players=3,
        n_gws=10,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome", min_n_events=5)  # default min_n_players = 20
    assert out["n_event"] >= 5  # the event floor is NOT what suppressed it
    assert out["n_players"] == 3
    assert np.isnan(out["conditional_rate"])
    assert out["support_flag"] == "insufficient_support"


def test_transition_reports_distinct_player_count() -> None:
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome", min_n_events=5, min_n_players=5)
    assert out["n_players"] == 40


def test_transition_lag_two_is_supported() -> None:
    df = _event_panel(
        n_players=40,
        n_gws=6,
        event_fn=lambda p, gw: gw % 2 == 1,
        outcome_fn=lambda p, gw: gw % 2 == 0,
    )
    out = post_event_outcome_rate(df, "event", "outcome", lag=2, min_n_events=5, min_n_players=5)
    assert out["lag"] == 2
    assert out["support_flag"] == ""
    assert 0.0 <= out["conditional_rate"] <= 1.0
