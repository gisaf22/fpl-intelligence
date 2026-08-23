"""The replay engine -- `DESIGN.md` §5.1, §4.3, §6.7.

One squad-week at a time, and four things per squad-week:

* **The chosen XI** -- §6.7's score-maximising legal XI over the ranker's panel, with §0.4's
  no-fixture demotion and §6.5's unrankable demotion applied by the harness and §6.8's
  `player_id` tie-break making the ranking strict.
* **The replay** -- §4.3's vacancy loop, once per candidate ordering, against that one fixed XI
  (§4.4). Element 0 of `bench_order` is the primary and is the only one T2 carries (§5.4, §7.2).
* **Regret** -- §0.1's counterfactual, on **realised** points, with no substitutions applied to
  the counterfactual side (§0.2's asymmetric option).
* **§0.10's absolute bench-order counterfactual** -- `best_permutation_total`, the best realised
  total over all 3! = 6 orderings of the outfield bench against that same fixed XI. It has no
  ordering dimension, so §7.2.1 stores it as a T2 column and not as rows on T5, and §4.4's
  ordering regret is derived from it by joining T2 to T5 on (squad, gw, ranker).
* **C1's closeness gap** -- §0.8's XI gap, on the **as-of** statistic §0.9 fixes, over §8.3's
  population. Not the same numbers, and not the same call.

**`best_legal_xi` is called twice per squad-week, and the two calls are not interchangeable.**
§0.8 records why: §0.1's regret needs the best legal XI on realised points, while C1 needs the
best *and* second-best on a statistic known before the outcome. Only the realised call's first
total is used, and only the as-of call's pair. §7.2's T2 keeps them in two named pairs --
`best_legal_xi_points` against `best_legal_xi_asof`/`second_best_xi_asof` -- because a single
runner-up column is what invited the conflation in the first place.

**Import closure: `dal/`, `domain/`, `formations.py`, stdlib, numpy, pandas.** Tier A (§3.5), so
no `model/`, no `research/`, no `serve/`, and **never `rankers.py`** -- the harness receives a
ranking function and a bench-ordering policy set as arguments (§3.2, §5.4). That single absent
edge is what makes §3.6's transitivity guarantee hold: every module this one reaches terminates
in `dal/` or `domain/`, both already fenced by `.importlinter`.

**The ranker is consumed structurally, not by import.** `RankerOutput` below is a `Protocol`
rather than a shared base class: `rankers.py` is Tier B and §5.1 forbids it every Tier A module,
so it cannot import a dataclass defined here, and a common base would have to live in a third
module that both may import. Structural typing needs no such module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Final, Protocol, SupportsFloat, cast, runtime_checkable

import numpy as np
import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load
from decisions.starting_xi.formations import LEGAL_FORMATIONS, best_legal_xi, is_legal_xi
from domain.fpl_squad import POSITIONS, SQUAD_SIZE, XI_MIN_PLAY, XI_SIZE

# ---------------------------------------------------------------------------
# Ranking tiers (§6.7)
# ---------------------------------------------------------------------------

# The three ranking tiers, best first. §6.7 fixes the order and the reason: a scored player
# outranks an unrankable one (§6.5), and an unrankable one outranks a no-fixture one (§0.4).
# Reversing the last two would let one ranker's own coverage hole decide a selection wherever a
# formation minimum forces a demoted player in, which is the asymmetry §0.4 removes.
_TIER_SCORED: Final[int] = 0
_TIER_UNRANKABLE: Final[int] = 1
_TIER_NO_FIXTURE: Final[int] = 2

_MART_COLUMNS: Final[tuple[str, ...]] = ("player_id", "gw", "position", "minutes", "total_points")


# ---------------------------------------------------------------------------
# The interfaces the harness is handed (§5.1, §5.4, §6.1)
# ---------------------------------------------------------------------------


@runtime_checkable
class RankerOutput(Protocol):
    """§6.1's panel-producing ranker output, as a structural type.

    `window` is the ranker's **declared** span, inclusive; §0.7 has the harness consume it rather
    than infer it. `scores` is a frame of (`player_id`, `gw`, `score`), higher = more preferred.
    A row a ranker cannot score inside its own window is emitted as unrankable -- either absent
    from the frame or carrying a null `score` -- rather than as a number (§6.5).
    """

    @property
    def name(self) -> str: ...

    @property
    def window(self) -> tuple[int, int]: ...

    @property
    def scores(self) -> pd.DataFrame: ...


RankFn = Callable[[pd.DataFrame], RankerOutput]
"""§6.1's `rank(mart) -> RankerOutput`. Called **once per run**, over the whole mart."""


