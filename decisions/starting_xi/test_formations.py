"""Tests for the 8-formation routine -- `DESIGN.md` §5.1, §0.8, §0.6.

The XI space is small enough that "exhaustive" is available where the squad space (§2.8) forced
the sampler's tests onto reduced universes, so it is used:

* **Legality is checked over every position multiset**, not over examples. Every non-negative
  (GK, DEF, MID, FWD) count vector summing to 0-15 is put to `is_legal_xi` and compared against
  the XI bounds read independently from `domain/fpl_squad.py`. Nothing is sampled.
* **The maximum is checked against brute force over every legal XI.** `INVENTORY.md` §2.4's
  prefix-sum shortcut is the claim under test, so the reference is all 1,365 11-subsets of the
  15, filtered and maximised directly. If the shortcut is wrong for any arrangement of points,
  a seeded sweep of squads finds it.
* Where a test could pass by being blind -- the guard against non-finite points, the exhaustive
  legality sweep, the runner-up's identity -- the counterfactual is executed rather than
  described, so the assertion is known to have something to fail against.
"""

from __future__ import annotations

import math
import subprocess
import sys
from functools import cache
from itertools import combinations

import numpy as np
import pytest

from decisions.starting_xi.formations import LEGAL_FORMATIONS, best_legal_xi, is_legal_xi
from domain.fpl_squad import POSITIONS, SQUAD_SELECT, SQUAD_SIZE, XI_MAX_PLAY, XI_MIN_PLAY, XI_SIZE

pytestmark = pytest.mark.unit


# `INVENTORY.md` §2.4's measured formation set, written out here and nowhere in the module. This
# is the drift test for `domain/fpl_squad.py`'s XI bounds: the module derives the set from those
# bounds, so a bound that moved without the document moving fails here rather than silently
# changing what the counterfactual maximises over.
INVENTORY_FORMATIONS = (
    (1, 3, 4, 3),
    (1, 3, 5, 2),
    (1, 4, 3, 3),
    (1, 4, 4, 2),
    (1, 4, 5, 1),
    (1, 5, 2, 3),
    (1, 5, 3, 2),
    (1, 5, 4, 1),
)


def _bounds_say_legal(counts: tuple[int, ...]) -> bool:
    """The legality rule read straight off `domain/fpl_squad.py`, independently of the module."""
    return sum(counts) == XI_SIZE and all(
        XI_MIN_PLAY[position] <= n <= XI_MAX_PLAY[position] for position, n in zip(POSITIONS, counts, strict=True)
    )


def _spell(counts: tuple[int, ...]) -> list[str]:
    """A candidate XI's positions, given its per-position counts."""
    return [position for position, n in zip(POSITIONS, counts, strict=True) for _ in range(n)]


def _count_vectors(total: int) -> list[tuple[int, ...]]:
    """Every non-negative 4-vector summing to `total`."""
    return [
        (gk, de, mi, total - gk - de - mi)
        for gk in range(total + 1)
        for de in range(total - gk + 1)
        for mi in range(total - gk - de + 1)
    ]


_QUOTA_LAYOUT = _spell(tuple(SQUAD_SELECT[position] for position in POSITIONS))
"""The 15's positions in `POSITIONS` order -- 2 GK, then 5 DEF, then 5 MID, then 3 FWD."""


def _quota_squad(points: list[float]) -> tuple[list[str], list[float]]:
    """A 2/5/5/3 squad carrying `points`, in `POSITIONS` order."""
    assert len(points) == SQUAD_SIZE
    return list(_QUOTA_LAYOUT), list(points)


def _ranked(positions: list[str], points: list[float]) -> dict[str, list[float]]:
    """Each position's points, descending. Written out here rather than imported so the routine's
    own prefix arithmetic is never the reference for a test of that arithmetic."""
    return {
        position: sorted((points[i] for i, p in enumerate(positions) if p == position), reverse=True)
        for position in POSITIONS
    }


@cache
def _legal_elevens() -> tuple[tuple[int, ...], ...]:
    """Every legal XI of a 2/5/5/3 squad, as index tuples into `_quota_squad`'s layout.

    All 1,365 eleven-subsets of the 15, filtered by the bounds read from `domain/fpl_squad.py` --
    550 survive. Which subsets are legal depends only on the position layout, which is fixed, so
    this is computed once and reused; that is what makes a 4,000-squad sweep affordable.
    """
    return tuple(
        xi
        for xi in combinations(range(SQUAD_SIZE), XI_SIZE)
        if _bounds_say_legal(tuple(sum(_QUOTA_LAYOUT[i] == position for i in xi) for position in POSITIONS))
    )


