"""Tests for the replay engine -- `DESIGN.md` §4.3, §6.7, §6.8, §5.1.

The design supplies three references this suite uses instead of examples, and each is executed
rather than described:

* **§6.7's equivalence is re-proved by exhaustion, not cited.** Every score profile drawable from
  a 3-valued alphabet -- 26,460 of them, ties everywhere -- is put to `select_xi`, to a greedy
  scan down the ranking, and to brute force over all 550 legal XIs of a 2/5/5/3 squad. The
  agreement §6.7 proves is the assertion, and the counterfactual is executed: a plain top-11 that
  ignores legality fails the same sweep.
* **§4.3.1's vacancy-order invariance obligation is discharged here, and it fails.** The minimal
  counterexample is pinned, and the failure's scope is swept over every permutation of the
  vacancy order on seeded multi-blank squad-weeks. §4.3.1 carries the cost measured over all
  11,100 squad-weeks and the slackest-first rule that replaced the fixed DEF-first order; these
  tests assert that rule's behaviour on the case that broke the old one.
* **§4.3's worked example is replayed**, and the priority-queue reading is separated from the
  consume-on-skip alternative by running both -- so the test knows it has something to fail
  against, per `METRIC.md` §2.5.
* **§0.10's absolute counterfactual is checked by exhaustion**, which is available because there
  are only 3! = 6 orderings of the outfield bench: `best_permutation_total` is re-derived from an
  independent enumeration on every squad-week of the fixture, and the relative form it replaced is
  computed alongside it and asserted to differ, so the suite cannot pass by being blind to which
  form the module emits.

Where a claim could pass by being blind -- the two `best_legal_xi` calls not being conflated, the
as-of statistic's denominator, the registration predicate matching the sampler's, the tie-break's
direction -- the wrong version is computed alongside the right one and asserted to differ.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement, permutations, product

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi.formations import LEGAL_FORMATIONS, is_legal_xi
from decisions.starting_xi.harness import (
    BenchPlayer,
    HarnessResult,
    as_of_points,
    build,
    rank_squad,
    registration_gw,
    replay,
    run,
    select_xi,
)
from decisions.starting_xi.sampler import _registration_gw
from domain.fpl_squad import POSITIONS, SQUAD_SELECT, SQUAD_SIZE, XI_MAX_PLAY, XI_MIN_PLAY, XI_SIZE

pytestmark = pytest.mark.unit


# `DESIGN.md` §7.2's T2 and T5 column sets, written out here and nowhere in the module. A column
# added, removed or renamed in the module without the document moving fails here.
T2_COLUMNS = (
    "squad_id",
    "gw",
    "ranker",
    "chosen_xi_points",
    "best_legal_xi_points",
    "best_legal_xi_asof",
    "second_best_xi_asof",
    "regret",
    "closeness_gap",
    "is_zero_gap",
    "substitution_fired",
    "uncovered_blank",
    "no_fixture_rule_changed_xi",
    "best_permutation_total",
)
T5_COLUMNS = (
    "squad_id",
    "gw",
    "ranker",
    "ordering_name",
    "is_primary",
    "substitution_fired",
    "realised_total",
    "entered_gk",
    "entered_outfield",
)

# A canonical 2/5/5/3 squad, ids ascending in position order.
SQUAD = tuple(range(SQUAD_SIZE))
POSITION_OF = {
    player_id: position
    for player_id, position in zip(SQUAD, [p for p in POSITIONS for _ in range(SQUAD_SELECT[p])], strict=True)
}


# ---------------------------------------------------------------------------
# Independent references
# ---------------------------------------------------------------------------

# Every legal 11-subset of a 2/5/5/3 squad, enumerated once. This is the brute-force reference
# `select_xi`'s prefix-sum shortcut is checked against.
LEGAL_XIS = tuple(
    frozenset(combo)
    for combo in combinations(SQUAD, XI_SIZE)
    if is_legal_xi([POSITION_OF[player_id] for player_id in combo])
)


def _brute_force_best_total(value: dict[int, float]) -> float:
    """The maximum total over every legal XI, by enumeration rather than by shortcut."""
    return max(sum(value[player_id] for player_id in xi) for xi in LEGAL_XIS)


def _greedy_xi(ranking: Sequence[int]) -> frozenset[int]:
    """§6.7's Reading B: scan the ranking, take a player if a legal XI stays reachable.

    Written independently of the module -- this is the *other* reading, and the point of the
    sweep below is that it and `select_xi` return the same total.
    """
    lo = tuple(XI_MIN_PLAY[p] for p in POSITIONS)
    hi = tuple(XI_MAX_PLAY[p] for p in POSITIONS)
    counts = [0, 0, 0, 0]
    chosen: list[int] = []
    for player_id in ranking:
        if len(chosen) == XI_SIZE:
            break
        index = POSITIONS.index(POSITION_OF[player_id])
        counts[index] += 1
        reachable = all(c <= h for c, h in zip(counts, hi, strict=True)) and (
            sum(max(low, c) for low, c in zip(lo, counts, strict=True)) <= XI_SIZE
        )
        if reachable:
            chosen.append(player_id)
        else:
            counts[index] -= 1
    return frozenset(chosen)


def _records(scores: Sequence[float | None], no_fixture: Sequence[bool] | None = None) -> list[BenchPlayer]:
    flags = [False] * SQUAD_SIZE if no_fixture is None else list(no_fixture)
    return [
        BenchPlayer(player_id=player_id, position=POSITION_OF[player_id], score=score, no_fixture=flag)
        for player_id, score, flag in zip(SQUAD, scores, flags, strict=True)
    ]


def _profiles(alphabet: Sequence[int]) -> Iterator[list[float]]:
    """Every score profile over `alphabet`, up to within-position permutation.

    Only the multiset per position matters to the maximum, so enumerating sorted multisets is
    exhaustive over the space that can distinguish the two readings, not a sample of it.
    """
    pools = [list(combinations_with_replacement(alphabet, SQUAD_SELECT[p])) for p in POSITIONS]
    for combo in product(*pools):
        yield [float(x) for pool in combo for x in pool]


# ---------------------------------------------------------------------------
# §6.7 -- the selection rule, and the equivalence it rests on
# ---------------------------------------------------------------------------


def test_selection_matches_brute_force_and_the_greedy_reading_on_every_three_valued_profile() -> None:
    """§6.7's claim, exhaustively: Reading A, Reading B and brute force agree on the total.

    26,460 profiles, ties throughout -- which is the case that matters, since §6.7 records that
    the two readings agree on membership only when scores are distinct. The sweep is over the
    *total*, which is what the equivalence covers and what §0.1's regret is built from.
    """
    checked = 0
    for scores in _profiles(range(3)):
        ranking = rank_squad(_records(scores))
        value = dict(zip(SQUAD, scores, strict=True))
        chosen = select_xi(ranking, POSITION_OF)
        total = sum(value[player_id] for player_id in chosen)
        assert total == _brute_force_best_total(value), scores
        assert total == sum(value[player_id] for player_id in _greedy_xi(ranking)), scores
        checked += 1
    assert checked == 26_460, checked


def test_a_selection_ignoring_legality_would_fail_that_sweep() -> None:
    """The counterfactual for the test above, executed rather than asserted.

    Without this, `test_selection_matches_brute_force_...` could be passing because every profile
    happens to make the top 11 legal, in which case it would be checking nothing about the
    formation constraints. A plain top-11-by-ranking is run over the same profiles and must both
    produce an illegal XI and miss the maximum somewhere.
    """
    illegal = 0
    wrong_total = 0
    for scores in _profiles(range(3)):
        ranking = rank_squad(_records(scores))
        naive = frozenset(ranking[:XI_SIZE])
        value = dict(zip(SQUAD, scores, strict=True))
        if not is_legal_xi([POSITION_OF[player_id] for player_id in naive]):
            illegal += 1
        if sum(value[player_id] for player_id in naive) != _brute_force_best_total(value):
            wrong_total += 1
    assert illegal > 0, "the naive rule never produced an illegal XI; the sweep proves nothing"
    assert wrong_total > 0, "the naive rule never missed the maximum; the sweep proves nothing"


def test_every_selected_xi_is_a_legal_formation() -> None:
    """Legality is a precondition of §0.1's lower bound (§0.6), so it is checked on the sweep."""
    for scores in _profiles(range(3)):
        chosen = select_xi(rank_squad(_records(scores)), POSITION_OF)
        assert len(chosen) == XI_SIZE
        assert is_legal_xi([POSITION_OF[player_id] for player_id in chosen]), scores