@dataclass(frozen=True)
class BenchPlayer:
    """One bench player, as an ordering policy sees him.

    §5.4 sketches the policy signature as `(bench_outfield, scores) -> ordered list`. It is
    narrowed here to a single argument, because the two halves of that sketch carry the same
    information: a policy may only order the players it is given, so a separate score mapping is
    either a copy of `score` below or a channel for scores of players who are not on the bench.
    The narrowing is an interface detail rather than a change of substance -- a policy still sees
    each bench player's score, his position and whether his club has a fixture, and nothing else.

    `score` is `None` for an unrankable row (§6.5). `no_fixture` is §0.4's flag, carried so a
    policy can see it rather than having to infer it from a null.
    """

    player_id: int
    position: str
    score: float | None
    no_fixture: bool


OrderingPolicy = Callable[[Sequence[BenchPlayer]], Sequence[int]]
"""`(bench_outfield) -> the 3 outfield bench players' ids, in priority order` (§5.4).

The GK slot takes no policy: with exactly one bench goalkeeper the ordering is degenerate and no
policy can differ from another on it (§4.2).
"""

BenchOrder = Sequence[tuple[str, OrderingPolicy]]
"""§5.4's required argument: a non-empty ordered sequence of named policies, element 0 primary."""


@dataclass(frozen=True)
class HarnessResult:
    """What §5.1 has the harness return: two frames, at the two grains §7.1 fixes.

    `squad_weeks` is §7.2's T2, one row per (squad, gameweek, ranker), carrying the **primary**
    ordering's replay and no other -- plus the two counterfactual columns, `best_legal_xi_points`
    and `best_permutation_total`, which are properties of the squad-week rather than of any
    ordering (§7.2, §7.2.1). `ordering_replays` is T5, one row per (squad, gameweek,
    ranker, ordering).

    Neither carries `run_id`: §7.3 makes that a hash of the run's identifying fields, which
    `results.py` owns. Ordering-relevance is **not** emitted -- §7.2.1 derives it at assembly,
    because relevance is a comparison *between* orderings and has no single-ordering home.

    §7.2's T1, at per-player grain, is **not** emitted: §5.1's harness row returns the
    per-squad-week and per-ordering records only and names no producer for T1. Flagged in
    `DESIGN.md`'s Provenance as a §5.1 gap rather than filled here.
    """

    squad_weeks: pd.DataFrame
    ordering_replays: pd.DataFrame


# ---------------------------------------------------------------------------
# The as-of statistic (§0.9, §8.3)
# ---------------------------------------------------------------------------


def registration_gw(mart: pd.DataFrame) -> pd.Series:
    """Per player, the first gameweek carrying a non-null `minutes` row.

    §8.3's population is "the full player-gameweek spine restricted to each player's
    post-registration window", and does not operationalise *registration*. The predicate used is
    the sampler's own (§2.1): a player is registered from his first non-null `minutes` row.
    Reusing it is what makes §8.3's coupling claim true -- the conditioning statistic and the
    squad universe read one population, not two that happen to look alike. `test_harness.py`
    asserts the two agree rather than leaving the reuse to the docstring.

    `INVENTORY.md` §2.5 records why the predicate is needed at all: the DAL spine is a full
    player x gameweek cartesian product, so a GW20 debutant *has* GW1-19 rows with NULL
    performance, and counting them would score the DAL's construction rather than the player.
    """
    played = mart.loc[mart["minutes"].notna(), ["player_id", "gw"]]
    return played.groupby("player_id")["gw"].min()


