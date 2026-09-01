"""Tests for the incremental feasibility primitive -- `DESIGN.md` §3.

Falsification probes mirroring `decisions/starting_xi/test_formations.py`'s legality tests:
adversarial pools built so `can_complete` must land on a specific, known verdict (budget too
tight, a position exhausted, a club cap already hit) rather than sampled and hoped to disagree.
"""

from __future__ import annotations

import numpy as np
import pytest

from decisions.free_hit.feasibility import _Pool, can_complete
from domain.fpl_squad import MAX_PER_CLUB, POSITIONS

pytestmark = pytest.mark.unit


def _pool(player_ids: list[int], prices: list[int], teams: list[int]) -> _Pool:
    return _Pool(
        player_id=np.array(player_ids, dtype=np.int64),
        price_tenths=np.array(prices, dtype=np.int64),
        team_id=np.array(teams, dtype=np.int64),
    )


def _full_pool() -> dict[str, _Pool]:
    """10 cheap players per position, spread one-per-club over 10 clubs -- generously feasible."""
    return {
        position: _pool(
            player_ids=[base + i for i in range(10)],
            prices=[40] * 10,
            teams=list(range(1, 11)),
        )
        for base, position in zip((0, 100, 200, 300), POSITIONS, strict=True)
    }


def _empty_picks() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64)


# ---------------------------------------------------------------------------
# True cases
# ---------------------------------------------------------------------------


def test_a_fully_stocked_pool_within_budget_can_complete() -> None:
    ids, prices, teams = _empty_picks()
    quota = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    assert can_complete(ids, prices, teams, 1000, quota, _full_pool())


def test_a_squad_with_nothing_left_to_fill_can_always_complete_at_non_negative_budget() -> None:
    ids, prices, teams = _empty_picks()
    assert can_complete(ids, prices, teams, 0, {}, _full_pool())
    assert can_complete(ids, prices, teams, 0, {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}, _full_pool())


# ---------------------------------------------------------------------------
# False: budget too tight for the cheapest completion
# ---------------------------------------------------------------------------


def test_budget_one_tenth_short_of_the_cheapest_completion_fails() -> None:
    ids, prices, teams = _empty_picks()
    quota = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    # Cheapest legal 15 here costs 15 * 40 = 600 tenths -- one short must fail, exact must pass.
    assert not can_complete(ids, prices, teams, 599, quota, _full_pool())
    assert can_complete(ids, prices, teams, 600, quota, _full_pool())


def test_a_negative_remaining_budget_always_fails_even_with_nothing_left_to_fill() -> None:
    ids, prices, teams = _empty_picks()
    assert not can_complete(ids, prices, teams, -1, {}, _full_pool())


# ---------------------------------------------------------------------------
# False: a position is exhausted
# ---------------------------------------------------------------------------


def test_a_position_with_too_few_eligible_players_fails() -> None:
    ids, prices, teams = _empty_picks()
    pool = _full_pool()
    pool["GK"] = _pool([1], [40], [1])  # one GK left, quota needs two
    assert not can_complete(ids, prices, teams, 1000, {"GK": 2, "DEF": 0, "MID": 0, "FWD": 0}, pool)
    assert can_complete(ids, prices, teams, 1000, {"GK": 1, "DEF": 0, "MID": 0, "FWD": 0}, pool)


def test_a_position_absent_from_the_pool_fails_if_still_needed() -> None:
    ids, prices, teams = _empty_picks()
    pool = _full_pool()
    del pool["FWD"]
    assert not can_complete(ids, prices, teams, 1000, {"GK": 0, "DEF": 0, "MID": 0, "FWD": 1}, pool)


# ---------------------------------------------------------------------------
# False: a club cap already hit, or hit mid-completion
# ---------------------------------------------------------------------------