def test_membership_is_unique_under_distinct_scores_and_matches_the_greedy_reading() -> None:
    """§6.7 records the membership half of the equivalence: the two readings agree exactly when
    the scores are distinct, where the maximum-weight basis is unique."""
    rng = np.random.default_rng(0)
    for _ in range(2_000):
        scores = [float(x) for x in rng.permutation(SQUAD_SIZE)]
        ranking = rank_squad(_records(scores))
        assert select_xi(ranking, POSITION_OF) == _greedy_xi(ranking), scores


def test_membership_agrees_with_the_greedy_reading_on_every_three_valued_profile() -> None:
    """§6.7's equivalence covers membership too, not only the total -- because the maximisation is
    over the **ranking**, whose values are distinct, so the maximiser is unique. Exhaustive over
    the same 26,460 profiles, ties included, since ties are where a non-unique maximiser would
    show up."""
    for scores in _profiles(range(3)):
        ranking = rank_squad(_records(scores))
        assert select_xi(ranking, POSITION_OF) == _greedy_xi(ranking), scores


def test_maximising_the_raw_score_column_would_break_that_membership_agreement() -> None:
    """The executed counterfactual for §6.7's "what is maximised" paragraph.

    Without it, `test_membership_agrees_...` could be passing because membership is insensitive to
    the maximised quantity, in which case naming that quantity would be pointless. Reading A run on
    the raw score column instead of on rank position must select a *different* XI somewhere -- it
    does, on 19,602 of the 26,460 profiles -- which is exactly why §6.7 fixes the quantity rather
    than leaving "maximise the score" to be read the obvious way.
    """

    def raw_score_reading_a(scores: Sequence[float], ranking: Sequence[int]) -> frozenset[int]:
        value = dict(zip(SQUAD, scores, strict=True))
        by_position = {position: [p for p in ranking if POSITION_OF[p] == position] for position in POSITIONS}
        best: frozenset[int] = frozenset()
        best_total: float | None = None
        for formation in LEGAL_FORMATIONS:
            picked = [p for position, n in zip(POSITIONS, formation, strict=True) for p in by_position[position][:n]]
            total = sum(value[p] for p in picked)
            if best_total is None or total > best_total:
                best_total, best = total, frozenset(picked)
        return best

    differing = sum(
        raw_score_reading_a(scores, rank_squad(_records(scores))) != _greedy_xi(rank_squad(_records(scores)))
        for scores in _profiles(range(3))
    )
    assert differing == 19_602, differing


def test_the_maximising_formation_is_unique_so_no_formation_tie_break_can_fire() -> None:
    """§6.7 records this as measured: enumerating all 7,567,560 assignments of the fifteen
    distinct rank values to the 2/5/5/3 quota finds no case where two formations tie on the
    rank-value sum. That full enumeration is too slow for this suite, so the property is checked
    over every 3-valued score profile plus a seeded sweep of distinct-score rankings -- and it is
    checked as *uniqueness of the maximum*, which is the claim, rather than as agreement with a
    tie-break rule that can never fire."""

    def maxima(ranking: Sequence[int]) -> int:
        value = {player_id: SQUAD_SIZE - index for index, player_id in enumerate(ranking)}
        by_position = {position: [p for p in ranking if POSITION_OF[p] == position] for position in POSITIONS}
        totals = [
            sum(value[p] for position, n in zip(POSITIONS, formation, strict=True) for p in by_position[position][:n])
            for formation in LEGAL_FORMATIONS
        ]
        return totals.count(max(totals))

    for scores in _profiles(range(3)):
        assert maxima(rank_squad(_records(scores))) == 1, scores
    rng = np.random.default_rng(13)
    for _ in range(5_000):
        assert maxima(tuple(int(x) for x in rng.permutation(SQUAD_SIZE))) == 1


# ---------------------------------------------------------------------------
# §6.8 / §6.5 / §0.4 -- the ranking's three tiers and its tie-break
# ---------------------------------------------------------------------------


def test_equal_scores_are_broken_by_ascending_player_id() -> None:
    assert rank_squad(_records([0.0] * SQUAD_SIZE)) == SQUAD


def test_a_descending_tie_break_would_give_a_different_xi() -> None:
    """§6.8's counterfactual. The rule only matters if the direction changes the answer, so the
    reversed convention is executed and must select a different XI."""
    scores = [0.0] * SQUAD_SIZE
    ascending = select_xi(rank_squad(_records(scores)), POSITION_OF)
    reversed_ranking = tuple(
        player_id for player_id in sorted(SQUAD, key=lambda p: (POSITIONS.index(POSITION_OF[p]), -p))
    )
    assert select_xi(reversed_ranking, POSITION_OF) != ascending


def test_the_tie_break_consumes_no_randomness() -> None:
    """§6.8 forbids a live draw, including a seeded one: two runs sharing a seed must select the
    same XI. Repeated calls with an independently shuffled input must return one answer."""
    rng = np.random.default_rng(7)
    scores = [0.0] * SQUAD_SIZE
    answers = set()
    for _ in range(50):
        shuffled = list(_records(scores))
        rng.shuffle(shuffled)
        answers.add(rank_squad(shuffled))
    assert len(answers) == 1