def as_of_points(mart: pd.DataFrame) -> pd.DataFrame:
    """§0.9's as-of statistic: season-to-date points per gameweek elapsed, strictly before `gw`.

    `METRIC.md` §3.2's first option, with §0.9's three sub-choices resolved: blanked weeks count
    at **0**, no-fixture weeks count at **0**, and pre-registration weeks **do not count at
    all**. The denominator is gameweeks elapsed since registration, not appearances -- §0.9
    records the failure of the alternative, which orders an 8-per-appearance player who features
    a third of the time above a nailed 4-per-week one.

    Returns:
        A frame of (`player_id`, `gw`, `as_of_points`), one row per post-registration
        player-gameweek. `gw` is the gameweek the statistic is used *at*; the window is
        `[registration_gw, gw)`, so the row at a player's own registration gameweek has an empty
        window.

    **The empty-denominator case is resolved here and is not settled upstream.** A player whose
    registration gameweek *is* the squad-week has no prior gameweek and no rate. §0.9 does not
    reach the case: it fixes what the denominator counts, not what happens when it counts
    nothing. The value used is **0**, on two grounds. It is the value §0.9 already assigns to
    every elapsed week that produced nothing, so a player with no history and one with an
    all-blank history are treated alike rather than differently. And the alternative -- dropping
    the squad-week -- would remove rows for a reason unrelated to closeness, which is the defect
    §0.8 rejects C2 for. Flagged rather than buried: it is a `DESIGN.md` §0.9 question this
    module answers locally because the build cannot proceed without an answer.
    """
    missing = [column for column in ("player_id", "gw", "minutes", "total_points") if column not in mart.columns]
    if missing:
        raise ValueError(f"mart is missing columns the as-of statistic reads: {missing}")

    first = registration_gw(mart)
    panel = mart.loc[:, ["player_id", "gw", "total_points"]].copy()
    panel["_first"] = panel["player_id"].map(first)
    panel = panel.loc[panel["_first"].notna() & (panel["gw"] >= panel["_first"])]
    panel = panel.sort_values(["player_id", "gw"], kind="stable")

    # §8.3's precondition, asserted at the call site because it is invisible there: a null left
    # in place would make every downstream mean skip it and produce an *appearance*-denominated
    # statistic -- the quantity §0.9 rejects, and one that would look entirely plausible.
    points = panel["total_points"].fillna(0).astype(float)
    if points.isna().any():  # pragma: no cover - fillna makes this unreachable; kept as the guard §8.3 requires
        raise AssertionError("total_points carries nulls after the fill; the as-of denominator would be appearances")

    grouped = points.groupby(panel["player_id"], sort=False)
    elapsed = grouped.cumcount().to_numpy()
    banked = (grouped.cumsum() - points).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        rate = np.where(elapsed > 0, banked / np.maximum(elapsed, 1), 0.0)

    return pd.DataFrame(
        {"player_id": panel["player_id"].to_numpy(), "gw": panel["gw"].to_numpy(), "as_of_points": rate}
    )


# ---------------------------------------------------------------------------
# Selection -- §6.7's Reading A
# ---------------------------------------------------------------------------


def rank_squad(players: Sequence[BenchPlayer]) -> tuple[int, ...]:
    """The strict ranking over a squad -- §6.7's three tiers, §6.8's tie-break.

    Args:
        players: the squad's players. Order is irrelevant; the ranking is a function of the
            records alone, which is what makes it independent of how the squad table was built.

    Returns:
        The `player_id`s, best first. Strict: no two players tie, because `player_id` is unique
        within a squad and breaks every remaining tie (§6.8).

    **Deterministic, and deliberately not a draw.** §6.8 fixes ascending `player_id` and states
    the requirement at the site: a tie-break drawn at run time -- even a seeded one -- would let
    two runs sharing a seed, a mart pin and a `run_id` select different XIs while every recorded
    field stayed identical. Nothing here consumes randomness and no seed reaches it, §8.4's
    `seed = 0` included; that constant governs the resampling call sites and has no business in a
    selection rule.
    """
    return tuple(
        player.player_id
        for player in sorted(
            players,
            key=lambda p: (
                _TIER_NO_FIXTURE if p.no_fixture else (_TIER_SCORED if p.score is not None else _TIER_UNRANKABLE),
                -(p.score if p.score is not None else 0.0),
                p.player_id,
            ),
        )
    )


