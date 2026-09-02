"""Naive greedy construction candidates -- `DESIGN.md` §4.

Three naive constructors (`DECISION.md` §4): season-PPG greedy (C1), value/PPG-per-price greedy
(C2), recent-form/rolling-PPG greedy (C3). All three fill positions in the same explicit order
(`domain.fpl_squad.POSITIONS`: GK -> DEF -> MID -> FWD), taking each position's remaining
candidates best-score-first and skipping any pick `feasibility.can_complete` says would make the
rest of the squad impossible to finish.

**Deviation from `DESIGN.md` §4's literal `ConstructionCandidate`, flagged rather than silently
applied.** The Protocol there declares exactly `player_id, position, price_tenths, team_id,
score`. `_Candidate` below carries three *extra* fields (`season_ppg`, `recent_form_ppg`,
`value`) so a single candidate-building pass over the mart (`build_candidates`) serves all three
policies, and each policy genuinely chooses its own ranking signal (rather than requiring the
caller to pre-score the list correctly before calling, which would push the one piece of
per-policy logic outside the policy function entirely). A concrete type carrying more than a
Protocol requires still structurally satisfies it -- `ConstructionPolicy`'s type is unaffected by
the extra fields the three named functions below happen to read.

`position` is typed `str`, not `Position` -- `DESIGN.md`'s code block names a `Position` type
that does not exist anywhere in this repository (confirmed by grep, `INVENTORY.md` §3); every
other position-keyed value in the codebase (`domain.fpl_squad.POSITIONS`,
`decisions.starting_xi.formations`'s `list[str]`) is typed plain `str` too, so this follows that
existing convention rather than inventing the missing type -- the same deviation
`feasibility.py`'s module docstring flags for `remaining_quota`.

**PPG derivation: re-derived locally from `total_points`, not imported.** `DESIGN.md` §4 requires
this -- importing `model.eval.baselines.expanding_prior_mean` pulls in `model/eval/__init__.py`'s
full eager fan-out regardless of which name is imported, a real `model/` dependency this Tier-A
slice must not take (`INVENTORY.md` §4). The pattern (`shift(1).expanding()` /
`shift(1).rolling(N, min_periods=1)`) matches `research/families/form/validate/study.py:347-350`
exactly, cited there for the identical reason: these `total_points`-derived columns are
deliberately excluded from the governed mart.

**Registration filtering.** `build_candidates` excludes any player not yet registered at the
target gameweek (first non-null `minutes` row, mirroring `decisions.starting_xi.sampler`'s
predicate, re-derived rather than imported for the same self-containment reason
`gameweek_population.py` gives). Confirmed directly against the live mart: a not-yet-debuted
player's `purchase_price` is a flat value identical to his eventual debut-gw price, held across
every pre-debut row -- the same phantom-pricing risk `decisions/starting_xi/INVENTORY.md`
documents for the sibling slice's sampler, and not specific to that slice's sampling method.
Without this filter a greedy constructor could pick a player who is not yet a real FPL asset that
gameweek, priced from data that does not exist yet.

No RNG anywhere in this module -- every function here is a pure function of its arguments.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

import numpy as np
import pandas as pd

from decisions.free_hit.feasibility import _Pool, can_complete
from domain.fpl_squad import MAX_PER_CLUB, POSITIONS, SQUAD_SIZE

RECENT_FORM_WINDOW: Final[int] = 3
"""Rolling-PPG window for C3's "recent form" signal. `DESIGN.md` does not pin a window; 3 matches
`research/families/form/validate/study.py:347`'s own `points_roll3` choice as a recognised
"recent form" horizon, named here rather than left as a literal so a different window is a
one-line change."""

FDR_ORDINAL_BINS: Final[list[float]] = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
FDR_ORDINAL_LABELS: Final[list[int]] = [1, 2, 3, 4, 5]
"""The governed ordinal representation of `fdr_avg` -- one bin per FDR rating on the rating's own
scale. Values re-derived from `research/kernels/descriptive/binning.py:28-29`, the scheme
`select_bucketing_scheme` returns for `FDR_SIGNALS`, rather than imported, for this module's
standing Tier-A self-containment reason (see module docstring, and `DESIGN.MD` §7.5 for the same
call made a third time in `verdict.py`). `binning.py` labels them as strings for `pd.cut`'s
categorical output; integers here because C4 does arithmetic on the bin (`FDR_BIN_REVERSAL - bin`),
not grouping by it.