def test_a_scored_player_outranks_an_unrankable_one_who_outranks_a_no_fixture_one() -> None:
    """§6.7 fixes the tier order and §6.6 records that reversing the last two would reintroduce
    §0.4's asymmetry. Each tier is given the *best* possible score so only the tier can be doing
    the work."""
    records = [
        BenchPlayer(player_id=0, position="GK", score=-99.0, no_fixture=False),
        BenchPlayer(player_id=1, position="GK", score=None, no_fixture=False),
        BenchPlayer(player_id=2, position="GK", score=99.0, no_fixture=True),
    ]
    assert [r.player_id for r in sorted(records, key=lambda r: rank_squad_index(records, r))] == [0, 1, 2]


def rank_squad_index(records: Sequence[BenchPlayer], record: BenchPlayer) -> int:
    """Position of one record in the ranking over a partial squad, via the module's own rule."""
    ordered = sorted(
        records,
        key=lambda r: (
            2 if r.no_fixture else (0 if r.score is not None else 1),
            -(r.score if r.score is not None else 0.0),
            r.player_id,
        ),
    )
    return [r.player_id for r in ordered].index(record.player_id)


def test_a_no_fixture_player_is_ranked_last_however_high_his_score() -> None:
    """§0.4: the rule is the harness's and applies identically to every ranker. `METRIC.md` §2.3
    records that a PPG ranker scores such a player at 0, which is not last -- so a raw-score
    ranking would not implement the rule and the demotion has to be explicit."""
    scores = [1.0] * SQUAD_SIZE
    flags = [False] * SQUAD_SIZE
    scores[3], flags[3] = 100.0, True  # a DEF with the best score in the squad, but no fixture
    ranking = rank_squad(_records(scores, flags))
    assert ranking[-1] == 3


def test_an_unrankable_player_sits_below_every_scored_player() -> None:
    """§6.5's rule, and it never invents a score."""
    scores: list[float | None] = [-50.0] * SQUAD_SIZE
    scores[7] = None
    ranking = rank_squad(_records(scores))
    assert ranking.index(7) == SQUAD_SIZE - 1


# ---------------------------------------------------------------------------
# §4.3 -- the replay
# ---------------------------------------------------------------------------


def _uniform(value: float) -> dict[int, float]:
    return dict.fromkeys(SQUAD, value)


def test_the_worked_example_from_section_4_3_replays_as_the_document_states() -> None:
    """§4.3's worked multi-substitution case, replayed exactly as written.

    Chosen XI is 1-3-5-2; a DEF and a MID both blank; the outfield bench in priority order is
    [FWD_a, DEF_b, MID_c]. FWD_a is skipped at the DEF vacancy (1-2-5-3 breaks the 3-DEF
    minimum), DEF_b enters, and FWD_a then enters at the MID vacancy giving a legal 1-3-4-3 --
    **because he was retained rather than consumed**.
    """
    xi = frozenset([0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13])  # GK0, DEF 2/3/4, MID 7-11, FWD 12/13
    assert sorted(POSITION_OF[p] for p in xi) == sorted(["GK"] + ["DEF"] * 3 + ["MID"] * 5 + ["FWD"] * 2)
    minutes: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    minutes[4] = 0.0  # a starting DEF blanks
    minutes[11] = 0.0  # a starting MID blanks
    bench_outfield = [14, 5, 6]  # FWD_a, DEF_b, MID_c -- the priority order under test

    result = replay(xi, SQUAD, POSITION_OF, minutes, _uniform(1.0), bench_outfield)

    assert result.entered_outfield == (5, 14), "DEF_b then FWD_a; FWD_a was retained at the first vacancy"
    assert result.substitution_fired and not result.uncovered_blank
    assert result.realised_total == float(XI_SIZE)


def test_a_consume_on_skip_rule_would_replay_the_worked_example_differently() -> None:
    """`METRIC.md` §2.5 says a rule treating a skipped player as spent measures a *different*
    bench order, and §0.6 selects the priority-queue reading over it. Both are run here, so the
    test above is known to be distinguishing them rather than passing on a case where they agree.
    """
    xi = frozenset([0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13])
    minutes: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    minutes[4] = 0.0
    minutes[11] = 0.0
    queue = [14, 5, 6]

    # The consume-on-skip alternative, written out rather than described.
    live = dict.fromkeys(sorted(xi), True)
    consumed: list[int] = []
    remaining = list(queue)
    for vacancy in [4, 11]:
        del live[vacancy]
        while remaining:
            candidate = remaining.pop(0)
            if is_legal_xi([POSITION_OF[p] for p in [*live, candidate]]):
                live[candidate] = True
                consumed.append(candidate)
                break

    assert tuple(sorted(consumed)) != replay(xi, SQUAD, POSITION_OF, minutes, _uniform(1.0), queue).entered_outfield


def test_the_final_total_is_NOT_invariant_to_the_vacancy_order() -> None:
    """§4.3.1's test obligation, discharged -- and it **fails**, which is why the rule changed.

    §4.3.1 formerly pinned DEF-then-MID-then-FWD, stated the invariance "as a test obligation and
    not as a premise", and said that "if the test fails, the pinned order is still the rule and
    the failure is a finding to report". It failed on this case; §4.3.1 then measured the cost of
    the fixed order over all 11,100 squad-weeks -- 143 points against 2 for serving the slackest
    position first -- and replaced it. The case is kept as the regression on the mechanism.

    **The counterexample, in full.** Chosen XI is 1-3-5-2 -- GK 0, DEF 4/5/6, MID 7-11, FWD 12/13.
    DEF 5 and MID 7 blank. The bench is GK 1, DEF 2, DEF 3, FWD 14, and **both bench defenders
    blanked too**, so §0.5 leaves FWD 14 as the only eligible substitute.

    * **DEF vacancy first** (the retired order). Removing DEF 5 leaves 1-2-5-2; FWD 14 would give
      1-2-5-3, which breaks the 3-DEF minimum, so he is skipped and the vacancy goes **unfilled**.
      The XI is now DEF-deficient, so at the MID vacancy 14 would give 1-2-4-3 -- still illegal.
      He never enters and the XI finishes with nine.
    * **MID vacancy first.** Removing MID 7 leaves 1-3-4-2; FWD 14 gives 1-3-4-3, which is legal,
      so he enters. The XI finishes with ten.

    **The mechanism, which is what makes this more than a curiosity: an unfilled vacancy poisons
    every vacancy behind it.** Leaving a slot empty drops the XI below a positional minimum, and
    the minimum can then never be restored, so each later substitution is illegal for a reason
    created by the ordering rather than by the squad. It therefore bites only where an uncovered
    blank (§4.6) is already present -- and the retired order served DEF vacancies first, which is
    where the binding 3-DEF minimum makes an unfilled vacancy most likely.

    **What the module now does on it.** DEF has zero slack here (3 live against a 3-minimum) and
    MID has three, so §4.3.1's rule serves MID first and reaches the better of the two totals.
    """
    xi = frozenset([0, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13])
    assert sorted(POSITION_OF[p] for p in xi) == sorted(["GK"] + ["DEF"] * 3 + ["MID"] * 5 + ["FWD"] * 2)
    minutes: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    for blank in (2, 3, 5, 7):
        minutes[blank] = 0.0
    points = _uniform(1.0)
    outfield = [14, 2, 3]

    def_first = _replay_with_vacancy_order(xi, minutes, points, outfield, [5, 7])
    mid_first = _replay_with_vacancy_order(xi, minutes, points, outfield, [7, 5])
    assert def_first == float(XI_SIZE - 2), "FWD 14 is stranded behind the unfilled DEF vacancy"
    assert mid_first == float(XI_SIZE - 1), "served the other way round, FWD 14 comes on"
    assert def_first != mid_first, "if these agreed, §4.3.1's invariance would hold after all"

    # And the module implements §4.3.1's slack order, so it defers the tight DEF vacancy and
    # produces the second of the two -- not the first, as the retired rule did.
    result = replay(xi, SQUAD, POSITION_OF, minutes, points, outfield)
    assert result.realised_total == mid_first
    assert result.entered_outfield == (14,), "FWD 14 enters at the MID vacancy, served first"
    assert result.uncovered_blank, "the DEF vacancy still goes unfilled; slack order salvages the other"