def test_a_players_own_club_already_at_the_cap_excludes_him_from_the_presence_count() -> None:
    ids = np.array([901, 902, 903], dtype=np.int64)
    prices = np.array([40, 40, 40], dtype=np.int64)
    teams = np.array([1, 1, 1], dtype=np.int64)  # club 1 already at MAX_PER_CLUB (3)
    pool = {
        "GK": _pool([1], [40], [1]),  # the only remaining GK is club 1 -- already capped
        "DEF": _pool([], [], []),
        "MID": _pool([], [], []),
        "FWD": _pool([], [], []),
    }
    assert not can_complete(ids, prices, teams, 1000, {"GK": 1, "DEF": 0, "MID": 0, "FWD": 0}, pool)


def test_the_club_cap_binds_across_positions_during_the_cheapest_completion() -> None:
    """Two positions' cheapest remaining candidate share one almost-capped club. Filling both
    from it would exceed the cap, so the true cheapest completion must use the pricier second
    club for one of the two -- a naive per-position-only minimum would underestimate the cost."""
    ids = np.array([901, 902], dtype=np.int64)
    prices = np.array([40, 40], dtype=np.int64)
    teams = np.array([5, 5], dtype=np.int64)  # two of club 5 already picked -- one slot left
    pool = {
        "GK": _pool([], [], []),
        "DEF": _pool([1, 2], [40, 90], [5, 6]),  # cheapest DEF (40) is club 5
        "MID": _pool([3, 4], [40, 90], [5, 6]),  # cheapest MID (40) is also club 5
        "FWD": _pool([], [], []),
    }
    quota = {"GK": 0, "DEF": 1, "MID": 1, "FWD": 0}
    # POSITIONS processes DEF before MID: club 5's one remaining slot goes to DEF's 40, leaving
    # MID to fall back to club 6's 90 -- 130 total, not the naive (wrong) 40 + 40 = 80.
    assert not can_complete(ids, prices, teams, 80, quota, pool)
    assert can_complete(ids, prices, teams, 130, quota, pool)


def test_an_already_picked_player_still_present_in_the_pool_is_not_double_counted() -> None:
    """`can_complete` filters `picked_player_ids` out of `pool` itself -- the pool need not be
    pre-shrunk by the caller (module docstring)."""
    ids = np.array([1], dtype=np.int64)
    prices = np.array([40], dtype=np.int64)
    teams = np.array([1], dtype=np.int64)
    pool = {"GK": _pool([1], [40], [1]), "DEF": _pool([], [], []), "MID": _pool([], [], []), "FWD": _pool([], [], [])}
    # Player 1 is already picked and is the only GK in the pool -- one more GK is not available.
    assert not can_complete(ids, prices, teams, 1000, {"GK": 1, "DEF": 0, "MID": 0, "FWD": 0}, pool)
    assert can_complete(ids, prices, teams, 1000, {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}, pool)


# ---------------------------------------------------------------------------
# Purity / determinism -- no RNG, same inputs give the same answer
# ---------------------------------------------------------------------------


def test_can_complete_is_a_pure_function_of_its_arguments() -> None:
    ids, prices, teams = _empty_picks()
    quota = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
    pool = _full_pool()
    results = {can_complete(ids, prices, teams, 1000, quota, pool) for _ in range(20)}
    assert results == {True}


# ---------------------------------------------------------------------------
# False negative: check (b)'s fixed position order rejects a genuinely completable squad
# ---------------------------------------------------------------------------


def _greedy_completion_cost(
    club_counts: dict[int, int],
    quota: dict[str, int],
    eligible: dict[str, tuple[np.ndarray, np.ndarray]],
    order: list[str],
) -> int | None:
    """Check (b)'s own greedy (module docstring), but run over `order` instead of `POSITIONS`.

    Local to the one test below: demonstrates the order-sensitivity `can_complete` itself cannot
    see, since it only ever tries `POSITIONS`' fixed order. Returns the total cost, or `None` if
    `order` cannot fill `quota` at all from `eligible`.
    """
    running = dict(club_counts)
    total_cost = 0
    for position in order:
        need = quota[position]
        prices, teams = eligible[position]
        taken = 0
        for price, team in zip(prices, teams):
            team_i = int(team)
            if running.get(team_i, 0) >= MAX_PER_CLUB:
                continue
            total_cost += int(price)
            running[team_i] = running.get(team_i, 0) + 1
            taken += 1
            if taken == need:
                break
        if taken < need:
            return None
    return total_cost