`DESIGN.MD` §7.2 makes this load-bearing rather than cosmetic: 59% of DEF rows sit at exactly
`fdr_avg == 3.0`, so a rank normalization of *raw* `fdr_avg` would give most of the pool the
identical averaged tie rank and leave the fdr term nominally weighted but practically inert --
exactly the degeneracy the strictly-nonzero-weight constraint exists to prevent."""

FDR_BIN_REVERSAL: Final[int] = max(FDR_ORDINAL_LABELS) + min(FDR_ORDINAL_LABELS)
"""`5 + 1 = 6`, the constant in `DESIGN.MD` §7.2's `6 - fdr_bin`. Lower fdr is better and the other
two composite terms are higher-is-better, so the fdr term is reversed *before* normalizing. Handling
the direction with a negative weight instead is rejected by §7.2: it would make "strictly nonzero
weights" and "every weight positive" different statements and invite a later reader to mistake the
sign for a preference for hard fixtures."""

COMPOSITE_WEIGHTS: Final[dict[str, float]] = {"recent_form_ppg": 0.25, "value": 0.25, "fdr": 0.50}
"""C4's weight vector -- `DESIGN.MD` §7.2's CURRENT SPECIFICATION, **pre-registered and never
fitted**. Supersedes the equal thirds used for C4's first run, per §7.2.1.

Fixed a priori and hard-coded, not a parameter with a default: fitting these on the 32-gameweek
evaluation set would make `METRIC.md` §2's verdict a resubstitution estimate and its p-values
meaningless, and that set is the only season available. The correction is derived from the one
population-independent finding in §7.2.1 -- `recent_form_ppg` and `value` are near-duplicates
(Spearman rho ~ +0.850 full pool, +0.566 survivors) while the fdr term is orthogonal to both in
both populations (~0.001) -- so the two collinear terms split one weight-slot's worth of influence
and the orthogonal term takes the other half. It is *not* tuned to any partial-rho magnitude and
*not* derived from C4's first-run regret result, so §7.2's a-priori requirement is preserved.

§7.2.1 marks this as the **final** weight-vector test for this candidate definition: if it also
fails `METRIC.md` §2's conjunctive rule, that is the documented conclusion, not a cue for a third
vector. Any substitute must be justified off-evaluation-set and written into `DESIGN.MD` §7.2
first."""

ABLATION_WEIGHTS: Final[dict[str, float]] = {"recent_form_ppg": 1 / 2, "value": 1 / 2, "fdr": 0.0}
"""C4-nofdr's weight vector -- `DESIGN.MD` §7.3's ablation: the fdr term dropped, its weight
redistributed *proportionally* across the other two, so the two variants differ in exactly one
thing (fdr present or absent) rather than in fdr *and* the relative balance of the other two.