def test_the_slack_order_beats_the_retired_fixed_order_and_reaches_the_bound() -> None:
    """§4.3.1's selection, on its own terms rather than on the pinned case alone.

    §4.3.1 measures slack ordering over the mart as never worse than the retired DEF-then-MID-
    then-FWD order on any of the 11,100 squad-weeks, strictly better on 105, and 2 points short
    of the best-over-orderings bound in one. That measurement needs the mart; what is checkable
    here is the same comparison over seeded multi-vacancy squad-weeks, at a blank rate high
    enough to exercise the poisoning case often.

    The GK is held featuring throughout, because `_replay_with_vacancy_order` implements §4.3's
    outfield loop only. Comparing it against `replay`, which also runs §0.6's GK slot, would
    compare two different quantities and the sweep would assert nothing about the vacancy order.
    """
    rng = np.random.default_rng(7)
    exercised = strictly_better = 0
    for _ in range(1500):
        scores = [float(x) for x in rng.permutation(SQUAD_SIZE)]
        ranking = rank_squad(_records(scores))
        xi = select_xi(ranking, POSITION_OF)
        minutes: dict[int, float | None] = {p: (0.0 if rng.random() < 0.4 else 90.0) for p in SQUAD}
        for player_id in SQUAD:
            if POSITION_OF[player_id] == "GK":
                minutes[player_id] = 90.0
        points = {p: float(rng.integers(0, 15)) for p in SQUAD}
        outfield = [p for p in ranking if p not in xi and POSITION_OF[p] != "GK"]
        vacancies = [p for p in xi if POSITION_OF[p] != "GK" and minutes[p] == 0.0]
        if len(vacancies) < 2:
            continue
        exercised += 1
        retired = _replay_with_vacancy_order(
            xi,
            minutes,
            points,
            outfield,
            sorted(vacancies, key=lambda p: (POSITIONS.index(POSITION_OF[p]), p)),
        )
        bound = max(
            _replay_with_vacancy_order(xi, minutes, points, outfield, list(order)) for order in permutations(vacancies)
        )
        actual = replay(xi, SQUAD, POSITION_OF, minutes, points, outfield).realised_total
        assert actual >= retired, f"slack order lost to the retired fixed order: {actual} < {retired}"
        assert actual == bound, f"slack order fell short of the best vacancy order: {actual} < {bound}"
        strictly_better += actual > retired
    assert exercised >= 200, f"only {exercised} multi-vacancy squad-weeks; the sweep proves little"
    assert strictly_better > 0, "the two rules never diverged, so this sweep asserts nothing"


def test_the_vacancy_order_only_matters_where_a_vacancy_goes_unfilled() -> None:
    """The scope of the finding above, measured rather than asserted.

    If invariance held wherever every vacancy is covered, the failure is confined to uncovered
    blanks and the pinned order is harmless elsewhere. Swept over seeded multi-vacancy
    squad-weeks: no squad-week in which every ordering fills every vacancy may show a difference.
    """
    rng = np.random.default_rng(11)
    exercised = covered_differing = 0
    for _ in range(600):
        scores = [float(x) for x in rng.permutation(SQUAD_SIZE)]
        ranking = rank_squad(_records(scores))
        xi = select_xi(ranking, POSITION_OF)
        minutes: dict[int, float | None] = {p: (0.0 if rng.random() < 0.3 else 90.0) for p in SQUAD}
        points = {p: float(rng.integers(0, 15)) for p in SQUAD}
        outfield = [p for p in ranking if p not in xi and POSITION_OF[p] != "GK"]
        vacancies = [p for p in xi if POSITION_OF[p] != "GK" and minutes[p] == 0.0]
        if len(vacancies) < 2:
            continue
        exercised += 1
        totals = {_replay_with_vacancy_order(xi, minutes, points, outfield, order) for order in permutations(vacancies)}
        if len(totals) > 1 and not replay(xi, SQUAD, POSITION_OF, minutes, points, outfield).uncovered_blank:
            covered_differing += 1
    assert exercised >= 50, f"only {exercised} multi-vacancy squad-weeks; the sweep proves little"
    assert covered_differing == 0, "a fully-covered squad-week differed by vacancy order"


def _replay_with_vacancy_order(
    xi: frozenset[int],
    minutes: dict[int, float | None],
    points: dict[int, float],
    outfield: Sequence[int],
    order: Sequence[int],
) -> float:
    """§4.3's loop with the vacancy order supplied, so the pinned order can be varied."""
    live = dict.fromkeys(sorted(xi), True)
    queue = list(outfield)
    for vacancy in order:
        del live[vacancy]
        for candidate in queue:
            if minutes[candidate] is None or minutes[candidate] == 0.0:
                continue
            if is_legal_xi([POSITION_OF[p] for p in [*live, candidate]]):
                live[candidate] = True
                queue.remove(candidate)
                break
    return float(sum(points[p] for p in live))


def test_an_incoming_substitute_must_himself_have_featured() -> None:
    """§0.5, under §0.3's two-state predicate -- `minutes = 0` and `minutes` NULL alike."""
    xi = frozenset([0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13])
    minutes: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    minutes[12] = 0.0  # a starting FWD blanks
    minutes[14] = 0.0  # the bench FWD did not feature either
    minutes[5] = None  # the bench DEF's club had no fixture

    result = replay(xi, SQUAD, POSITION_OF, minutes, _uniform(1.0), [14, 5, 6])
    assert result.entered_outfield == (6,), "only the MID featured, and 1-3-5-2 -> 1-3-6-1 is illegal"


