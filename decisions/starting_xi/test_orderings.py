"""What this suite has to establish, beyond that the module imports.

`orderings.py` holds one policy and one tuple, so the risk is not that the code is wrong -- it is
that a claim made *about* it in prose is untrue and nothing notices. Three such claims are
executed rather than described:

* **"Calling `rank_squad` is equivalent to returning the harness's argument untouched."** The
  module derives the order instead of trusting the argument's, and justifies that by a claim the
  two agree. Both are run through `harness.run` over the same fixture and every replay compared.
* **"A function of the records alone."** The property is only worth having if it is real, so the
  policy's input is permuted -- exhaustively, all 3! of them -- and the output asserted invariant.
* **"Tier A, and the tier is forced."** Asserted as an import closure in a subprocess, for §5.6's
  reason: this session has already imported `model` via `testpaths`, so an in-process `sys.modules`
  check could not tell this module's closure from what was already loaded.

And the contract §5.4 states, since the composition root is what consumes it: the set is non-empty,
its names are unique, element 0 is the primary, and `harness.run` accepts it as it stands.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import permutations

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi.harness import BenchPlayer, registration_gw, run
from decisions.starting_xi.orderings import BY_RANK, PRE_REGISTERED_ORDERINGS, order_by_rank
from domain.fpl_squad import POSITIONS, SQUAD_SELECT

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Ranker:
    """A stand-in for §6.1's `RankerOutput`, satisfying the protocol structurally."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _identity(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """The argument untouched -- what §5.4 would let a caller pass instead of a named policy.

    Kept in the tests and not in the module: it is the thing `order_by_rank` is asserted equal to,
    not a second pre-registered ordering.
    """
    return tuple(record.player_id for record in bench)


def _fixture(
    n_squads: int = 4, gameweeks: Sequence[int] = (2, 3, 4), seed: int = 3
) -> tuple[pd.DataFrame, pd.DataFrame, _Ranker]:
    """A small mart, squad table and ranker, built together so the ids line up.

    Blanks and no-fixture rows are drawn at a rate that makes substitutions fire, since an
    ordering that is never consumed would let the equivalence test pass vacuously.
    """
    rng = np.random.default_rng(seed)
    n_players = 60
    positions = [p for p in POSITIONS for _ in range(SQUAD_SELECT[p] * 4)]
    rows: list[tuple[int, int, str, float | None, float | None]] = []
    for player_id in range(n_players):
        for gw in range(1, max(gameweeks) + 1):
            draw = rng.random()
            if draw < 0.1:
                rows.append((player_id, gw, positions[player_id], None, None))
            elif draw < 0.3:
                rows.append((player_id, gw, positions[player_id], 0.0, 0.0))
            else:
                rows.append((player_id, gw, positions[player_id], 90.0, float(rng.integers(0, 16))))
    mart = pd.DataFrame(rows, columns=["player_id", "gw", "position", "minutes", "total_points"]).astype(
        {"minutes": "Float64", "total_points": "Float64"}
    )

    # §2.1's registration predicate, applied when drawing: the sampler builds the universe before
    # drawing, so a squad never names a player who has not yet registered.
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
    return mart, squads, _Ranker(name="F_test", window=(1, max(gameweeks)), scores=scores)


# ---------------------------------------------------------------------------
# The claims the module's prose makes (§5.4.1)
# ---------------------------------------------------------------------------


def test_ordering_by_rank_agrees_with_the_bench_the_harness_hands_it() -> None:
    """The module derives the order rather than returning its argument, and says the two agree.

    Asserted on **every bench `harness.run` actually passes** -- §4.12's induced order over the
    non-selected outfield players -- rather than through the replays those benches produce. The
    replay route was tried and is vacuous: two different orderings frequently bring on the same
    player, so a policy sorting by `player_id` produces replay records identical to this one's
    across a whole fixture. The claim is about the ordering, so the ordering is what is compared.
    """
    mart, squads, ranker = _fixture()
    seen: list[tuple[BenchPlayer, ...]] = []

    def spy(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
        seen.append(tuple(bench))
        return _identity(bench)

    run(squads, lambda _: ranker, [("spy", spy)], mart, (2, 4))

    assert seen, "the harness never called a policy; there is nothing to compare"
    for bench in seen:
        assert order_by_rank(bench) == _identity(bench), bench


def test_the_equivalence_is_not_vacuous() -> None:
    """Two ways it could be, and both are ruled out.

    The ordering must be **consumed** -- an ordering no substitution ever reaches would make the
    comparison above true of any policy at all. And it must be a **real** ordering: if every bench
    happened to arrive in ascending `player_id` order, agreeing with it would say nothing about
    §6.7's tiers or §6.8's tie-break, since the identity and a bare id-sort would coincide.
    """
    mart, squads, ranker = _fixture()
    seen: list[tuple[BenchPlayer, ...]] = []

    def spy(bench: Sequence[BenchPlayer]) -> tuple[int, ...]:
        seen.append(tuple(bench))
        return _identity(bench)

    result = run(squads, lambda _: ranker, [("spy", spy)], mart, (2, 4))

    assert result.squad_weeks["substitution_fired"].sum() > 0, "no substitution fired; the ordering was never live"
    by_id = [bench for bench in seen if _identity(bench) != tuple(sorted(r.player_id for r in bench))]
    assert by_id, "every bench arrived in ascending player_id order; the induced order is untested"


def test_the_policy_is_a_function_of_the_records_and_not_of_their_order() -> None:
    """§6.7's tiers and §6.8's tie-break make the ranking a total order on records, so every
    permutation of one bench must give one answer. Swept exhaustively over 3! inputs."""
    bench = (
        BenchPlayer(player_id=7, position="MID", score=2.0, no_fixture=False),
        BenchPlayer(player_id=3, position="DEF", score=None, no_fixture=False),
        BenchPlayer(player_id=9, position="FWD", score=5.0, no_fixture=True),
    )
    answers = {order_by_rank(list(candidate)) for candidate in permutations(bench)}
    assert answers == {(7, 3, 9)}, answers


def test_equal_scores_break_on_ascending_player_id_and_not_on_arrival_order() -> None:
    """§6.8's direction, asserted rather than inherited: a tie-break that reversed, or that took
    the argument's order, would give (9, 3) here and the wrong version is computed to prove it."""
    bench = [
        BenchPlayer(player_id=9, position="MID", score=4.0, no_fixture=False),
        BenchPlayer(player_id=3, position="MID", score=4.0, no_fixture=False),
    ]
    assert order_by_rank(bench) == (3, 9)
    assert _identity(bench) == (9, 3), "the fixture no longer separates the two rules"