def select_xi(ranking: Sequence[int], positions: Mapping[int, str]) -> frozenset[int]:
    """§6.7's chosen XI: the legal XI maximising a value consistent with `ranking`.

    Reading A, over the same 8 prefix-sum combinations `formations.py` uses for realised points.
    §6.7 proves the alternative reading -- greedy down the ranking -- returns the same *total*,
    because the legal XIs are the bases of a matroid and greedy attains a maximum-weight basis;
    it also records that the two differ on **membership** under ties, which is why the reading is
    named rather than left to the implementation.

    Args:
        ranking: the squad's `player_id`s, best first, strict (`rank_squad`).
        positions: each player's position.

    Returns:
        The chosen 11 `player_id`s.

    **What is maximised is rank position, not the raw score** (§6.7). The two agree wherever no
    demotion applies and must not be conflated where one does: an unrankable row carries no score
    at all, and `METRIC.md` §2.3 records that a PPG-style ranker scores a no-fixture player at 0,
    which is not last. Rank positions are distinct, so the maximiser is unique -- and by §6.7's
    matroid argument the same XI maximises every weighting consistent with the ranking, the
    ranker's own scores among them.
    """
    if len(ranking) != SQUAD_SIZE:
        raise ValueError(f"expected a squad of {SQUAD_SIZE}, got {len(ranking)}")
    if len(set(ranking)) != SQUAD_SIZE:
        raise ValueError("ranking contains a duplicate player_id")

    # Rank position turned into a value: strictly decreasing, so a prefix over a position's own
    # players is that position's best n under the ranking. Any strictly decreasing function of
    # the position would do; this one keeps the arithmetic in small integers.
    value = {player_id: SQUAD_SIZE - index for index, player_id in enumerate(ranking)}
    by_position: dict[str, list[int]] = {position: [] for position in POSITIONS}
    for player_id in ranking:
        position = positions[player_id]
        if position not in by_position:
            raise ValueError(f"unrecognised position {position!r}; expected one of {POSITIONS} (DESIGN.md §8.4)")
        by_position[position].append(player_id)

    best_total: int | None = None
    best: tuple[int, ...] = ()
    for formation in LEGAL_FORMATIONS:
        if any(n > len(by_position[position]) for position, n in zip(POSITIONS, formation, strict=True)):
            continue
        picked = tuple(
            player_id
            for position, n in zip(POSITIONS, formation, strict=True)
            for player_id in by_position[position][:n]
        )
        total = sum(value[player_id] for player_id in picked)
        # Strict `>` resolves a formation tie to the lowest formation tuple, since
        # `LEGAL_FORMATIONS` is ascending -- the rule §6.7 names, and the one `formations.py`
        # already applies to its own maximum.
        if best_total is None or total > best_total:
            best_total, best = total, picked

    if best_total is None:  # pragma: no cover - the 2/5/5/3 quota admits all eight formations
        raise ValueError("no legal formation fits this squad")
    return frozenset(best)


# ---------------------------------------------------------------------------
# The replay -- §4.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Replay:
    """One ordering's replay of one squad-week (§4.3), as T5 stores it (§7.2)."""

    realised_total: float
    substitution_fired: bool
    uncovered_blank: bool
    entered_gk: int | None
    entered_outfield: tuple[int, ...]


def _featured(minutes: float | None) -> bool:
    """§0.3's two-state predicate: did the player record any minutes?

    Covers `minutes = 0` (had a fixture, did not feature) and `minutes` NULL (no fixture) alike,
    which `INVENTORY.md` §2.5 records as structurally distinct states on the mart. §0.5 applies
    the same predicate to an incoming substitute.
    """
    return minutes is not None and not pd.isna(minutes) and minutes > 0