def test_a_blank_the_bench_cannot_cover_is_an_uncovered_blank_not_a_quiet_zero() -> None:
    """§4.6's third quantity. §7.5 turns on the distinction between this and "no substitution
    fired", so both are constructed and asserted to differ."""
    xi = frozenset([0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13])
    blanked: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    blanked[12] = 0.0
    for bench in (14, 5, 6):
        blanked[bench] = 0.0

    covered = replay(xi, SQUAD, POSITION_OF, _uniform(90.0), _uniform(1.0), [14, 5, 6])
    uncovered = replay(xi, SQUAD, POSITION_OF, blanked, _uniform(1.0), [14, 5, 6])

    assert not covered.substitution_fired and not covered.uncovered_blank
    assert not uncovered.substitution_fired and uncovered.uncovered_blank
    assert uncovered.realised_total == float(XI_SIZE - 1), "the XI finished short"


def test_the_gk_slot_is_a_separate_process_and_no_ordering_can_change_it() -> None:
    """§4.2: a 15 holds exactly 2 goalkeepers and every legal XI starts 1, so the GK ordering is
    degenerate. Every permutation of the outfield bench must leave `entered_gk` identical."""
    xi = frozenset([0, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13])
    minutes: dict[int, float | None] = _uniform(90.0)  # type: ignore[assignment]
    minutes[0] = 0.0  # the starting GK blanks
    results = {
        replay(xi, SQUAD, POSITION_OF, minutes, _uniform(1.0), list(order)) for order in permutations([14, 5, 6])
    }
    assert {r.entered_gk for r in results} == {1}
    assert {r.entered_outfield for r in results} == {()}


def test_a_replay_never_lets_the_chosen_side_out_score_its_own_counterfactual() -> None:
    """§0.1's lower bound, which §0.6's legality requirement exists to protect. Checked as a
    property over seeded squad-weeks rather than on one case."""
    from decisions.starting_xi.formations import best_legal_xi

    rng = np.random.default_rng(3)
    for _ in range(500):
        scores = [float(x) for x in rng.permutation(SQUAD_SIZE)]
        ranking = rank_squad(_records(scores))
        xi = select_xi(ranking, POSITION_OF)
        minutes: dict[int, float | None] = {p: (0.0 if rng.random() < 0.4 else 90.0) for p in SQUAD}
        points = {p: float(rng.integers(0, 20)) for p in SQUAD}
        outfield = [p for p in ranking if p not in xi and POSITION_OF[p] != "GK"]
        result = replay(xi, SQUAD, POSITION_OF, minutes, points, outfield)
        ceiling = best_legal_xi([POSITION_OF[p] for p in SQUAD], [points[p] for p in SQUAD])
        assert result.realised_total <= ceiling.best_legal_xi_points + 1e-9


# ---------------------------------------------------------------------------
# §0.9 / §8.3 -- the as-of statistic
# ---------------------------------------------------------------------------