def _brute_force(positions: list[str], points: list[float]) -> tuple[float, float]:
    """The best legal XI total and the second-best **distinct XI** total, by enumeration.

    The reference the routine is checked against. It ranks *XIs* rather than formations, which is
    how the two quantities come apart -- see
    `test_the_second_best_total_is_the_second_best_xi_not_the_second_best_formation`. It shares no
    arithmetic with the routine: no prefix sums, no formation set, no demotion rule.
    """
    assert positions == _QUOTA_LAYOUT, "the cached subsets assume _quota_squad's layout"
    ordered = sorted((sum(points[i] for i in xi) for xi in _legal_elevens()), reverse=True)
    return ordered[0], ordered[1]


def _formation_gap_runner_up(positions: list[str], points: list[float]) -> float:
    """The **superseded** computation: the second-largest of the 8 formation totals.

    Kept as a live counterfactual rather than a comment. §0.8 rejected this quantity, and the
    tests below assert that the routine does not return it -- so a rewrite that quietly regresses
    to the cheaper computation fails rather than passes quietly.
    """
    ranked = _ranked(positions, points)
    totals = sorted(
        (sum(sum(ranked[p][:n]) for p, n in zip(POSITIONS, formation, strict=True)) for formation in LEGAL_FORMATIONS),
        reverse=True,
    )
    return totals[1]


# ---------------------------------------------------------------------------
# The formation set -- derived from `domain/`, pinned against `INVENTORY.md` §2.4
# ---------------------------------------------------------------------------


def test_the_derived_formation_set_is_the_eight_inventory_measured() -> None:
    assert LEGAL_FORMATIONS == INVENTORY_FORMATIONS


def test_every_derived_formation_sits_inside_the_domain_bounds() -> None:
    """The set is a consequence of `domain/fpl_squad.py`, so it is checked against it and not
    only against the literal above: together the two make a changed bound a loud failure."""
    assert all(_bounds_say_legal(formation) for formation in LEGAL_FORMATIONS)
    assert len(set(LEGAL_FORMATIONS)) == len(LEGAL_FORMATIONS)


# ---------------------------------------------------------------------------
# §0.6 legality -- exhaustive over every position multiset
# ---------------------------------------------------------------------------


def test_legality_agrees_with_the_domain_bounds_on_every_position_multiset() -> None:
    """Every count vector summing to 0-15, not a sample of them. 3,876 cases."""
    checked = 0
    for total in range(SQUAD_SIZE + 1):
        for counts in _count_vectors(total):
            assert is_legal_xi(_spell(counts)) is _bounds_say_legal(counts), counts
            checked += 1
    assert checked == 3876, checked

    # Executed, not claimed: the sweep above contains both verdicts, in quantity. A predicate
    # stuck at False -- the shape an unrecognised-position bug would take -- would pass a sweep
    # that happened to contain no legal case, and one stuck at True would pass the converse.
    legal = [counts for total in range(SQUAD_SIZE + 1) for counts in _count_vectors(total) if _bounds_say_legal(counts)]
    assert len(legal) == len(LEGAL_FORMATIONS)
    assert len(legal) < checked


def test_legality_ignores_the_order_the_positions_arrive_in() -> None:
    """§4.3.1: legality is a property of the multiset, which is why the replay may fill vacancies
    in a pinned order without that order entering the constraint."""
    rng = np.random.default_rng(0)
    xi = _spell((1, 4, 4, 2))
    for _ in range(20):
        assert is_legal_xi(list(rng.permutation(xi)))


def test_a_short_or_long_candidate_is_not_a_legal_xi() -> None:
    assert not is_legal_xi(_spell((1, 4, 4, 2))[:10])
    assert not is_legal_xi([*_spell((1, 4, 4, 2)), "MID"])
    assert is_legal_xi(_spell((1, 4, 4, 2)))


def test_an_unrecognised_position_raises_rather_than_reporting_an_illegal_xi() -> None:
    """§8.4 normalises `position_label` (GKP) at the harness boundary. A GKP reaching here means
    that was missed, and a `False` would show up as every substitution silently failing to fire
    rather than as an error -- so the same XI is asserted legal under the normalised vocabulary."""
    unnormalised = ["GKP", *_spell((0, 4, 4, 2))]
    with pytest.raises(ValueError, match="unrecognised position"):
        is_legal_xi(unnormalised)
    assert is_legal_xi(["GK", *_spell((0, 4, 4, 2))])


# ---------------------------------------------------------------------------
# §0.1/§0.8 -- the two totals, against brute force over every legal XI
# ---------------------------------------------------------------------------


SWEEP_SQUADS = 4000
"""Squads in the brute-force sweep. Held at the count the demotion rule was originally validated
at, so the test *is* that validation rather than a thinner re-run of it. It costs ~1s: the legal
eleven-subsets depend only on the fixed position layout, so `_legal_elevens` computes them once."""