# ---------------------------------------------------------------------------
# The contract the composition root consumes (§5.4, §5.4.1, §7.3)
# ---------------------------------------------------------------------------


def test_the_pre_registered_set_satisfies_section_5_4s_contract() -> None:
    """Non-empty, uniquely named, element 0 primary. §7.3 makes the whole ordered set run
    identity, so the *order* is asserted and not only the membership."""
    names = [name for name, _ in PRE_REGISTERED_ORDERINGS]
    assert names, "bench_order must be non-empty (DESIGN.md §5.4)"
    assert len(set(names)) == len(names), names
    assert names[0] == BY_RANK


def test_the_pre_registered_set_is_what_it_is_frozen_as() -> None:
    """§5.4.1 pre-registers exactly one policy and §7.4 freezes it. A second policy added without
    a `METRIC.md` pass characterising the comparison set fails here, which is the point: the set
    is a pre-registration, not a convenience list."""
    assert [name for name, _ in PRE_REGISTERED_ORDERINGS] == [BY_RANK]


def test_the_harness_accepts_the_pre_registered_set_unmodified() -> None:
    """The composition root passes this tuple straight through, so the acceptance is asserted here
    rather than left for the root to discover."""
    mart, squads, ranker = _fixture()
    result = run(squads, lambda _: ranker, PRE_REGISTERED_ORDERINGS, mart, (2, 4))
    assert len(result.ordering_replays) == len(result.squad_weeks)
    assert result.ordering_replays["is_primary"].all()
    assert set(result.ordering_replays["ordering_name"]) == {BY_RANK}


# ---------------------------------------------------------------------------
# The tier (§3.3, §5.1, §5.6)
# ---------------------------------------------------------------------------


def test_importing_the_orderings_pulls_in_no_downstream_layer_and_no_tier_b_module() -> None:
    """§5.1 forbids a Tier A module `model/`, `research/`, `serve/` and both Tier B siblings.

    `.importlinter` covers all of it; this asserts the runtime closure as well, because §5.6
    records that a re-export in a parent `__init__.py` would break the closure while every
    contract still passed. `harness.py` is expected: it is where §5.4's policy type lives, and
    that edge is why this module is Tier A rather than Tier B.
    """
    program = (
        "import sys; import decisions.starting_xi.orderings; "
        "leaked = [m for m in sys.modules "
        "if m.split('.')[0] in {'model', 'research', 'serve', 'operational'} "
        "or m.startswith('decisions.starting_xi.rankers') "
        "or m.startswith('decisions.starting_xi.uncertainty')]; "
        "assert not leaked, leaked; "
        "assert 'decisions.starting_xi.harness' in sys.modules"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0