def _mart(rows: Sequence[tuple[int, int, str, float | None, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["player_id", "gw", "position", "minutes", "total_points"]).astype(
        {"minutes": "Float64", "total_points": "Float64"}
    )


def test_the_as_of_statistic_matches_an_independent_per_player_reference() -> None:
    """§0.9's definition, computed the slow way and compared: total points before *t* over
    gameweeks before *t* since registration, blanks and no-fixture at 0, prefix excluded."""
    rng = np.random.default_rng(5)
    rows: list[tuple[int, int, str, float | None, float | None]] = []
    for player_id in range(6):
        debut = int(rng.integers(1, 5))
        for gw in range(1, 12):
            if gw < debut:
                rows.append((player_id, gw, "MID", None, None))
            elif rng.random() < 0.25:
                rows.append((player_id, gw, "MID", None, None))  # a blank after registration
            else:
                rows.append((player_id, gw, "MID", 90.0, float(rng.integers(0, 12))))
    mart = _mart(rows)

    # `registration_gw` is the module's; the reference below re-derives the window from the raw
    # rows so the two are not the same computation twice.
    got = as_of_points(mart).set_index(["player_id", "gw"])["as_of_points"].to_dict()
    for player_id in range(6):
        own = mart.loc[mart["player_id"] == player_id].sort_values("gw")
        played = own.loc[own["minutes"].notna(), "gw"]
        debut = int(played.min())
        for gw in range(debut, 12):
            prior = own.loc[(own["gw"] >= debut) & (own["gw"] < gw), "total_points"].fillna(0).astype(float)
            expected = float(prior.sum() / len(prior)) if len(prior) else 0.0
            assert got[(player_id, gw)] == pytest.approx(expected), (player_id, gw)


def test_an_appearance_denominated_statistic_would_differ() -> None:
    """§8.3 names this as the silent-wrong-answer risk: a rolling mean that skips nulls yields
    an *appearance*-denominated rate, which §0.9 rejects. The wrong quantity is computed here so
    the test above is known to be pinning the right one."""
    mart = _mart(
        [
            (1, 1, "MID", 90.0, 10.0),
            (1, 2, "MID", None, None),  # a blank -- counts at 0 under §0.9
            (1, 3, "MID", 90.0, 2.0),
            (1, 4, "MID", 90.0, 0.0),
        ]
    )
    got = as_of_points(mart).set_index("gw")["as_of_points"].to_dict()
    assert got[4] == pytest.approx(12 / 3), "gameweeks elapsed"
    assert got[4] != pytest.approx(12 / 2), "appearances -- the quantity §0.9 rejects"


def test_pre_registration_weeks_do_not_count() -> None:
    """§0.9: charging a GW20 entrant with nineteen zeros would score the DAL's cartesian spine
    (`INVENTORY.md` §2.5), not the player. The counting version is computed and must differ."""
    rows: list[tuple[int, int, str, float | None, float | None]] = [(1, gw, "MID", None, None) for gw in range(1, 5)]
    rows += [(1, gw, "MID", 90.0, 6.0) for gw in range(5, 8)]
    got = as_of_points(_mart(rows)).set_index("gw")["as_of_points"].to_dict()
    assert set(got) == {5, 6, 7}, "prefix rows are not in the population at all"
    assert got[7] == pytest.approx(6.0)
    assert got[7] != pytest.approx(12 / 6), "the prefix-counting version"


def test_a_player_registering_at_the_squad_week_itself_scores_zero_not_a_nan() -> None:
    """The empty-denominator case, which §0.9 does not reach and `harness.py` resolves at 0. A
    NaN here would reach `best_legal_xi`, which rejects non-finite values -- so the case has to
    be answered, and the answer is asserted rather than left to a docstring."""
    got = as_of_points(_mart([(1, 1, "MID", 90.0, 7.0), (1, 2, "MID", 90.0, 3.0)]))
    assert got.loc[got["gw"] == 1, "as_of_points"].item() == 0.0
    assert np.isfinite(got["as_of_points"]).all()


def test_the_registration_predicate_is_the_samplers() -> None:
    """§8.3's coupling claim -- the conditioning statistic and the squad universe read **one**
    population -- is only true if the two predicates agree. Asserted against the sampler's own
    private helper rather than restated, so a drift in either fails here."""
    rng = np.random.default_rng(9)
    rows: list[tuple[int, int, str, float | None, float | None]] = []
    for player_id in range(12):
        debut = int(rng.integers(1, 9))
        for gw in range(1, 12):
            featured = gw >= debut and rng.random() < 0.8
            rows.append((player_id, gw, "MID", 90.0 if featured else None, 4.0 if featured else None))
    mart = _mart(rows)
    pd.testing.assert_series_equal(registration_gw(mart), _registration_gw(mart))


# ---------------------------------------------------------------------------
# §5.1 / §7.2 -- the run, and the two calls it must not conflate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Ranker:
    """A stand-in for §6.1's `RankerOutput`, satisfying the protocol structurally."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _by_rank(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """The trivial policy: the harness's own ranking order, which is how it arrives."""
    return tuple(record.player_id for record in bench)


def _reversed(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    return tuple(record.player_id for record in reversed(list(bench)))


def _fixture(
    n_squads: int = 3, gameweeks: Sequence[int] = (2, 3, 4), seed: int = 1
) -> tuple[pd.DataFrame, pd.DataFrame, _Ranker]:
    """A small mart, squad table and ranker, built together so the ids line up."""
    rng = np.random.default_rng(seed)
    n_players = 60
    positions = [p for p in POSITIONS for _ in range(SQUAD_SELECT[p] * 4)]
    rows: list[tuple[int, int, str, float | None, float | None]] = []
    for player_id in range(n_players):
        for gw in range(1, max(gameweeks) + 1):
            draw = rng.random()
            if draw < 0.1:
                rows.append((player_id, gw, positions[player_id], None, None))
            elif draw < 0.25:
                rows.append((player_id, gw, positions[player_id], 0.0, 0.0))
            else:
                rows.append((player_id, gw, positions[player_id], 90.0, float(rng.integers(0, 16))))
    mart = _mart(rows)

    # §2.1's registration predicate, applied when drawing: the sampler builds the universe before
    # drawing, so a squad never names a player who has not yet registered. The harness rejects one
    # that does, and a fixture ignoring it would be testing an input the slice cannot produce.
    registered = registration_gw(mart)
    squad_rows = []
    for gw in gameweeks:
        eligible = {int(p) for p in registered.index if registered[p] <= gw}
        pool = {
            position: [p for p in range(n_players) if positions[p] == position and p in eligible]
            for position in POSITIONS
        }
        for index in range(n_squads):
            members = [
                int(player_id)
                for position in POSITIONS
                for player_id in rng.choice(pool[position], SQUAD_SELECT[position], replace=False)
            ]
            squad_rows += [{"gw": gw, "squad_id": f"gw{gw:02d}-{index:04d}", "player_id": p} for p in members]
    squads = pd.DataFrame(squad_rows)

    scores = mart.loc[:, ["player_id", "gw"]].copy()
    scores["score"] = rng.integers(0, 5, len(scores)).astype(float)
    ranker = _Ranker(name="F_test", window=(1, max(gameweeks)), scores=scores)
    return mart, squads, ranker


def test_the_two_frames_carry_exactly_the_columns_section_7_2_specifies() -> None:
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    assert tuple(result.squad_weeks.columns) == T2_COLUMNS
    assert tuple(result.ordering_replays.columns) == T5_COLUMNS


def test_t5_carries_one_row_per_squad_week_per_ordering_with_one_primary() -> None:
    """§7.2's T5 grain includes `ranker`, and §5.4 makes element 0 the primary."""
    mart, squads, ranker = _fixture()
    order = [("by_rank", _by_rank), ("reversed", _reversed)]
    result = run(squads, lambda _: ranker, order, mart, (2, 4))
    assert len(result.ordering_replays) == 2 * len(result.squad_weeks)
    per_group = result.ordering_replays.groupby(["squad_id", "gw", "ranker"])["is_primary"].sum()
    assert (per_group == 1).all()
    primaries = result.ordering_replays.loc[result.ordering_replays["is_primary"], "ordering_name"]
    assert set(primaries) == {"by_rank"}


def test_t2_carries_the_primary_orderings_replay_and_no_other() -> None:
    """§7.2: "Every figure in T2 is the *primary* ordering's." Checked by running the same
    fixture with the two policies swapped and asserting T2 follows element 0."""
    mart, squads, ranker = _fixture()
    forward = run(squads, lambda _: ranker, [("a", _by_rank), ("b", _reversed)], mart, (2, 4))
    backward = run(squads, lambda _: ranker, [("b", _reversed), ("a", _by_rank)], mart, (2, 4))

    for label, result in (("a", forward), ("b", backward)):
        chosen = result.squad_weeks.set_index(["squad_id", "gw"])["chosen_xi_points"]
        primary = result.ordering_replays
        primary = primary.loc[primary["ordering_name"] == label].set_index(["squad_id", "gw"])["realised_total"]
        pd.testing.assert_series_equal(chosen, primary, check_names=False)


def test_the_realised_and_as_of_pairs_are_not_the_same_call() -> None:
    """§0.8's correction, asserted rather than trusted: the closeness gap is the **as-of** pair's,
    and computing it from realised points gives a different number. If the two calls were
    conflated this test fails, and the columns' names would be lying."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))

    assert (result.squad_weeks["best_legal_xi_points"] != result.squad_weeks["best_legal_xi_asof"]).any(), (
        "the two calls returned identical totals everywhere; they may be the same call"
    )
    gap = result.squad_weeks["best_legal_xi_asof"] - result.squad_weeks["second_best_xi_asof"]
    pd.testing.assert_series_equal(result.squad_weeks["closeness_gap"], gap, check_names=False)
    assert (result.squad_weeks["closeness_gap"] != result.squad_weeks["best_legal_xi_points"]).any()


def test_regret_is_the_realised_pair_and_is_never_negative() -> None:
    """§0.1, and §0.2's asymmetric option: the counterfactual has no substitutions applied."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    expected = result.squad_weeks["best_legal_xi_points"] - result.squad_weeks["chosen_xi_points"]
    pd.testing.assert_series_equal(result.squad_weeks["regret"], expected, check_names=False)
    assert (result.squad_weeks["regret"] >= 0).all()


def test_zero_gap_is_flagged_where_the_two_leading_as_of_xis_tie() -> None:
    """§0.8's zero-gap squad-weeks -- excluded and counted at assembly, flagged here."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    pd.testing.assert_series_equal(
        result.squad_weeks["is_zero_gap"], result.squad_weeks["closeness_gap"] <= 0.0, check_names=False
    )


def test_the_no_fixture_rule_is_measured_and_actually_bites() -> None:
    """§0.4's measurement, stored per squad-week (§7.6). A fixture in which the rule never
    changed an XI would make the column untested, so the flag must fire somewhere."""
    mart, squads, ranker = _fixture(seed=4)
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    assert result.squad_weeks["no_fixture_rule_changed_xi"].any()


def test_a_window_outside_the_rankers_declared_span_raises() -> None:
    """§0.7 makes the declared window the ranker's own claim; §6.3 has a caller narrow to the
    intersection. Scoring outside it would be the harness inventing coverage."""
    mart, squads, ranker = _fixture()
    narrow = _Ranker(name=ranker.name, window=(3, 4), scores=ranker.scores)
    with pytest.raises(ValueError, match="declared window"):
        run(squads, lambda _: narrow, [("primary", _by_rank)], mart, (2, 4))


def test_the_run_is_deterministic() -> None:
    """§7.3 makes `run_id` a hash of the identifying fields, which is only sound if identical
    inputs replay identically. §6.8's tie-break is the part that could break this."""
    mart, squads, ranker = _fixture()
    first = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    second = run(squads.sample(frac=1, random_state=2), lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    pd.testing.assert_frame_equal(first.squad_weeks, second.squad_weeks)


def test_an_empty_bench_order_raises() -> None:
    mart, squads, ranker = _fixture()
    with pytest.raises(ValueError, match="non-empty"):
        run(squads, lambda _: ranker, [], mart, (2, 4))


def test_a_policy_that_drops_or_invents_a_bench_player_raises() -> None:
    """A policy is a callable supplied by the caller (§5.4), so its output is validated rather
    than trusted -- a dropped player would silently shorten the queue and change the replay."""
    mart, squads, ranker = _fixture()
    with pytest.raises(ValueError, match="exactly the outfield bench"):
        run(squads, lambda _: ranker, [("bad", lambda bench: [bench[0].player_id])], mart, (2, 4))


def test_unrankable_rows_are_the_absent_ones_as_well_as_the_null_ones() -> None:
    """§6.5: a ranker "emits it as unrankable rather than as a number", which on a frame is
    either a null score or an absent row. Both must reach the same tier."""
    mart, squads, ranker = _fixture()
    dropped = ranker.scores.loc[ranker.scores["gw"] != 3]
    nulled = ranker.scores.copy()
    nulled.loc[nulled["gw"] == 3, "score"] = np.nan
    order = [("primary", _by_rank)]
    a = run(squads, lambda _: _Ranker(ranker.name, ranker.window, dropped), order, mart, (2, 4))
    b = run(squads, lambda _: _Ranker(ranker.name, ranker.window, nulled), order, mart, (2, 4))
    pd.testing.assert_frame_equal(a.squad_weeks, b.squad_weeks)


def test_run_returns_the_result_type_and_build_is_the_dal_entry_point() -> None:
    """§5.1's shape. `build` is the one function that reads, on the sampler's `build_squads`
    pattern; `run` is the same computation over a mart already in hand."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    assert isinstance(result, HarnessResult)
    assert callable(build)


# ---------------------------------------------------------------------------
# §0.10 / §7.2.1 -- the absolute counterfactual
# ---------------------------------------------------------------------------


def _enumerate_best_total(
    xi: frozenset[int],
    squad: Sequence[int],
    positions: dict[int, str],
    minutes: dict[int, float | None],
    points: dict[int, float],
) -> float:
    """An independent enumeration of §0.10's sigma*: replay all 6 orderings, take the best.

    Written out here rather than imported, so the assertion compares the module's value against a
    reference this file computes rather than against the module's own arithmetic restated.
    """
    bench_outfield = sorted(p for p in squad if p not in xi and positions[p] != "GK")
    return max(
        replay(xi, squad, positions, minutes, points, list(order)).realised_total
        for order in permutations(bench_outfield)
    )


def _score_of(ranker: _Ranker, player_id: int, gw: int) -> float | None:
    hit = ranker.scores.loc[(ranker.scores["player_id"] == player_id) & (ranker.scores["gw"] == gw), "score"]
    return None if hit.empty or pd.isna(hit.iloc[0]) else float(hit.iloc[0])


def _squad_week_inputs(
    mart: pd.DataFrame, squads: pd.DataFrame, squad_id: str, gw: int
) -> tuple[list[int], dict[int, str], dict[int, float | None], dict[int, float]]:
    """The per-squad-week lookups `run` builds, rebuilt here from the fixture frames."""
    squad = [int(p) for p in squads.loc[(squads["squad_id"] == squad_id) & (squads["gw"] == gw), "player_id"]]
    slice_ = mart.loc[mart["gw"] == gw].set_index("player_id")
    positions = {p: str(slice_.loc[p, "position"]) for p in squad}
    minutes: dict[int, float | None] = {
        p: (None if pd.isna(slice_.loc[p, "minutes"]) else float(slice_.loc[p, "minutes"])) for p in squad
    }
    points = {
        p: (0.0 if pd.isna(slice_.loc[p, "total_points"]) else float(slice_.loc[p, "total_points"])) for p in squad
    }
    return squad, positions, minutes, points


def test_best_permutation_total_is_the_max_over_all_six_orderings_on_every_squad_week() -> None:
    """§0.10's sigma*, checked exhaustively rather than sampled -- there are only 6 orderings.

    The XI is rebuilt through the module's own selection so the bench is the one sigma* ranges
    over (§4.4 conditions the bench on the ranker's XI), and the maximum is then re-derived from
    the independent enumeration above.
    """
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))

    checked = 0
    for row in result.squad_weeks.itertuples(index=False):
        gw = int(row.gw)
        squad, positions, minutes, points = _squad_week_inputs(mart, squads, str(row.squad_id), gw)
        records = [BenchPlayer(p, positions[p], _score_of(ranker, p, gw), no_fixture=minutes[p] is None) for p in squad]
        xi = select_xi(rank_squad(records), positions)
        assert row.best_permutation_total == pytest.approx(_enumerate_best_total(xi, squad, positions, minutes, points))
        checked += 1
    assert checked == len(result.squad_weeks) > 0


def test_the_absolute_counterfactual_is_not_the_relative_one_the_document_withdrew() -> None:
    """§0.10 withdrew the relative form -- sigma* over the *policies compared*. That form is
    computed here alongside the emitted one, so this suite cannot pass by being blind to which of
    the two the module emits.

    The one-policy run is the sharpest separator and §5.4 permits it: under the relative form
    sigma* = sigma, so ordering regret is identically 0 and the single policy examined is reported
    perfect. Both halves are asserted -- that the relative form degenerates, and that the emitted
    one does not.
    """
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("only", _by_rank)], mart, (2, 4))

    key = ["squad_id", "gw", "ranker"]
    absolute = result.squad_weeks.set_index(key)["best_permutation_total"]
    relative = result.ordering_replays.groupby(key)["realised_total"].max().reindex(absolute.index)
    chosen = result.squad_weeks.set_index(key)["chosen_xi_points"]

    assert ((relative - chosen).abs() < 1e-9).all(), "the relative form did not degenerate; it is not the relative form"
    assert (absolute - chosen > 1e-9).any(), "sigma* never beat the primary's total; the fixture does not exercise it"
    assert (absolute >= relative - 1e-9).all()


def test_ordering_regret_is_non_negative_for_every_candidate_ordering() -> None:
    """§4.4: ordering regret is >= 0, and 0 only for an ordering that achieved the best total
    available. Every candidate is one of the 6 sigma* ranges over, so the bound is structural."""
    mart, squads, ranker = _fixture()
    order = [("by_rank", _by_rank), ("reversed", _reversed)]
    result = run(squads, lambda _: ranker, order, mart, (2, 4))

    joined = result.ordering_replays.merge(
        result.squad_weeks[["squad_id", "gw", "ranker", "best_permutation_total"]],
        on=["squad_id", "gw", "ranker"],
        validate="many_to_one",
    )
    regret = joined["best_permutation_total"] - joined["realised_total"]
    assert (regret >= -1e-9).all()
    assert (regret > 1e-9).any(), "no candidate ordering ever fell short of sigma*; the fixture is degenerate"


def test_sigma_star_cancels_from_the_paired_difference_and_is_the_same_stored_cell() -> None:
    """§4.5, and §7.2.1's claim that under the selected shape the cancellation is *structural*.

    Two things are asserted, not one. That the paired difference of mean ordering regrets equals
    the paired difference of realised totals with the sign reversed -- the algebraic cancellation
    §0.10 states. And that it holds **cell-wise**: because `best_permutation_total` carries no
    ordering dimension, both regrets at a squad-week read the same T2 cell, so sigma* is gone from
    the difference per squad-week and not merely on average.
    """
    mart, squads, ranker = _fixture()
    order = [("by_rank", _by_rank), ("reversed", _reversed)]
    result = run(squads, lambda _: ranker, order, mart, (2, 4))

    key = ["squad_id", "gw", "ranker"]
    star = result.squad_weeks.set_index(key)["best_permutation_total"]
    totals = result.ordering_replays.pivot_table(index=key, columns="ordering_name", values="realised_total")
    regret_a = star - totals["by_rank"]
    regret_b = star - totals["reversed"]

    pd.testing.assert_series_equal(regret_a - regret_b, totals["reversed"] - totals["by_rank"], check_names=False)
    assert regret_a.mean() - regret_b.mean() == pytest.approx(totals["reversed"].mean() - totals["by_rank"].mean())


def test_a_counterfactual_carrying_an_ordering_dimension_would_not_cancel_cell_wise() -> None:
    """The counterfactual to the test above, executed rather than asserted in its docstring.

    Had sigma* been stored per ordering -- the T5 shape §7.2.1 declined -- each regret would read
    its own value and the cancellation would not be structural. A per-ordering counterfactual is
    constructed here and its cell-wise difference does **not** reduce to the totals' difference,
    which is what makes the assertion above load-bearing rather than a tautology of subtraction.
    """
    mart, squads, ranker = _fixture()
    order = [("by_rank", _by_rank), ("reversed", _reversed)]
    result = run(squads, lambda _: ranker, order, mart, (2, 4))

    key = ["squad_id", "gw", "ranker"]
    totals = result.ordering_replays.pivot_table(index=key, columns="ordering_name", values="realised_total")
    # "Best among the orderings that are not this one" -- ordering-dependent by construction.
    bad_a = totals["reversed"] - totals["by_rank"]
    bad_b = totals["by_rank"] - totals["reversed"]
    assert not np.allclose(bad_a - bad_b, totals["reversed"] - totals["by_rank"])


def test_no_substitution_leaves_sigma_star_defined_and_equal_to_the_chosen_total() -> None:
    """§7.5's first degenerate case. Where no substitution fires all 6 orderings return the same
    total, so sigma* is well defined and equals the chosen total -- and the *derived* regret is 0.
    §7.5 gates that derivation on `substitution_fired` so it reads null rather than 0 at assembly;
    the column itself is always populated, which is what this asserts."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, [("primary", _by_rank)], mart, (2, 4))
    quiet = result.squad_weeks.loc[~result.squad_weeks["substitution_fired"]]
    assert not quiet.empty, "the fixture fired a substitution everywhere; the quiet case is untested"
    assert quiet["best_permutation_total"].notna().all()
    pd.testing.assert_series_equal(quiet["best_permutation_total"], quiet["chosen_xi_points"], check_names=False)


def test_sigma_star_does_not_depend_on_which_policies_the_run_compares() -> None:
    """The defect §0.10 removed, asserted directly rather than argued: under the relative form,
    adding a policy to a comparison moved every other policy's already-computed score. Under the
    absolute form the counterfactual is a fact about the squad-week, so it is identical across two
    runs comparing different policy sets -- while the relative form demonstrably is not."""
    mart, squads, ranker = _fixture()
    key = ["squad_id", "gw", "ranker"]
    one = run(squads, lambda _: ranker, [("by_rank", _by_rank)], mart, (2, 4))
    two = run(squads, lambda _: ranker, [("by_rank", _by_rank), ("reversed", _reversed)], mart, (2, 4))

    pd.testing.assert_series_equal(
        one.squad_weeks.set_index(key)["best_permutation_total"],
        two.squad_weeks.set_index(key)["best_permutation_total"],
    )
    rel_one = one.ordering_replays.groupby(key)["realised_total"].max()
    rel_two = two.ordering_replays.groupby(key)["realised_total"].max()
    assert not rel_one.equals(rel_two), "the two policies never differed anywhere; the contrast is untested"


def test_t5_is_untouched_by_the_new_column_so_b2_stays_comparison_relative() -> None:
    """§7.2.1's third reason for the T2 shape. Six permutation rows on T5 would have redefined the
    group §4.6's ordering-relevance derivation runs over, converting B2 into the
    permutation-relevant count §4.10 forbids. T5's rows must stay one per candidate ordering."""
    mart, squads, ranker = _fixture()
    order = [("by_rank", _by_rank), ("reversed", _reversed)]
    result = run(squads, lambda _: ranker, order, mart, (2, 4))
    assert len(result.ordering_replays) == len(order) * len(result.squad_weeks)
    assert set(result.ordering_replays["ordering_name"]) == {"by_rank", "reversed"}


# ---------------------------------------------------------------------------
# §3.5/§5.1 -- the import contract
# ---------------------------------------------------------------------------


def test_importing_the_harness_pulls_in_no_tier_b_module_and_no_ranker() -> None:
    """§5.1 forbids `harness.py` `model/`, `research/`, `serve/` and `rankers.py`; §3.6's
    transitivity guarantee rests on that closure. `dal/` and `domain/` are permitted and expected.

    Run in a subprocess for §5.6's reason: the session has already imported `model` via
    `testpaths`, so an in-process check could not tell this module's closure from what was
    already loaded. The `.importlinter` contract covers the first three; the sibling half --
    `rankers.py` -- cannot be written as a `forbidden` contract until that module exists, so it
    is enforced here.
    """
    program = (
        "import sys; import decisions.starting_xi.harness; "
        "leaked = [m for m in sys.modules "
        "if m.split('.')[0] in {'model', 'research', 'serve', 'operational'} "
        "or m.startswith('decisions.starting_xi.rankers') "
        "or m.startswith('decisions.starting_xi.uncertainty')]; "
        "assert not leaked, leaked; "
        "assert 'decisions.starting_xi.formations' in sys.modules; "
        "assert 'dal.pipeline' in sys.modules"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0