def replay(
    xi: frozenset[int],
    squad: Sequence[int],
    positions: Mapping[int, str],
    minutes: Mapping[int, float | None],
    points: Mapping[int, float],
    outfield_order: Sequence[int],
) -> Replay:
    """§4.3's replay: an ordering becomes a realised total.

    Vacancies are processed **one at a time**, each filled before the next is considered, so
    every state §0.6's legality condition is evaluated against is a complete 11 (§4.3). The
    vacancy order is §4.3.1's: the vacancy whose position carries the most live slack first --
    slack being its count in the current XI minus its XI minimum, recomputed before each vacancy
    -- ties by DEF, then MID, then FWD, then ascending `player_id`.

    A skipped bench player **stays in the queue** for a later vacancy -- §0.6's priority-queue
    reading. A rule that consumed him would measure a different bench order (`METRIC.md` §2.5).

    Args:
        xi: the chosen XI's `player_id`s.
        squad: the 15.
        positions, minutes, points: per player. `points` is realised and already null-filled by
            the caller (see `_realised_points`).
        outfield_order: the 3 outfield bench players in priority order -- the ordering under test.

    Returns:
        A `Replay`. `uncovered_blank` is §4.6's third quantity: a starter recorded no minutes and
        **no** substitution fired for him, so the XI finished short. It is distinct from "no
        substitution fired" and §7.5 turns on the distinction.
    """
    if len(xi) != XI_SIZE:
        raise ValueError(f"expected an XI of {XI_SIZE}, got {len(xi)}")

    live = dict.fromkeys(sorted(xi), True)
    entered_gk: int | None = None
    entered_outfield: list[int] = []
    uncovered = False

    bench = [player_id for player_id in squad if player_id not in xi]

    # GK slot -- a separate process (§0.6), and degenerate: a 15 holds exactly 2 goalkeepers and
    # every legal formation starts exactly 1 (§4.2), so no ordering choice exists here and no
    # policy can differ from another on it.
    starting_gk = [player_id for player_id in xi if positions[player_id] == "GK"]
    bench_gk = [player_id for player_id in bench if positions[player_id] == "GK"]
    if starting_gk and not _featured(minutes[starting_gk[0]]):
        if bench_gk and _featured(minutes[bench_gk[0]]):
            del live[starting_gk[0]]
            live[bench_gk[0]] = True
            entered_gk = bench_gk[0]
        else:
            uncovered = True

    # Outfield slots. §4.3.1's vacancy order: slackest position first, recomputed each pass.
    # The final XI is **not** invariant to this order -- an unfilled vacancy drops the XI below a
    # positional minimum that can never be restored, which makes every vacancy behind it
    # unfillable. Deferring the tightest position is what avoids that, and §4.3.1 measures the
    # cost of the fixed DEF-first order this replaces at 143 points over 11,100 squad-weeks
    # against 2 for this rule. Slack reads positions only, never points, so the replay stays
    # mechanical rather than becoming a hindsight optimiser (§4.3.1).
    tie_rank = {position: index for index, position in enumerate(POSITIONS)}
    vacancies = [player_id for player_id in xi if positions[player_id] != "GK" and not _featured(minutes[player_id])]
    queue = list(outfield_order)

    while vacancies:
        slack = {
            position: sum(1 for player_id in live if positions[player_id] == position) - XI_MIN_PLAY[position]
            for position in POSITIONS
        }
        vacancy = min(
            vacancies,
            key=lambda player_id: (-slack[positions[player_id]], tie_rank[positions[player_id]], player_id),
        )
        vacancies.remove(vacancy)
        del live[vacancy]
        for candidate in queue:
            if not _featured(minutes[candidate]):
                continue  # §0.5: an incoming substitute must himself have featured.
            if is_legal_xi([positions[player_id] for player_id in [*live, candidate]]):
                live[candidate] = True
                queue.remove(candidate)
                entered_outfield.append(candidate)
                break
            # else: skipped, and REMAINS in the queue for a later vacancy (§0.6, §4.3).
        else:
            uncovered = True  # no candidate qualified; the XI finishes short.

    return Replay(
        realised_total=float(sum(points[player_id] for player_id in live)),
        substitution_fired=entered_gk is not None or bool(entered_outfield),
        uncovered_blank=uncovered,
        entered_gk=entered_gk,
        # Sorted so equality of the stored value is set equality: §7.2.1 derives
        # ordering-relevance by comparing these across policies, and §4.6 defines it on the
        # entering *sets*.
        entered_outfield=tuple(sorted(entered_outfield)),
    )


# ---------------------------------------------------------------------------
# The run (§5.1)
# ---------------------------------------------------------------------------