A diagnostic, not a fourth candidate. §7.3 is explicit that it does not enter `METRIC.md` §2's
Holm-Bonferroni family, which is pre-registered as exactly three candidate-vs-baseline comparisons;
adding a fourth arm post hoc would be the multiplicity inflation §2 exists to control. This is the
one weight vector in this module exempt from the strictly-positive invariant below, by
construction -- `_composite_scores` takes the exemption as an explicit argument rather than
inferring it from the zero."""


class ConstructionCandidate(Protocol):
    """`DESIGN.md` §4's element type for `ConstructionPolicy` -- see module docstring for the
    `Position` deviation."""

    player_id: int
    position: str
    price_tenths: int
    team_id: int
    score: float


ConstructionPolicy = Callable[[Sequence[ConstructionCandidate], int, dict[str, int]], list[ConstructionCandidate]]
"""`DESIGN.md` §4's policy type: a full-squad greedy fill, not a per-pick step. Takes the whole
scored candidate pool for one gameweek plus a budget (tenths) and quota, and returns the selected
legal squad."""


class InfeasibleGameweek(Exception):
    """No legal 15-player squad (2 GK/5 DEF/5 MID/3 FWD, budget, club cap) exists in the pool
    handed to a construction policy."""


@dataclass
class _Candidate:
    """Concrete `ConstructionCandidate` -- see module docstring for why it carries the three raw
    signals rather than only the Protocol's minimum `score`.

    Not frozen: `DESIGN.md` §4's `ConstructionCandidate` Protocol declares plain (read-write)
    attributes, and mypy's structural Protocol check requires an implementing class's attributes
    to match that mutability exactly -- a frozen dataclass's fields are read-only and would not
    satisfy it.
    """

    player_id: int
    position: str
    price_tenths: int
    team_id: int
    season_ppg: float
    recent_form_ppg: float
    value: float
    fdr_bin: float
    score: float


def _price_tenths(price: float) -> int:
    """Convert a mart price to integer tenths -- the unit the budget cap is exact in.

    Reimplemented from `decisions.starting_xi.sampler._price_tenths`'s exact check rather than
    imported, for the same self-containment reason as the rest of this module.
    """
    tenths = price * 10.0
    if abs(tenths - round(tenths)) > 1e-6:
        raise ValueError(f"purchase_price {price!r} is not quoted in tenths")
    return round(tenths)


def build_candidates(mart: pd.DataFrame, gw: int) -> list[ConstructionCandidate]:
    """This gameweek's eligible, registered candidates, with all three re-derived signals.

    A signal is `float("nan")` wherever its window has no prior data -- always true for every
    player at GW1, since `shift(1)` has nothing before the season's first row. `_greedy_fill`
    treats a NaN score as unrankable: sorted after every scored candidate, never a reason to
    exclude the player (mirroring `decisions.starting_xi.orderings`'s unrankable-tier handling).
    """
    ordered = mart.sort_values(["player_id", "gw"]).copy()
    ordered["season_ppg"] = ordered.groupby("player_id")["total_points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )
    ordered["recent_form_ppg"] = ordered.groupby("player_id")["total_points"].transform(
        lambda s: s.shift(1).rolling(RECENT_FORM_WINDOW, min_periods=1).mean()
    )
    # Value is season_ppg per unit price, not recent_form_ppg per price -- C2 and C3 differ only
    # in "which points signal", never compounding two choices into one number.
    ordered["value"] = ordered["season_ppg"] / ordered["purchase_price"]
    # The governed ordinal representation, not raw `fdr_avg` -- see FDR_ORDINAL_BINS.
    # `pd.cut` is right-closed, so bin i holds (i - 0.5, i + 0.5]: exactly the integer rating i.
    ordered["fdr_bin"] = pd.cut(ordered["fdr_avg"], bins=FDR_ORDINAL_BINS, labels=FDR_ORDINAL_LABELS).astype("float64")

    registered_gw = ordered.loc[ordered["minutes"].notna()].groupby("player_id")["gw"].min()
    ordered["registered_gw"] = ordered["player_id"].map(registered_gw)

    week = ordered.loc[(ordered["gw"] == gw) & ordered["registered_gw"].notna() & (ordered["registered_gw"] <= gw)]

    return [
        _Candidate(
            player_id=int(row.player_id),
            position=str(row.position),
            price_tenths=_price_tenths(float(row.purchase_price)),
            team_id=int(row.team_id),
            season_ppg=float(row.season_ppg),
            recent_form_ppg=float(row.recent_form_ppg),
            value=float(row.value),
            fdr_bin=float(row.fdr_bin),
            score=float("nan"),
        )
        for row in week.itertuples()
    ]


def _sort_key(candidate: ConstructionCandidate) -> tuple[bool, float, int]:
    """Best score first; a NaN score sorts last; ties break on ascending `player_id`."""
    unrankable = candidate.score != candidate.score  # NaN != NaN, avoids importing math for one check
    return (unrankable, 0.0 if unrankable else -candidate.score, candidate.player_id)


def _group_by_position(candidates: Sequence[ConstructionCandidate]) -> dict[str, list[ConstructionCandidate]]:
    by_position: dict[str, list[ConstructionCandidate]] = {position: [] for position in POSITIONS}
    for candidate in candidates:
        by_position[candidate.position].append(candidate)
    return by_position


def _build_pool(by_position: dict[str, list[ConstructionCandidate]]) -> dict[str, _Pool]:
    return {
        position: _Pool(
            player_id=np.array([c.player_id for c in group], dtype=np.int64),
            price_tenths=np.array([c.price_tenths for c in group], dtype=np.int64),
            team_id=np.array([c.team_id for c in group], dtype=np.int64),
        )
        for position, group in by_position.items()
    }


def _greedy_fill(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """The shared fill routine every named policy below delegates to, once `.score` is set.

    Fills positions in `domain.fpl_squad.POSITIONS`'s order -- GK -> DEF -> MID -> FWD -- taking
    each position's candidates best-`score`-first (`_sort_key`) and skipping a candidate that
    would make the rest of the squad infeasible per `can_complete`. Raises `InfeasibleGameweek`
    if a position's quota cannot be filled from the candidates at all.
    """
    by_position = _group_by_position(candidates)
    pool = _build_pool(by_position)

    picked: list[ConstructionCandidate] = []
    picked_ids: list[int] = []
    picked_prices: list[int] = []
    picked_teams: list[int] = []
    budget_left = budget_tenths
    quota_left = dict(quota)

    for position in POSITIONS:
        ranked = sorted(by_position[position], key=_sort_key)
        for candidate in ranked:
            if quota_left.get(position, 0) <= 0:
                break
            if candidate.price_tenths > budget_left:
                continue
            if picked_teams.count(candidate.team_id) >= MAX_PER_CLUB:
                continue

            trial_ids = np.array([*picked_ids, candidate.player_id], dtype=np.int64)
            trial_prices = np.array([*picked_prices, candidate.price_tenths], dtype=np.int64)
            trial_teams = np.array([*picked_teams, candidate.team_id], dtype=np.int64)
            trial_quota = quota_left | {position: quota_left.get(position, 0) - 1}
            trial_budget = budget_left - candidate.price_tenths

            if not can_complete(trial_ids, trial_prices, trial_teams, trial_budget, trial_quota, pool):
                continue

            picked.append(candidate)
            picked_ids = trial_ids.tolist()
            picked_prices = trial_prices.tolist()
            picked_teams = trial_teams.tolist()
            budget_left = trial_budget
            quota_left = trial_quota

        if quota_left.get(position, 0) > 0:
            raise InfeasibleGameweek(
                f"no legal {SQUAD_SIZE}-player squad exists in this pool: {quota_left[position]} "
                f"{position} slot(s) remain unfilled after exhausting the position's candidates"
            )

    if sum(quota_left.values()) != 0 or len(picked) != SQUAD_SIZE:
        raise InfeasibleGameweek(f"no legal {SQUAD_SIZE}-player squad exists in this pool")

    return picked


def _scored(candidates: Sequence[ConstructionCandidate], field: str) -> list[ConstructionCandidate]:
    """Copy `candidates` with `.score` set from the named raw signal field.

    `candidates` in practice are always `_Candidate` instances carrying `season_ppg`/
    `recent_form_ppg`/`value` -- fields beyond `ConstructionCandidate`'s Protocol minimum -- so
    every field here is read via `getattr` rather than static attribute access, keeping this
    function's parameter honestly typed as the Protocol rather than the concrete class.
    """
    return [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=getattr(c, "season_ppg"),
            recent_form_ppg=getattr(c, "recent_form_ppg"),
            value=getattr(c, "value"),
            fdr_bin=getattr(c, "fdr_bin"),
            score=getattr(c, field),
        )
        for c in candidates
    ]


def greedy_by_season_ppg(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """C1 -- greedy by as-of season-PPG (`DECISION.md` §4)."""
    return _greedy_fill(_scored(candidates, "season_ppg"), budget_tenths, quota)


def greedy_by_value(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """C2 -- greedy by value, season-PPG per unit price (`DECISION.md` §4)."""
    return _greedy_fill(_scored(candidates, "value"), budget_tenths, quota)


def greedy_by_recent_form(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """C3 -- greedy by recent form, rolling PPG over `RECENT_FORM_WINDOW` gameweeks
    (`DECISION.md` §4)."""
    return _greedy_fill(_scored(candidates, "recent_form_ppg"), budget_tenths, quota)


def _rank_normalize(values: np.ndarray) -> np.ndarray:
    """`DESIGN.MD` §7.2's `r(.)`: ascending rank over this gameweek's pool, mapped to `[0, 1]`.

    `(rank - 1) / (n - 1)` with ties taking their **average** rank. NaN in, NaN out -- a missing
    term must propagate to a NaN composite score rather than be imputed to a middling rank (§7.2),
    and NaN is excluded from the ranking entirely so it cannot shift the scored candidates'
    positions.

    Rank normalization rather than z-scoring, per §7.2: the three terms are on incommensurable
    scales (points, points-per-million, a 1-5 ordinal), so raw addition would let the scales rather
    than the weights set the effective weighting; and z-scoring fixes the units but not the shape,
    since one explosive haul in a heavy-tailed points distribution would let a single player's
    `recent_form_ppg` dominate a fixed-weight sum. The stated cost: ranks discard magnitude, so a
    player far ahead of second place on form is scored as merely first.

    A pool with fewer than two scorable values has no `(n - 1)` to divide by; every scorable entry
    is mapped to 0.5, the midpoint, since no ordering information exists to separate them.
    """
    out = np.full(values.shape, np.nan, dtype=float)
    scorable = ~np.isnan(values)
    n = int(scorable.sum())
    if n == 0:
        return out
    if n == 1:
        out[scorable] = 0.5
        return out

    present = values[scorable]
    order = np.argsort(present, kind="stable")
    ordinal = np.empty(n, dtype=float)
    ordinal[order] = np.arange(1, n + 1, dtype=float)

    # Average rank within each group of tied values, matching §7.2's "ties taking their average
    # rank" -- without this, `argsort`'s stable order would break ties by pool position, which is
    # arbitrary and would make the score depend on the mart's row order.
    unique, inverse = np.unique(present, return_inverse=True)
    sums = np.zeros(unique.size, dtype=float)
    counts = np.zeros(unique.size, dtype=float)
    np.add.at(sums, inverse, ordinal)
    np.add.at(counts, inverse, 1.0)
    averaged = (sums / counts)[inverse]

    out[scorable] = (averaged - 1.0) / (n - 1)
    return out


def _composite_scores(
    candidates: Sequence[ConstructionCandidate],
    weights: dict[str, float],
    *,
    allow_zero_fdr_weight: bool = False,
) -> list[ConstructionCandidate]:
    """`DESIGN.MD` §7.2's combination rule -- copy `candidates` with `.score` set to the composite.

        score(p, g) = w_form * r(recent_form_ppg) + w_value * r(value) + w_fdr * r(6 - fdr_bin)

    Additive, rank-normalized within the gameweek's whole pool (not per position -- §7.2's grain is
    global, one ranking key and the same weights for every position, matching the position-blind
    ranker C1/C2/C3 already use). The composite is NaN whenever **any** of its three terms is NaN,
    which propagates the existing per-signal NaN semantics rather than silently imputing a missing
    signal; `_sort_key` then sorts those candidates last (§7.7 measures the rate at 138/24,918 =
    0.554% of eligible candidate rows, ~4-5 per gameweek, and assesses the existing NaN-last
    tie-break as sufficient).

    **Documented invariant: the weights are strictly positive and sum to 1.** §7.2 makes the
    strictly-nonzero constraint definitional -- it is what guarantees every term contributes at
    every ranking, so C4 can never degenerate into being one of C1/C2/C3. Both the superseded equal
    thirds and §7.2's current 0.25 / 0.25 / 0.50 satisfy it incidentally; asserting it here makes
    it a checked property of the module rather than an
    accident of the default, so a future substitute weight vector cannot quietly violate it.
    `allow_zero_fdr_weight` is the single explicit exemption, for §7.3's C4-nofdr ablation, which
    is a diagnostic rather than a candidate and drops the fdr term by definition.
    """
    missing = {"recent_form_ppg", "value", "fdr"} - set(weights)
    if missing:
        raise ValueError(f"weights must name all three composite terms; missing {sorted(missing)}")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1, got {sum(weights.values())!r}")
    zero_allowed = {"fdr"} if allow_zero_fdr_weight else set()
    for term, weight in weights.items():
        if weight < 0.0 or (weight == 0.0 and term not in zero_allowed):
            raise ValueError(f"weight for {term!r} must be strictly positive, got {weight!r}")

    form = _rank_normalize(np.array([getattr(c, "recent_form_ppg") for c in candidates], dtype=float))
    value = _rank_normalize(np.array([getattr(c, "value") for c in candidates], dtype=float))
    # Reversed before normalizing so all three terms are higher-is-better and w_fdr stays positive.
    fdr = _rank_normalize(FDR_BIN_REVERSAL - np.array([getattr(c, "fdr_bin") for c in candidates], dtype=float))

    scores = weights["recent_form_ppg"] * form + weights["value"] * value + weights["fdr"] * fdr

    return [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=getattr(c, "season_ppg"),
            recent_form_ppg=getattr(c, "recent_form_ppg"),
            value=getattr(c, "value"),
            fdr_bin=getattr(c, "fdr_bin"),
            score=float(score),
        )
        for c, score in zip(candidates, scores, strict=True)
    ]


def greedy_by_composite(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """C4 -- greedy by the 0.25 / 0.25 / 0.50 composite of recent form, value and reversed fdr bin
    (`DESIGN.MD` §7.2). The cheap non-forecasting candidate `DECISION.md` §4 sequences first."""
    return _greedy_fill(_composite_scores(candidates, COMPOSITE_WEIGHTS), budget_tenths, quota)


def greedy_by_composite_nofdr(
    candidates: Sequence[ConstructionCandidate],
    budget_tenths: int,
    quota: dict[str, int],
) -> list[ConstructionCandidate]:
    """C4-nofdr -- `DESIGN.MD` §7.3's ablation of C4 with the fdr term dropped.

    A **diagnostic**, not a fourth candidate: it does not compete for `METRIC.md` §2's verdict and
    must not enter the Holm-Bonferroni family. Its purpose is to answer whether the fdr term --
    C4's only structurally orthogonal input, since `recent_form_ppg` and `value` are two views of
    the same lagged `total_points` series (§7.4) -- moved anything, and in which direction.
    """
    return _greedy_fill(
        _composite_scores(candidates, ABLATION_WEIGHTS, allow_zero_fdr_weight=True), budget_tenths, quota
    )