def test_a_fixed_position_order_can_reject_a_squad_a_different_order_would_complete() -> None:
    """The module docstring's caveat, constructed and pinned rather than left theoretical -- per
    this pass's instructions to construct the failure mode directly rather than assume it away.

    Check (b) shares one running per-club cap across positions but only ever visits them in
    `POSITIONS` order (GK -> DEF -> MID -> FWD). That fixed order can spend a club's last cap slot
    on an early position's own cheapest candidate, stranding a later position whose *only*
    remaining candidate needed that same slot -- even when completing the later position first (so
    the early position falls back to its second-cheapest candidate) is affordable at the exact same
    total cost. `can_complete` never tries the other order, so it cannot see this.

    **The construction.** Two of club 5's three cap slots are already spent (one left). DEF's
    cheapest remaining candidate (40) is club 5; DEF's next-cheapest (90) is club 6. MID's *only*
    remaining candidate (50) is also club 5. `POSITIONS` visits DEF before MID: the greedy takes
    DEF's 40 from club 5, exhausting the cap, and MID then has nothing left -- `can_complete`
    reports infeasible at any budget. But the true cheapest completion exists at cost 140: DEF
    falls back to club 6 (90), leaving club 5's last slot for MID (50) -- visiting MID before DEF
    finds exactly this.

    This is a real, triggered false negative on this exact input -- not merely "may" reject a
    feasible squad, as the module docstring's general caveat has it, but does, here. Per that
    docstring the bias only ever runs toward more conservative (a `False` here can never hide an
    actually-illegal `True` elsewhere), so the risk is a naive baseline scoring slightly worse than
    achievable, not an unsound squad. Whether this pattern arises anywhere in the real dataset the
    three constructors actually build from is `test_feasibility_club_cap_probe.py`'s question, not
    this one's -- it swept all 33 qualifying gameweeks and found no occurrence, which is why the
    algorithm is left unchanged and this synthetic case is kept only as the regression pin.
    """
    ids = np.array([901, 902], dtype=np.int64)
    prices = np.array([40, 40], dtype=np.int64)
    teams = np.array([5, 5], dtype=np.int64)  # two of club 5 already picked -- one slot left
    pool = {
        "GK": _pool([], [], []),
        "DEF": _pool([1, 2], [40, 90], [5, 6]),  # cheapest DEF (40) is club 5; next (90) is club 6
        "MID": _pool([3], [50], [5]),  # the ONLY eligible MID is club 5
        "FWD": _pool([], [], []),
    }
    quota = {"GK": 0, "DEF": 1, "MID": 1, "FWD": 0}

    # can_complete only ever tries POSITIONS' fixed DEF-before-MID order and cannot find the true
    # completion -- fails even at the true cheapest cost, not just below it.
    assert not can_complete(ids, prices, teams, 140, quota, pool), (
        "if this starts passing, POSITIONS order or check (b)'s greedy changed -- update this pin"
    )
    assert not can_complete(ids, prices, teams, 200, quota, pool)  # generous budget: still fails

    # Confirm 140 is in fact the true cheapest completion, and that it is order-dependent: the
    # fixed POSITIONS order (DEF, MID) cannot find it, but the other order (MID, DEF) can.
    club_counts = {5: 2}
    eligible = {"DEF": (np.array([40, 90]), np.array([5, 6])), "MID": (np.array([50]), np.array([5]))}
    assert _greedy_completion_cost(club_counts, quota, eligible, ["DEF", "MID"]) is None  # POSITIONS' own order
    assert _greedy_completion_cost(club_counts, quota, eligible, ["MID", "DEF"]) == 140