def _optional_float(value: object) -> float | None:
    """A nullable mart cell as a plain float, or `None`.

    `minutes` is nullable on the mart and its NULL state is load-bearing -- §0.3's trigger and
    §0.4's no-fixture rule both turn on it -- so it is narrowed rather than filled.
    """
    return None if value is None or pd.isna(value) else float(cast(SupportsFloat, value))


def _realised_points(value: object) -> float:
    """Realised points for one player-gameweek, nulls filled to 0.

    **This is a local resolution of something `DESIGN.md` fixes only for the as-of statistic.**
    §0.9 sets blanked and no-fixture weeks to 0 for the *conditioning* statistic and gives the
    reason -- "a player whose club had no fixture scored 0 for anyone who started him". Nothing
    states the same for realised points, and something must: `total_points` is nullable on the
    mart (`INVENTORY.md` §2.5) and `best_legal_xi` rejects a non-finite value rather than
    guessing at it. The same sentence is the answer, and the alternatives are worse -- a null
    propagated into the counterfactual maximum would make regret undefined for the whole
    squad-week, and excluding the squad-week would drop rows for a reason unrelated to closeness.
    Flagged rather than buried; it is a §0.1/§0.9 question answered locally.
    """
    return 0.0 if value is None or pd.isna(value) else float(cast(SupportsFloat, value))


