"""Incremental, partial-squad feasibility primitive -- `DESIGN.md` §3.

Built in-slice rather than promoted to `domain/fpl_squad_feasibility.py` (`DESIGN.md` §3: no
`Player`/`Pool` type exists anywhere in the repository to share, and `.importlinter`'s
`no_layers_to_decisions` contract forbids `domain/` from importing anything under `decisions/`
regardless). `can_complete` is the whole of the primitive: given a partial squad (three parallel
arrays) and the gameweek's eligible pool, can the squad still be completed inside the remaining
budget and quota.

**Two deviations from `DESIGN.md` §3's literal code block, flagged rather than silently applied
(per this pass's instructions to stop and report rather than improvise past a gap):**

1. **`pool` is `dict[str, _Pool]`, not a single `_Pool`.** `DESIGN.md`'s signature types `pool`
   as one `_Pool` -- but its own two checks are stated *per remaining position*, and a single
   `_Pool` (parallel arrays with no position field, per `decisions.starting_xi.sampler`) cannot
   support a per-position lookup. `dict[str, _Pool]` mirrors
   `decisions.starting_xi.sampler._Universe.pools`'s shape -- the one part of that module already
   doing the "eligible pool split by position" job (`INVENTORY.md` §3).
2. **`_Pool` is redefined here, not imported from `sampler.py`.** Importing a sibling decision
   slice's module-private class would be a tighter, more fragile coupling than `DESIGN.md` §3's
   "operating on the same array-shaped representation... already uses" language calls for -- read
   here as shape-parity, not a literal shared import. This keeps the primitive self-contained
   (§3/§4's own reasoning for staying in-slice) and respects the read-only-reference boundary
   this build pass was given against the `starting_xi` slice.

**Check (b)'s "cheapest feasible completion", stated precisely.** `DESIGN.md` §3 does not fully
specify how the per-club cap interacts *across* positions when estimating the cheapest
completion (a club could be exhausted by picks made for one remaining position before another
remaining position is even considered). This implementation resolves it as a **sequential
per-position greedy in `domain.fpl_squad.POSITIONS` order**: cheapest-first within each position,
decrementing a running per-club capacity shared across positions as it goes. Within one position
this greedy is optimal (minimum-cost k-of-n selection under a per-group cap is solved exactly by
a cheapest-first partition-matroid greedy), but the *sequential* composition across positions is
a documented approximation, not a joint optimum -- it can only ever overstate the true cheapest
cost, so a `True` return is always sound (a cheaper real completion may exist) and a `False`
return is conservative (it may reject a still-feasible squad in a rare shared-club edge case,
never accept an infeasible one). Resolving this exactly is ILP-shaped and out of this pass's
scope (`DECISION.md` §4, §5).

**That rare shared-club edge case, probed rather than left theoretical.** The failure mode is
real and constructible:
`test_feasibility.py::test_a_fixed_position_order_can_reject_a_squad_a_different_order_would_complete`
pins a synthetic case where check (b) returns `False` at the true cheapest completion's exact cost,
because `POSITIONS` order spends a club's last cap slot on an earlier position's own cheapest pick
when a later position's only remaining candidate needed that same slot -- visiting the positions in
the other order finds the completion `can_complete` misses. Proven non-triggering on the real
2025-26 dataset as of 2026-08-31, though: swept over all three real constructors
(`decisions.free_hit.candidates`'s C1/C2/C3) across all 33 qualifying gameweeks
(`gameweek_population.py`), 75 `can_complete() == False` events occurred and an all-orderings
brute force confirmed every one was a genuine rejection, 0 artifacts of the fixed order -- see
`test_feasibility_club_cap_probe.py::test_the_club_cap_approximation_never_rejects_a_completable_squad_on_the_real_mart`
for the measurement and its method. The algorithm is unchanged; both tests are pinned as
regressions so this is re-checked automatically if the mart or the constructors change, mirroring
`decisions/starting_xi/DESIGN.md` §4.3.1's vacancy-fill-order investigation, which resolved the
same class of fixed-order-approximation question the same way.

No RNG anywhere in this module -- `can_complete` is a pure function of its arguments.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain.fpl_squad import MAX_PER_CLUB, POSITIONS


@dataclass(frozen=True)
class _Pool:
    """One position's slice of a gameweek's eligible pool, as parallel arrays.

    Mirrors `decisions.starting_xi.sampler._Pool`'s shape exactly -- see module docstring for
    why it is redefined here rather than imported.
    """

    player_id: np.ndarray
    price_tenths: np.ndarray
    team_id: np.ndarray

    @property
    def size(self) -> int:
        return int(self.player_id.size)


def can_complete(
    picked_player_ids: np.ndarray,
    picked_prices: np.ndarray,
    picked_teams: np.ndarray,
    remaining_budget_tenths: int,
    remaining_quota: dict[str, int],
    pool: dict[str, _Pool],
) -> bool:
    """Can the partially-picked squad still be completed, per `DESIGN.md` §3's two checks.

    Args:
        picked_player_ids, picked_prices, picked_teams: the players already selected, as
            parallel arrays (empty arrays for a squad with nothing picked yet).
        remaining_budget_tenths: budget left after `picked_prices`' cost, in integer tenths.
        remaining_quota: players still needed per position (`domain.fpl_squad.POSITIONS`
            values). A position with nothing left to fill may be given 0 or omitted -- both are
            treated identically.
        pool: this gameweek's eligible pool, split by position. Not pre-filtered by the caller:
            `can_complete` removes already-picked players and clubs already at
            `domain.fpl_squad.MAX_PER_CLUB` itself, using `picked_player_ids`/`picked_teams` --
            so the same `pool` can be built once per gameweek and reused unchanged across every
            call in one construction run.

    Returns:
        `False` if either check fails: (a) fewer than `remaining_quota[position]` eligible
        players remain in `pool[position]` for some position still needing more, after removing
        already-picked players and clubs already at the cap; or (b) the cheapest feasible
        completion found (module docstring) costs more than `remaining_budget_tenths`. `True`
        otherwise, including when `remaining_quota` needs nothing further and the budget is
        non-negative.
    """
    if remaining_budget_tenths < 0:
        return False

    picked_ids = np.asarray(picked_player_ids)
    club_counts: dict[int, int] = {}
    for team in np.asarray(picked_teams):
        team_i = int(team)
        club_counts[team_i] = club_counts.get(team_i, 0) + 1

    # (a) Presence: enough eligible players per remaining position, after removing already-picked
    # players and clubs already at the cap. Also builds each position's price-sorted eligible
    # arrays for (b), so the pool is scanned once per position rather than twice.
    eligible: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for position, need in remaining_quota.items():
        if need <= 0:
            continue
        position_pool = pool.get(position)
        if position_pool is None or position_pool.size == 0:
            return False

        not_picked = ~np.isin(position_pool.player_id, picked_ids)
        club_has_room = np.array([club_counts.get(int(team), 0) < MAX_PER_CLUB for team in position_pool.team_id])
        mask = not_picked & club_has_room
        if int(mask.sum()) < need:
            return False

        order = np.argsort(position_pool.price_tenths[mask], kind="stable")
        eligible[position] = (position_pool.price_tenths[mask][order], position_pool.team_id[mask][order])

    # (b) Cheapest feasible completion: sequential per-position greedy in POSITIONS order,
    # sharing one running per-club capacity across positions (module docstring).
    running_club_counts = dict(club_counts)
    total_cost = 0
    for position in POSITIONS:
        need = remaining_quota.get(position, 0)
        if need <= 0:
            continue
        prices, teams = eligible[position]
        taken = 0
        for price, team in zip(prices, teams):
            team_i = int(team)
            if running_club_counts.get(team_i, 0) >= MAX_PER_CLUB:
                continue
            total_cost += int(price)
            running_club_counts[team_i] = running_club_counts.get(team_i, 0) + 1
            taken += 1
            if taken == need:
                break
        if taken < need:
            return False

    return total_cost <= remaining_budget_tenths