def _sweep_squad(seed: int) -> tuple[list[str], list[float]]:
    """One squad of the sweep. Integer points over a range wide enough that the binding formation
    moves between squads, and wide enough to admit ties -- both are asserted below."""
    rng = np.random.default_rng(seed)
    return _quota_squad([float(x) for x in rng.integers(-2, 20, SQUAD_SIZE)])


def test_both_totals_match_brute_force_over_every_legal_xi() -> None:
    """The whole claim, against the only reference that shares no arithmetic with it.

    `INVENTORY.md` §2.4's prefix-sum shortcut supplies the maximum; §0.8's demotion rule supplies
    the second-best. `_brute_force` supplies both by enumerating every legal XI directly. Run over
    `SWEEP_SQUADS` squads, which is the validation the design's cost claim rests on -- §0.8 states
    the second-best legal XI is either another formation's best or a single demotion within the
    winning one, and if that is wrong for any arrangement of points this is what finds it.
    """
    for seed in range(SWEEP_SQUADS):
        positions, points = _sweep_squad(seed)
        result = best_legal_xi(positions, points)
        assert (result.best_legal_xi_points, result.second_best_xi_points) == _brute_force(positions, points), seed


def test_the_formation_gap_would_fail_the_sweep_above() -> None:
    """The counterfactual, executed at sweep scale: §0.8's rejected computation must **not** pass.

    Without this, `test_both_totals_match_brute_force_over_every_legal_xi` could be passing on
    squads where the two quantities happen to coincide, and a rewrite that regressed to the
    cheaper formation gap would go unnoticed. The disagreement is asserted to be common rather
    than merely non-empty, so the guard does not rest on a handful of lucky seeds: **1,186 of the
    4,000 squads separate the two quantities**, measured against this fixture. The floor is set an
    order of magnitude below that -- it exists to catch a regression to the formation gap, not to
    pin a property of the point distribution these squads are drawn from.

    The one-directional relation `INVENTORY.md` §2.4 records is asserted on every squad, not just
    on the ones that disagree: the formation gap never exceeds the XI gap.
    """
    disagreed = 0
    for seed in range(SWEEP_SQUADS):
        positions, points = _sweep_squad(seed)
        formation_gap = _formation_gap_runner_up(positions, points)
        true_second = _brute_force(positions, points)[1]
        assert formation_gap <= true_second, f"the formation gap must never exceed the XI gap: seed {seed}"
        disagreed += formation_gap != true_second
    assert disagreed > SWEEP_SQUADS // 10, f"only {disagreed} of {SWEEP_SQUADS} squads distinguish the two"


def test_the_demotion_search_stays_within_four_candidates() -> None:
    """§0.8's cost claim, checked rather than asserted: at most one demotion per position, and only
    where the 15 leaves a spare. The bound is what keeps this inside a `formations.py`-shaped pure
    function, so a formation admitting more would be a finding, not a slow path."""
    sizes = {
        sum(1 for position, n in zip(POSITIONS, formation, strict=True) if n < SQUAD_SELECT[position])
        for formation in LEGAL_FORMATIONS
    }
    assert sizes <= {2, 3, 4}, sizes
    assert min(sizes) >= 1, "a formation offering no demotion would make the second-best XI undefined here"


def test_the_sweep_is_not_answered_by_one_formation_alone() -> None:
    """The sweep above would be blind if every squad's best XI came from the same formation: a
    routine that enumerated one combination would pass. It does not -- the maximising formation
    varies across the seeds, so the enumeration is load-bearing."""
    binding = set()
    for seed in range(200):
        positions, points = _sweep_squad(seed)
        best = best_legal_xi(positions, points).best_legal_xi_points
        ranked = _ranked(positions, points)
        for formation in LEGAL_FORMATIONS:
            if sum(sum(ranked[p][:n]) for p, n in zip(POSITIONS, formation, strict=True)) == best:
                binding.add(formation)
    assert len(binding) > 1, binding


def test_the_maximum_is_the_best_of_the_eight_combinations() -> None:
    """The first total only, against the eight formation totals computed independently here, so
    the routine's own prefix arithmetic is not the reference for its own maximum. The *second*
    total is deliberately not checked this way -- it is not one of these eight."""
    positions, points = _sweep_squad(7)
    ranked = _ranked(positions, points)
    totals = [
        sum(sum(ranked[p][:n]) for p, n in zip(POSITIONS, formation, strict=True)) for formation in LEGAL_FORMATIONS
    ]
    assert best_legal_xi(positions, points).best_legal_xi_points == max(totals)


