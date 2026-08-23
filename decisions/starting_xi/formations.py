"""The shared 8-formation routine -- `DESIGN.md` §5.1, §3.5.

Two things, and nothing else:

* **`best_legal_xi`** -- the best legal XI total over a 15, and the second-best. §0.1's
  counterfactual regret is the gap between the chosen XI's total and the first; §0.8's C1
  closeness gap is the gap between the first and the second. `INVENTORY.md` §2.4 measures the
  search for the maximum: sort each position's points descending and take the best of 8
  prefix-sum combinations, no solver and no new dependency. **The second-best XI is not the
  second-best of those 8** -- `INVENTORY.md` §2.4 records that the enumeration's runner-up is the
  best total achievable by a *different* formation, and §0.8 selects the XI gap over that
  formation gap. It costs the same 8 combinations plus at most four subtractions; the derivation
  is on `best_legal_xi`.
* **`is_legal_xi`** -- §0.6's legality predicate, which §4.3's replay evaluates at every vacancy
  before a substitution is allowed to fire. It is what holds regret at or above 0: an XI that
  left the set the counterfactual maximises over could out-score its own counterfactual.

**The formation set is derived, never listed.** `LEGAL_FORMATIONS` is enumerated at import from
`domain/fpl_squad.py`'s `XI_MIN_PLAY`, `XI_MAX_PLAY` and `XI_SIZE` -- the bounds FPL declares and
`dal/staging/contracts/element_types.yaml` stages (`INVENTORY.md` §2.2). Writing the eight tuples
out here would put a second copy of a staged rule in a decision slice, where nothing checks it
against the source.

**The routine reads no data and holds no state.** That is what keeps it at `domain/`-only
(§3.5): a version that loaded its own frame would need `dal/`, and one that scored its own
candidates would need `model/`. It takes the points as an argument (§5.2). Import closure:
`domain/` and the standard library. Tier A, and the most constrained module in the slice --
`DESIGN.md` §5.1 forbids it everything project-internal except `domain/`, **including every
sibling slice module**, so it imports neither `sampler` nor anything else in this package.

**Nulls are rejected rather than filled.** A missing points value sorts unpredictably and would
propagate silently into a maximum, which is the shape of failure §8.3 guards the PPG population
against at its own call site. Whether a blank is a 0 or an exclusion is the harness's question,
not this routine's, so the precondition is asserted here and the policy stays with the caller.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate, product
from typing import Final

from domain.fpl_squad import POSITIONS, SQUAD_SELECT, XI_MAX_PLAY, XI_MIN_PLAY, XI_SIZE

Formation = tuple[int, ...]
"""A per-position starter count, in `POSITIONS` order -- (GK, DEF, MID, FWD)."""


def _enumerate_formations() -> tuple[Formation, ...]:
    """Every per-position count vector inside the XI bounds that sums to a full XI.

    `INVENTORY.md` §2.4 measures this at 8 for the staged 2025/26 bounds. The count is not
    asserted here: it is a consequence of the bounds, and pinning it in the module would make a
    changed bound fail in the wrong place. `test_formations.py` pins it against the eight tuples
    `INVENTORY.md` records, which is where a drift should surface.
    """
    per_position = [range(XI_MIN_PLAY[position], XI_MAX_PLAY[position] + 1) for position in POSITIONS]
    return tuple(sorted(counts for counts in product(*per_position) if sum(counts) == XI_SIZE))


LEGAL_FORMATIONS: Final[tuple[Formation, ...]] = _enumerate_formations()
"""The legal formations, ascending. Derived from `domain/fpl_squad.py`, not listed (see above)."""

_LEGAL: Final[frozenset[Formation]] = frozenset(LEGAL_FORMATIONS)


@dataclass(frozen=True)
class BestXI:
    """What §5.1 has the routine return: the two totals, and not their difference.

    Field names are `DESIGN.md` §7.2's T2 column names, so the harness carries them through to
    the artefact without a rename. §7.6 records why both are stored rather than the gap alone --
    #4's signed-error metric is named as required and left undefined (§0.1), and storing the
    inputs rather than the difference keeps whatever definition is eventually fixed derivable
    without re-running the harness.
    """

    best_legal_xi_points: float
    second_best_xi_points: float


def _position_counts(positions: Sequence[str]) -> Formation:
    """Count a candidate's players per position, in `POSITIONS` order.

    An unrecognised position raises rather than counting as "not GK/DEF/MID/FWD" and quietly
    making the XI illegal. §8.4 fixes `position` (GK/DEF/MID/FWD) as the slice's vocabulary and
    normalises any `position_label` value (GKP/...) at the harness boundary; a `GKP` arriving
    here means that boundary was missed, and returning `False` would turn it into every
    substitution silently failing to fire.
    """
    counts = dict.fromkeys(POSITIONS, 0)
    for position in positions:
        if position not in counts:
            raise ValueError(f"unrecognised position {position!r}; expected one of {POSITIONS} (DESIGN.md §8.4)")
        counts[position] += 1
    return tuple(counts[position] for position in POSITIONS)


def is_legal_xi(positions: Sequence[str]) -> bool:
    """Is a candidate XI a legal formation? -- §0.6's condition, as §4.3's replay applies it.

    Args:
        positions: the positions of the candidate's players, in any order. Legality is a property
            of the position multiset alone (§4.3.1), so the caller's ordering is irrelevant and
            no player identity is needed.

    Returns:
        True iff the counts sit inside the XI bounds and total a full XI. A candidate of any other
        size is not a legal XI and is reported as such: §4.3 fills one vacancy at a time precisely
        so that every state this is asked about is a complete 11, and the formation constraints
        define nothing about a partial XI.

    Raises:
        ValueError: if a position is outside the slice's vocabulary (see `_position_counts`).
    """
    return _position_counts(positions) in _LEGAL


def best_legal_xi(positions: Sequence[str], points: Sequence[float]) -> BestXI:
    """The best legal XI total over a 15, and the second-best legal XI total.

    Sorting each position's points descending makes the best XI *for a given formation* a sum of
    per-position prefixes, so the maximum is 8 prefix-sum combinations (`INVENTORY.md` §2.4).

    **The second-best XI is not the second-best of those 8**, and §0.8 selects the XI gap over the
    formation gap for that reason. Any legal XI other than the best either has a different
    formation -- and is then at most that formation's own best, one of the other 7 -- or shares the
    winning formation, in which case it differs from the best by demoting at least one starter. A
    formation's best XI takes the top *n* at each position, so any other selection under it loses at
    least the smallest single-demotion gap, and demoting exactly one starter achieves that loss. The
    second-best legal XI is therefore the larger of those two candidates.

    Args:
        positions: each of the 15 players' positions.
        points: each player's points, positionally aligned with `positions`.

    Returns:
        A `BestXI`. `best_legal_xi_points` is the maximum over the 8 combinations;
        `second_best_xi_points` is the best total over every legal XI *except* the maximising one
        -- so two legal XIs tied at the top give an equal pair, which is §0.8's zero-gap squad-week
        and is excluded from the conditioned sample there rather than here.

    Raises:
        ValueError: if the two arguments differ in length; if the squad is not the 2/5/5/3 quota
            §5.1 states the input as; if a position is outside the slice's vocabulary; or if any
            points value is not finite.
    """
    if len(positions) != len(points):
        raise ValueError(f"positions and points differ in length: {len(positions)} vs {len(points)}")

    counts = _position_counts(positions)
    quota = tuple(SQUAD_SELECT[position] for position in POSITIONS)
    if counts != quota:
        raise ValueError(f"expected the {quota} quota over {POSITIONS}, got {counts}")

    ranked: dict[str, list[float]] = {position: [] for position in POSITIONS}
    for position, value in zip(positions, points, strict=True):
        if not math.isfinite(value):
            raise ValueError(f"points contains a non-finite value ({value!r}); nulls are the caller's to resolve")
        ranked[position].append(float(value))

    descending = {position: sorted(values, reverse=True) for position, values in ranked.items()}
    # prefix[position][k] is the sum of that position's top k players; index 0 is the empty sum,
    # which is what lets a formation index straight into it.
    prefix = {position: [0.0, *accumulate(values)] for position, values in descending.items()}

    totals = {
        formation: sum(prefix[position][n] for position, n in zip(POSITIONS, formation, strict=True))
        for formation in LEGAL_FORMATIONS
    }

    # Ties resolve to the lowest formation tuple, since `LEGAL_FORMATIONS` is ascending and the
    # dict preserves that order. Which one is named does not affect either total: a tie at the top
    # makes `best_elsewhere` equal to `best`, so the pair comes back equal either way.
    winner = max(totals, key=lambda formation: totals[formation])
    best = totals[winner]

    # Candidate (a): the best XI under each of the other 7 formations.
    best_elsewhere = max(total for formation, total in totals.items() if formation != winner)

    # Candidate (b): the winning side with exactly one starter demoted to the next player at his
    # position. A position offers a demotion only where the 15 holds more players than the
    # formation starts. The list is never empty -- every legal formation starts 1 of the squad's 2
    # goalkeepers -- and runs to 2-4 entries across the 8.
    demotions = [
        descending[position][n - 1] - descending[position][n]
        for position, n in zip(POSITIONS, winner, strict=True)
        if n < len(descending[position])
    ]
    best_demoted = best - min(demotions)

    return BestXI(best_legal_xi_points=best, second_best_xi_points=max(best_elsewhere, best_demoted))
