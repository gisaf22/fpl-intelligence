"""Real-mart probe for `feasibility.can_complete`'s check (b) club-cap approximation --
`feasibility.py`'s module docstring, "the *sequential* composition across positions is a
documented approximation, not a joint optimum".

Kept in its own file, entirely marked `integration`, rather than mixed into `test_feasibility.py`
with a per-function `@pytest.mark.integration`: a module-level `pytestmark = pytest.mark.unit`
plus a per-function `integration` mark both apply to that function, so `pytest -m unit` (what
CI's unit-test job runs, against a fixture DB with no live mart) would still collect and try to
run it -- the same reasoning `test_candidates_integration.py` and
`test_gameweek_population_integration.py` give for the same split.

`test_feasibility.py::test_a_fixed_position_order_can_reject_a_squad_a_different_order_would_complete`
constructs and pins the failure mode directly: a synthetic case where check (b)'s fixed
`POSITIONS`-order greedy returns `False` for a squad that is genuinely completable under a
different position-visiting order. This file asks the empirical question that pin cannot answer
on its own: does that failure mode actually arise anywhere the three real constructors
(`decisions.free_hit.candidates`'s C1/C2/C3, via `test_candidates.POLICIES`) build a squad from
the live mart, over all 33 qualifying gameweeks (`gameweek_population.py`)?

Every `can_complete` call made during a real construction run is intercepted; every time it
returns `False`, an all-position-orderings brute force independently re-derives whether a
different order finds a cheaper, still-affordable completion -- the same "try every ordering"
method `decisions/starting_xi/harness.py`'s vacancy-order investigation used to size that sibling
slice's fixed-order approximation before deciding whether it mattered (`decisions/starting_xi/
DESIGN.md` §4.3.1: measured over all 11,100 squad-weeks before the fixed order was replaced). The
brute force's check (a) (presence) is reused unmodified from `can_complete`'s own logic -- it is
order-independent by construction (whether enough eligible players with club-room remain per
position does not depend on which position is considered first) and so cannot itself be the
source of a false reject; only check (b) is re-run over every permutation of the positions still
needing a pick, rather than `can_complete`'s single fixed order.

**Finding, as of 2026-08-31, against the live mart:** 75 `can_complete() == False` events across
the three constructors' 33 qualifying gameweeks (99 squad constructions total), 0 of which the
brute force disagrees with -- the approximation never rejected an actually-completable squad
anywhere in this sweep. Per the module docstring this failure mode can only ever make a rejection
MORE conservative, never approve an illegal squad -- so the risk it poses is a naive baseline
scoring slightly worse than achievable, never an unsound squad reaching a caller. This file's
finding is that on the real 2025-26 season's price/quota distribution, that conservatism is not,
in practice, being paid: `feasibility.py`'s check (b) is left unchanged, and this test pins the
finding so it is re-checked automatically if the mart or the three constructors change. A failure
here is evidence the approximation now matters on real data and is a decision point (tighten
check (b), or accept and re-document the cost) -- not something to silently patch.
"""

from __future__ import annotations

import itertools
from typing import Any
from unittest import mock

import numpy as np
import pytest

from dal.pipeline import load
from decisions.free_hit import candidates as candidates_mod
from decisions.free_hit.candidates import build_candidates
from decisions.free_hit.feasibility import _Pool
from decisions.free_hit.feasibility import can_complete as real_can_complete
from decisions.free_hit.gameweek_population import schedule_clean_gameweeks
from decisions.free_hit.test_candidates import POLICIES
from domain.fpl_squad import BUDGET_CAP_TENTHS, MAX_PER_CLUB, POSITIONS, SQUAD_SELECT

pytestmark = pytest.mark.integration