def run(
    squads: pd.DataFrame,
    rank_fn: RankFn,
    bench_order: BenchOrder,
    mart: pd.DataFrame,
    window: tuple[int, int],
) -> HarnessResult:
    """Replay every squad-week in `window` under one ranker and every candidate ordering.

    Args:
        squads: the sampler's frozen squad table -- (`gw`, `squad_id`, `player_id`), 15 rows per
            squad, one `gw` per `squad_id` (§2.9).
        rank_fn: §6.1's `rank(mart) -> RankerOutput`. Called **once**, over the whole mart, not
            once per gameweek: §6.1 records that a per-gameweek signature would force `p_play`'s
            expanding walk-forward to re-run from the start of the season for every gameweek.
        bench_order: §5.4's required argument -- a non-empty ordered sequence of `(name, policy)`
            pairs, element 0 the **primary**. No default: §4.9 establishes that primary regret is
            not independent of bench order, so a defaulted ordering would emit a regret figure
            that could not be reconstructed from its stated inputs.
        mart: the mart across every gameweek in scope, read via `dal/` (`build` is the entry
            point that does the reading). The whole panel is needed, not the window's slice: the
            as-of statistic's denominator runs from each player's registration gameweek (§0.9).
        window: the comparison window, inclusive. §6.3 computes it from the declared windows of
            the rankers in a comparison; the harness consumes it and never infers it (§0.7).

    Returns:
        A `HarnessResult` -- T2 and T5 (§7.2).

    Raises:
        ValueError: on a malformed squad table, a squad that is not 15 players, a bench order
            that is empty, or a `window` the ranker's declared window does not cover.
    """
    if not bench_order:
        raise ValueError("bench_order must be non-empty; element 0 is the primary ordering (DESIGN.md §5.4)")
    names = [name for name, _ in bench_order]
    if len(set(names)) != len(names):
        raise ValueError(f"bench_order carries duplicate policy names: {names}")
    missing = [column for column in _MART_COLUMNS if column not in mart.columns]
    if missing:
        raise ValueError(f"mart is missing columns the harness reads: {missing}")

    first_gw, last_gw = int(window[0]), int(window[1])
    if first_gw > last_gw:
        raise ValueError(f"window is empty: {window}")

    output = rank_fn(mart)
    declared_first, declared_last = output.window
    if first_gw < declared_first or last_gw > declared_last:
        # §0.7 makes the declared window the ranker's own claim about where it can score. Scoring
        # outside it would be the harness inventing coverage the ranker did not declare, and
        # §6.3 exists precisely so a caller narrows the window instead.
        raise ValueError(
            f"comparison window {window} is not covered by {output.name}'s declared window "
            f"{output.window} (DESIGN.md §0.7, §6.3)"
        )

    scores = output.scores.loc[:, ["player_id", "gw", "score"]]
    score_lookup: dict[tuple[int, int], float] = {
        (int(player_id), int(gw)): float(score)
        for player_id, gw, score in scores.itertuples(index=False)
        if not pd.isna(score)
    }

    facts = mart.loc[:, list(_MART_COLUMNS)]
    # `minutes` keeps its NULL state (§0.3, §0.4); `total_points` is filled to 0 here, once, at
    # the boundary -- see `_realised_points` for why that fill is this module's to make.
    fact_lookup: dict[tuple[int, int], tuple[str, float | None, float]] = {
        (int(player_id), int(gw)): (str(position), _optional_float(minutes), _realised_points(points))
        for player_id, gw, position, minutes, points in facts.itertuples(index=False)
    }
    as_of_lookup: dict[tuple[int, int], float] = {
        (int(player_id), int(gw)): float(value) for player_id, gw, value in as_of_points(mart).itertuples(index=False)
    }

    in_window = squads.loc[(squads["gw"] >= first_gw) & (squads["gw"] <= last_gw)]
    squad_week_rows: list[dict[str, object]] = []
    replay_rows: list[dict[str, object]] = []

    for (squad_id, gw), block in in_window.groupby(["squad_id", "gw"], sort=True):
        gw = int(gw)
        squad = [int(player_id) for player_id in block["player_id"]]
        if len(squad) != SQUAD_SIZE:
            raise ValueError(f"squad {squad_id!r} at gw {gw} holds {len(squad)} players, expected {SQUAD_SIZE}")

        keys = [(player_id, gw) for player_id in squad]
        absent = [key for key in keys if key not in fact_lookup]
        if absent:
            raise ValueError(f"squad {squad_id!r} at gw {gw} names players absent from the mart: {absent}")

        positions = {player_id: fact_lookup[(player_id, gw)][0] for player_id in squad}
        minutes: dict[int, float | None] = {player_id: fact_lookup[(player_id, gw)][1] for player_id in squad}
        points = {player_id: fact_lookup[(player_id, gw)][2] for player_id in squad}
        # §0.4: a player whose club has no fixture is ranked last by the harness, identically for
        # every ranker. NULL `minutes` is that state on the mart, post-registration
        # (`INVENTORY.md` §2.5) -- and the squad universe excludes pre-registration rows by
        # construction (§2.1), so a NULL reaching here is a blank rather than a prefix.
        no_fixture = {player_id: minutes[player_id] is None for player_id in squad}

        records = [
            BenchPlayer(
                player_id=player_id,
                position=positions[player_id],
                score=score_lookup.get((player_id, gw)),
                no_fixture=bool(no_fixture[player_id]),
            )
            for player_id in squad
        ]
        ranking = rank_squad(records)
        xi = select_xi(ranking, positions)

        # §0.4's measurement, stored per squad-week (§7.6): would the XI have differed had the
        # rank-last rule not been applied? The counterfactual keeps §6.5's unrankable demotion,
        # which is the ranker's own, and drops only the harness's no-fixture one.
        without_rule = select_xi(
            rank_squad([BenchPlayer(r.player_id, r.position, r.score, no_fixture=False) for r in records]),
            positions,
        )

        bench_outfield = [record for record in records if record.player_id not in xi and record.position != "GK"]
        bench_by_rank = sorted(bench_outfield, key=lambda r: ranking.index(r.player_id))

        # §0.10's absolute counterfactual: the best realised total over **all 3! = 6 orderings** of
        # the outfield bench, against this same fixed XI, these same blanks and these same realised
        # points. It is a property of (squad, gw, ranker) and of no ordering, which is why §7.2.1
        # stores it as a T2 column rather than as rows on T5 -- six permutation rows would redefine
        # the group T5's ordering-relevance derivation runs over, turning §4.6's comparison-relative
        # B2 into the permutation-relevant count §4.10 forbids. Six replays, against the policy
        # count; §4.3.1 measured the same enumeration over all 11,100 squad-weeks in seconds.
        best_permutation_total = max(
            replay(xi, squad, positions, minutes, points, list(order)).realised_total
            for order in permutations(record.player_id for record in bench_outfield)
        )

        replays: dict[str, Replay] = {}
        for name, policy in bench_order:
            ordered = [int(player_id) for player_id in policy(bench_by_rank)]
            expected = {record.player_id for record in bench_outfield}
            if set(ordered) != expected or len(ordered) != len(expected):
                raise ValueError(
                    f"ordering policy {name!r} returned {ordered} for squad {squad_id!r} at gw {gw}; "
                    f"it must return exactly the outfield bench {sorted(expected)}, each once"
                )
            replays[name] = replay(xi, squad, positions, minutes, points, ordered)

        # §0.1's counterfactual, on realised points, with **no** substitutions applied to the
        # counterfactual side (§0.2's asymmetric option). Only the first total is used here.
        realised = best_legal_xi([positions[p] for p in squad], [points[p] for p in squad])
        # §0.8's C1, on the as-of statistic. A separate call over the same 15 with different
        # values; only this call's *pair* is used, and §7.2's T2 keeps them apart by name.
        asof = best_legal_xi([positions[p] for p in squad], [as_of_lookup[(p, gw)] for p in squad])

        primary = replays[names[0]]
        regret = realised.best_legal_xi_points - primary.realised_total
        if regret < -1e-9:
            # §0.1's lower bound. §0.6 requires every substitution preserve a legal formation
            # exactly so the chosen side stays inside the set the counterfactual maximises over;
            # a negative regret means that invariant broke, and it fails loudly rather than
            # being reported.
            raise AssertionError(
                f"regret {regret} < 0 at squad {squad_id!r} gw {gw}: the replayed XI out-scored its own "
                f"counterfactual, so it left the set the counterfactual maximises over (DESIGN.md §0.1, §0.6)"
            )

        beaten = [name for name, r in replays.items() if r.realised_total > best_permutation_total + 1e-9]
        if beaten:
            # Every candidate ordering is a permutation of the same outfield bench, so it is one of
            # the six the maximum ranges over and cannot exceed it. A breach means the policy
            # returned a bench the enumeration did not cover, which would make §4.4's ordering
            # regret negative -- the bound §0.1 holds for P1, mirrored.
            raise AssertionError(
                f"ordering(s) {beaten} out-scored the 6-permutation maximum at squad {squad_id!r} gw {gw}: "
                f"the candidate bench is not the bench sigma* ranges over (DESIGN.md §0.10, §4.4)"
            )

        closeness = asof.best_legal_xi_points - asof.second_best_xi_points
        squad_week_rows.append(
            {
                "squad_id": squad_id,
                "gw": gw,
                "ranker": output.name,
                "chosen_xi_points": primary.realised_total,
                "best_legal_xi_points": realised.best_legal_xi_points,
                "best_legal_xi_asof": asof.best_legal_xi_points,
                "second_best_xi_asof": asof.second_best_xi_points,
                "regret": max(regret, 0.0),
                "closeness_gap": closeness,
                "is_zero_gap": closeness <= 0.0,
                "substitution_fired": primary.substitution_fired,
                "uncovered_blank": primary.uncovered_blank,
                "no_fixture_rule_changed_xi": xi != without_rule,
                "best_permutation_total": best_permutation_total,
            }
        )
        replay_rows.extend(
            {
                "squad_id": squad_id,
                "gw": gw,
                "ranker": output.name,
                "ordering_name": name,
                "is_primary": index == 0,
                "substitution_fired": replays[name].substitution_fired,
                "realised_total": replays[name].realised_total,
                "entered_gk": replays[name].entered_gk,
                "entered_outfield": replays[name].entered_outfield,
            }
            for index, name in enumerate(names)
        )

    return HarnessResult(
        squad_weeks=pd.DataFrame(squad_week_rows),
        ordering_replays=pd.DataFrame(replay_rows),
    )


def build(
    squads: pd.DataFrame,
    rank_fn: RankFn,
    bench_order: BenchOrder,
    window: tuple[int, int],
    *,
    db_path: Path = DB_PATH,
) -> HarnessResult:
    """Read the mart via `dal/` and replay against it (§5.1).

    The one function in this module that touches the data layer, on the same shape as the
    sampler's `build_squads`: `run` is the same computation over a mart already in hand, which is
    what the tests exercise.
    """
    return run(squads, rank_fn, bench_order, load(db_path).mart, window)
