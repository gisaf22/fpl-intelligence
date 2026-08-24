"""The pre-registered bench-ordering policy set -- `DESIGN.md` §5.4.1, §4.12, §6.7, §6.8, §7.4.

**One policy, and the reason it is one is a gap rather than a selection.** §5.4 fixes
`bench_order`'s *shape* -- a non-empty ordered sequence of named policies, element 0 primary --
and names no policy. The only ordering `DESIGN.md` commits to is §4.12's: "the bench ordering is
the induced order over the 4 non-selected players, GK separated", with §6.7 and §6.8 fixing how
a score panel induces it. :data:`PRE_REGISTERED_ORDERINGS` is that ordering and nothing else.
Which *further* policies belong in the comparison set is an open decision `METRIC.md` carries no
candidates for -- §5.4.1 states it, and §1.5 lists it -- so no second policy is invented here.

**The consequence is named rather than discovered on the first run.** §4.6 defines B2, the
ordering-relevant count, over the orderings *actually compared*, and §4.7 makes B2 the
denominator for every bench-order claim. Under a one-policy set no two orderings can differ, so
**B2 = 0 and no bench-order figure is reportable**. The primary arc is unaffected: §5.4 permits a
one-policy run explicitly, primary regret is well defined under element 0, and §0.10's absolute
counterfactual -- `best_permutation_total`, over all 6 permutations -- is a squad-week property
the harness emits whatever the policy count. What a one-policy run cannot do is measure
`DECISION.md` §1's *secondary* decision.

**Tier A, and the tier is forced rather than chosen.** §5.4's `OrderingPolicy` takes a
`Sequence[BenchPlayer]` and `BenchPlayer` is defined in `harness.py`, so any module importing the
policy type is importing a Tier A module -- which §3.3 forbids Tier B. Tier A permits `domain/`,
`dal/` and Tier A siblings, all this module needs. The forward constraint that follows is recorded
at §5.4.1: an ordering policy that needed `model/` could not be written against this signature.

**Why a named identity policy rather than nothing at all.** `harness.run` hands each policy the
outfield bench already in ranking order, so a caller could get this ordering by passing a policy
that returns its input untouched. That is exactly the implicit default §5.4 exists to prevent: the
whole argument for `bench_order` having no default is that "the primary number" must always read
as "the primary number *under this ordering*", and §7.3 makes the named policy set part of run
identity. An ordering nobody named would be reproducible from the code and not from the manifest.

**And it derives the order rather than trusting the argument's.** :func:`order_by_rank` calls
`harness.rank_squad` on the bench it is given instead of returning it unchanged. The two agree --
`test_orderings.py` asserts it -- but only the first is a function of the records alone, which is
the property `rank_squad`'s own docstring claims and the one that makes this policy independent of
how the harness happened to sort its argument.

**Import closure: `harness.py`, stdlib.** Tier A (§3.3, §5.1), so no `model/`, no `research/`, no
`serve/`, and neither Tier B sibling -- `rankers.py`, `uncertainty.py`. `test_orderings.py` asserts
the closure in a subprocess, for §5.6's reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from decisions.starting_xi.harness import BenchOrder, BenchPlayer, rank_squad

# ---------------------------------------------------------------------------
# The policies (§4.12, §6.7, §6.8)
# ---------------------------------------------------------------------------

BY_RANK: Final[str] = "by_rank"
"""§4.12's induced order. The name is run identity (§7.3) and §7.4 freezes it."""


def order_by_rank(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """§4.12's ordering: the bench in the ranker's own induced order, best first.

    Args:
        bench: the outfield bench -- §4.2's three players, the GK slot having no policy because
            an ordering over one element carries no information.

    Returns:
        Their `player_id`s in priority order. Strict, and a function of the records alone:
        `rank_squad` keys on (§6.7's tier, negated score, `player_id`), and §6.8's ascending
        `player_id` breaks every remaining tie without consuming randomness.

    **Restricting the 15's ranking to the bench and ranking the bench directly give the same
    order**, because `rank_squad`'s key is a total order on records and sorting a subset under a
    total order agrees with restricting the sorted whole. That is what makes calling `rank_squad`
    here equivalent to returning the harness's argument untouched, and it is asserted rather than
    left to this paragraph.
    """
    return rank_squad(bench)


# ---------------------------------------------------------------------------
# The pre-registered set (§5.4.1, §7.4)
# ---------------------------------------------------------------------------

PRE_REGISTERED_ORDERINGS: Final[BenchOrder] = ((BY_RANK, order_by_rank),)
"""§5.4's `bench_order` argument, as §5.4.1 pre-registers it: one policy, `by_rank`, primary.

A tuple rather than a mapping because **order is meaning**: §5.4 makes element 0 the primary --
the ordering behind every figure T2 carries -- and §7.3 makes the whole ordered set, primary named
as such, part of `run_id`. A mapping would carry the same members and lose the fact that decides
which of them the headline number was computed under.

Ordering `rankers.py`'s `FLOOR_RANKERS`: both are the slice's pre-registered sets of callables the
composition root passes into the harness, and §7.4 freezes both into `PRE_REGISTRATION.yaml`.
"""