def _brute_force_cheapest(
    picked_ids: np.ndarray,
    picked_teams: np.ndarray,
    budget: int,
    quota: dict[str, int],
    pool: dict[str, _Pool],
) -> tuple[bool, int | None]:
    """Check (a) exactly as `can_complete` computes it (order-independent -- see module
    docstring), then check (b) taken as the minimum over every permutation of the positions still
    needing a pick, instead of `can_complete`'s single fixed `POSITIONS` order. An upper bound on
    the true joint optimum (`feasibility.py`'s own ILP note), not the optimum itself, but a
    strictly wider search than `can_complete` performs. Returns `(is_completable, cheapest_cost)`.
    """
    picked_ids = np.asarray(picked_ids)
    club_counts: dict[int, int] = {}
    for team in np.asarray(picked_teams):
        club_counts[int(team)] = club_counts.get(int(team), 0) + 1

    eligible: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for position, need in quota.items():
        if need <= 0:
            continue
        position_pool = pool.get(position)
        if position_pool is None or position_pool.size == 0:
            return False, None
        not_picked = ~np.isin(position_pool.player_id, picked_ids)
        club_has_room = np.array([club_counts.get(int(t), 0) < MAX_PER_CLUB for t in position_pool.team_id])
        mask = not_picked & club_has_room
        if int(mask.sum()) < need:
            return False, None
        order = np.argsort(position_pool.price_tenths[mask], kind="stable")
        eligible[position] = (position_pool.price_tenths[mask][order], position_pool.team_id[mask][order])

    needed_positions = [p for p in POSITIONS if quota.get(p, 0) > 0]
    costs: list[int] = []
    for perm in itertools.permutations(needed_positions):
        running = dict(club_counts)
        total_cost = 0
        ok = True
        for position in perm:
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
                ok = False
                break
        if ok:
            costs.append(total_cost)

    if not costs:
        return False, None
    cheapest = min(costs)
    return cheapest <= budget, cheapest


def test_the_club_cap_approximation_never_rejects_a_completable_squad_on_the_real_mart() -> None:
    """Swept over the three real constructors and all 33 qualifying gameweeks: does
    `can_complete`'s fixed-`POSITIONS`-order check (b) ever reject a squad an all-orderings brute
    force confirms is genuinely completable? Module docstring. See this file's module docstring
    for the 2026-08-31 finding this test pins: no, 0 of 75 `False` verdicts disagreed."""
    live_mart = load().mart
    # The §3.2 schedule axis, not `qualifying_gameweeks` -- this probe asks whether the club-cap
    # approximation is ever wrong, so it sweeps every gameweek a squad is built for, including
    # the warm-up week `METRIC.md` §3.3 excludes from *scoring*. Narrowing it would shrink the
    # probe's coverage and silently change the pinned 75-verdict figure below.
    qualifying = sorted(schedule_clean_gameweeks(live_mart))
    assert len(qualifying) == 33  # DESIGN.md §2 / INVENTORY.md §1's cited figure

    total_false = 0
    artifacts: list[dict[str, Any]] = []

    def _wrapped(
        picked_ids: np.ndarray,
        picked_prices: np.ndarray,
        picked_teams: np.ndarray,
        budget: int,
        quota: dict[str, int],
        pool: dict[str, _Pool],
    ) -> bool:
        nonlocal total_false
        result = real_can_complete(picked_ids, picked_prices, picked_teams, budget, quota, pool)
        if result is False:
            total_false += 1
            is_completable, cheapest = _brute_force_cheapest(picked_ids, picked_teams, budget, quota, pool)
            if is_completable:
                artifacts.append({"budget": int(budget), "quota": dict(quota), "brute_force_cheapest": cheapest})
        return result

    with mock.patch.object(candidates_mod, "can_complete", side_effect=_wrapped):
        for gw in qualifying:
            candidates = build_candidates(live_mart, gw)
            for policy in POLICIES:
                policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))

    assert total_false > 0, "no can_complete() == False events at all -- this sweep exercised nothing"
    assert artifacts == [], (
        f"the fixed-order approximation rejected {len(artifacts)} actually-completable squad(s) on the "
        f"real mart -- this is the theoretical failure mode in feasibility.py's docstring becoming real; "
        f"report this as a finding, do not silently patch check (b): {artifacts[:5]}"
    )