def test_the_second_best_total_is_the_second_best_xi_not_the_second_best_formation() -> None:
    """Which of two quantities §0.8's C1 is, pinned on the squad the decision was taken on.

    §0.8 selects the **XI** gap: the second-best legal XI, which within the winning formation may
    be one starter demoted rather than a different formation entirely. The formation gap -- the
    second-largest of the 8 combinations -- is the rejected candidate, and this squad separates
    them by 15 points. All three values are asserted, so the two quantities cannot silently
    converge and the routine cannot silently return the wrong one.
    """
    positions, points = _quota_squad(
        [200.0, 10.0, 100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0, 5.0, 4.0, 3.0]
    )
    result = best_legal_xi(positions, points)
    best_xi, second_best_xi = _brute_force(positions, points)

    assert result.best_legal_xi_points == best_xi == 745.0
    assert result.second_best_xi_points == second_best_xi == 744.0

    # The rejected computation, executed: it returns 729 here, and returning it would fail.
    assert _formation_gap_runner_up(positions, points) == 729.0
    assert result.second_best_xi_points != _formation_gap_runner_up(positions, points)

    # 744 is the winning (1,5,4,1) side with its one forward demoted from 5.0 to 4.0 -- a
    # single demotion inside the winner, which is the branch the formation gap cannot reach.
    assert result.best_legal_xi_points - result.second_best_xi_points == 1.0


def test_two_formations_tied_at_the_top_give_an_equal_pair() -> None:
    """§0.8's zero-gap squad-week, which is excluded and counted at the conditioning step rather
    than signalled here: the routine reports the two totals and nothing else."""
    positions, points = _quota_squad([1.0] * SQUAD_SIZE)
    result = best_legal_xi(positions, points)
    assert result.best_legal_xi_points == result.second_best_xi_points == 11.0


def test_the_totals_do_not_depend_on_the_order_the_squad_arrives_in() -> None:
    rng = np.random.default_rng(3)
    positions, points = _quota_squad([float(x) for x in rng.integers(0, 15, SQUAD_SIZE)])
    baseline = best_legal_xi(positions, points)
    order = rng.permutation(SQUAD_SIZE)
    assert best_legal_xi([positions[i] for i in order], [points[i] for i in order]) == baseline


def test_a_player_who_scored_nothing_is_still_selectable_when_the_bounds_require_it() -> None:
    """§0.2 applies no substitutions to the counterfactual side, so a blanked player is a 0 in
    the enumeration rather than an omission: with only three forwards and a `>= 1 FWD` minimum,
    every legal XI carries one however he scored."""
    positions, points = _quota_squad([9.0] * 12 + [0.0] * 3)
    # 1 GK + 5 DEF + 4 MID at 9 each, plus the forward the minimum forces in at 0.
    assert best_legal_xi(positions, points).best_legal_xi_points == 90.0


# ---------------------------------------------------------------------------
# Preconditions the caller owns
# ---------------------------------------------------------------------------


def test_a_non_finite_points_value_raises_rather_than_propagating_into_the_maximum() -> None:
    """The guard's counterfactual is executed: without it, a NaN sorts into the leading slots and
    the maximum comes back NaN -- a wrong answer that looks like a value, not like a failure."""
    assert math.isnan(sum(sorted([float("nan"), 1.0, 2.0], reverse=True)[:2]))

    positions, points = _quota_squad([5.0] * SQUAD_SIZE)
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="non-finite"):
            best_legal_xi(positions, [bad, *points[1:]])
    assert best_legal_xi(positions, points).best_legal_xi_points == 55.0


def test_a_squad_that_is_not_the_quota_raises() -> None:
    positions, points = _quota_squad([5.0] * SQUAD_SIZE)
    with pytest.raises(ValueError, match="quota"):
        best_legal_xi(positions[:-1], points[:-1])
    with pytest.raises(ValueError, match="quota"):
        best_legal_xi(["MID", *positions[1:]], points)


def test_mismatched_positions_and_points_raise() -> None:
    positions, points = _quota_squad([5.0] * SQUAD_SIZE)
    with pytest.raises(ValueError, match="differ in length"):
        best_legal_xi(positions, points[:-1])


# ---------------------------------------------------------------------------
# §3.5/§5.1 -- the most constrained module in the slice, and it stays that way
# ---------------------------------------------------------------------------


def test_importing_the_routine_pulls_in_no_layer_below_domain_and_no_sibling() -> None:
    """§5.1 forbids `formations.py` everything project-internal except `domain/` -- `dal/`
    included, and every sibling slice module included. Run in a subprocess for §5.6's reason: the
    session has already imported `model` via `testpaths`, so an in-process `sys.modules` check
    could not tell this module's closure from what was already loaded."""
    program = (
        "import sys; import decisions.starting_xi.formations; "
        "leaked = [m for m in sys.modules "
        "if m.split('.')[0] in {'model', 'research', 'serve', 'dal', 'operational'} "
        "or m.startswith('decisions.starting_xi.') and m != 'decisions.starting_xi.formations']; "
        "assert not leaked, leaked; "
        "assert 'domain.fpl_squad' in sys.modules"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0
