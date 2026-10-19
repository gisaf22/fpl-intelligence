"""The pre-registered bench-ordering policy set (`PRE_REGISTRATION.yaml`'s `bench_ordering`).

**One policy, and the reason it is one is a gap rather than a selection.** `bench_order`'s
*shape* is fixed -- a non-empty ordered sequence of named policies, element 0 primary -- but no
policy is named by it. The one committed ordering is the induced order over the 4 non-selected
players, GK separated, with CARD.md §3's ranking fixing how a score panel induces it.
:data:`PRE_REGISTERED_ORDERINGS` is that ordering and nothing else. Which *further* policies
belong in the comparison set is an open decision with no candidates yet, so no second policy is
invented here.

**The consequence is named rather than discovered on the first run.** B2, the ordering-relevant
count, is defined over the orderings *actually compared*, and it is the denominator for every
bench-order claim. Under a one-policy set no two orderings can differ, so
**B2 = 0 and no bench-order figure is reportable**. The primary arc is unaffected: a one-policy run
is permitted explicitly, primary regret is well defined under element 0, and the absolute
counterfactual -- `best_permutation_total`, over all 6 permutations -- is a squad-week property
the harness emits whatever the policy count. What a one-policy run cannot do is measure
the *secondary* bench-order decision (CARD.md §1).

**Tier A, and the tier is forced rather than chosen.** `OrderingPolicy` takes a
`Sequence[BenchPlayer]` and `BenchPlayer` is defined in `harness.py`, so any module importing the
policy type is importing a Tier A module -- which the import contract forbids Tier B. Tier A
permits `domain/`, `dal/` and Tier A siblings, all this module needs. The forward constraint that
follows: an ordering policy that needed `model/` could not be written against this signature.

**Why a named identity policy rather than nothing at all.** `harness.run` hands each policy the
outfield bench already in ranking order, so a caller could get this ordering by passing a policy
that returns its input untouched. That is exactly the implicit default the signature exists to prevent: the
whole argument for `bench_order` having no default is that "the primary number" must always read
as "the primary number *under this ordering*", and the named policy set is part of run
identity. An ordering nobody named would be reproducible from the code and not from the manifest.

**And it derives the order rather than trusting the argument's.** :func:`order_by_rank` calls
`harness.rank_squad` on the bench it is given instead of returning it unchanged. The two agree --
`test_orderings.py` asserts it -- but only the first is a function of the records alone, which is
the property `rank_squad`'s own docstring claims and the one that makes this policy independent of
how the harness happened to sort its argument.

**Import closure: `harness.py`, stdlib.** Tier A, so no `model/`, no `research/`, no
`serve/`, and neither Tier B sibling -- `rankers.py`, `uncertainty.py`. `test_orderings.py` asserts
the closure in a subprocess.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from decisions.starting_xi.harness import BenchOrder, BenchPlayer, rank_squad

# ---------------------------------------------------------------------------
# The policies
# ---------------------------------------------------------------------------

BY_RANK: Final[str] = "by_rank"
"""The induced order. The name is run identity and `PRE_REGISTRATION.yaml` freezes it."""


def order_by_rank(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """The induced ordering: the bench in the ranker's own induced order, best first.

    Args:
        bench: the outfield bench -- three players, the GK slot having no policy because
            an ordering over one element carries no information.

    Returns:
        Their `player_id`s in priority order. Strict, and a function of the records alone:
        `rank_squad` keys on (tier, negated score, `player_id`) per CARD.md §3, and ascending
        `player_id` breaks every remaining tie without consuming randomness.

    **Restricting the 15's ranking to the bench and ranking the bench directly give the same
    order**, because `rank_squad`'s key is a total order on records and sorting a subset under a
    total order agrees with restricting the sorted whole. That is what makes calling `rank_squad`
    here equivalent to returning the harness's argument untouched, and it is asserted rather than
    left to this paragraph.
    """
    return rank_squad(bench)


BY_WEIGHTED_SCORE: Final[str] = "by_weighted_score"
"""A second naive floor-candidate for the bench-order comparison set (an open item).

Not pre-registered: closing "which ordering policies form the comparison set" takes a metric
pass, which has not run. Defined and tested here so that pass has a second
naive candidate to characterise against `by_rank`, which should not be the sole naive baseline.
"""

_POSITION_WEIGHT: Final[dict[str, float]] = {"DEF": 1.00, "MID": 1.05, "FWD": 1.10}
"""A fixed multiplier on `score`, read off `position` alone -- no `model/` access, no new input.

**The rule.** Within the scored tier, sort on `score * _POSITION_WEIGHT[position]` descending
instead of on `score` alone; the no-fixture and unrankable tiers are unchanged from `order_by_rank`
because CARD.md §3 fixes that demotion and a naive alternative has no basis to relitigate it. **Why these
three numbers and this direction:** FPL's biggest hauls cluster in the most advanced positions
(one attacking return is worth more to a FWD's week than a defensive one is to a DEF's), so a
bench-caller who trusts nothing but position tendency nudges an advanced player above an
equal-or-slightly-higher-scored deeper one rather than reading `score` as position-neutral.
"""


def order_by_weighted_score(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """Position-weighted score, best first -- the module's second naive ordering.

    Args:
        bench: the outfield bench -- the same three records `order_by_rank` sees, and nothing more
            (`score`, `position`, `no_fixture`, `player_id`).

    Returns:
        Their `player_id`s in priority order. Strict: ties inside the scored tier -- on
        `score * _POSITION_WEIGHT[position]`, not on `score` -- break on ascending `player_id`,
        the same tie-break CARD.md §3 fixes for `order_by_rank`, so the two policies differ only on the
        weighting and never on how a remaining tie resolves.

    A function of the records alone, by the same sort-is-a-total-order argument `order_by_rank`'s
    docstring makes: this key is total on the records handed to it, so restricting or permuting the
    input cannot change the answer. `test_orderings.py` sweeps that claim exhaustively, and
    separately proves this policy is not a relabelled `order_by_rank` -- it produces a different
    order on a bench constructed to expose the weighting, not merely runs without error.
    """
    no_fixture = [player for player in bench if player.no_fixture]
    unrankable = [player for player in bench if not player.no_fixture and player.score is None]
    scored = [player for player in bench if not player.no_fixture and player.score is not None]

    scored_ordered = sorted(
        scored,
        key=lambda p: (-(p.score * _POSITION_WEIGHT[p.position]), p.player_id),  # type: ignore[operator]
    )
    unrankable_ordered = sorted(unrankable, key=lambda p: p.player_id)
    no_fixture_ordered = sorted(no_fixture, key=lambda p: p.player_id)

    return tuple(player.player_id for player in (*scored_ordered, *unrankable_ordered, *no_fixture_ordered))


# ---------------------------------------------------------------------------
# The pre-registered set
# ---------------------------------------------------------------------------

PRE_REGISTERED_ORDERINGS: Final[BenchOrder] = ((BY_RANK, order_by_rank),)
"""The `bench_order` argument, as pre-registered: one policy, `by_rank`, primary.

A tuple rather than a mapping because **order is meaning**: element 0 is the primary --
the ordering behind every reported figure -- and the whole ordered set, primary named
as such, is part of `run_id`. A mapping would carry the same members and lose the fact that decides
which of them the headline number was computed under.

Like `rankers.rules`, it is a pre-registered set of callables the composition root passes into the
harness, and `PRE_REGISTRATION.yaml` freezes both.
"""
