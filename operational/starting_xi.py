"""The `starting_xi` composition root -- `DESIGN.md` §3.8, §5.1.2, §6.3.1, §7.3, §8.2.

**The one place Tier A and Tier B meet.** `INVENTORY.md` §2.11 records that `operational/` is not a
root package and carries no `.importlinter` contract, which is what §3.8 relies on to make this the
legal place to wire a Tier B ranker (`rankers.py`) into a Tier A harness (`harness.py`). §8.2 states
the same wiring from the interval side: "the composition root imports `harness.py`, `rankers.py` and
`uncertainty.py` and wires them together." `sampler.py`, `results.py` and `orderings.py` join that
list because §5.1.2's assembly needs all three directly -- squads to replay, an artefact to write,
and the sole pre-registered ordering to default `bench_order` to. Verified against the text rather
than assumed: nothing in §3.8 or `INVENTORY.md` §2.11 narrows what `operational/` may import, and
nothing else in the slice is a candidate caller of these six modules together.

**T3 assembly lives here, as named private functions, per §5.1.2.** Six pieces of logic, all fully
specified elsewhere in `DESIGN.md` and none a choice left to this module: §0.13's floor
determination, §10.7's differencing, §7.2.1's `ordering_relevant_count` derivation, §0.15's S1/S2/S3
bar, and §7.5's per-status row shape. §5.1.2 rejects both inlining them into `run_study` and giving
them a new Tier module of their own -- they are named private functions taking and returning frames,
testable without `dal/` or `model/`.

**The window per ranker, per §6.3.1.** `harness.run` is called once per ranker, at that ranker's own
declared window -- never at a comparison's intersection, which is computed post-hoc from T2 instead
(§6.3.1: "replay wide, restrict at assembly"). This module reads each ranker's declared window from
`rankers.DECLARED_WINDOWS`, which that module exposes "so the composition root can record the
windows without running a comparison" -- calling `rank_fn` a second time just to read `.window`
would refit `p_play`'s expanding walk-forward for nothing.

**`bench_order` defaults to the sole pre-registered ordering, and nothing else.** §5.4 makes
`bench_order` a required argument with no default at `harness.run`'s own boundary, because a
defaulted ordering would emit a regret figure that could not be reconstructed from its stated
inputs; that contract is unchanged here; `harness.run` still receives it explicitly on every call
this module makes. What this module adds is a *convenience* default at its own boundary, and the
only value that could occupy it without inventing one: `orderings.PRE_REGISTERED_ORDERINGS`, §5.4.1's
single committed policy. `rank_fns` is symmetric: it defaults to `rankers.FLOOR_RANKERS`, §0.12's
whole pre-registered, unconditional set.

**A T3 gap this pass resolves and flags rather than hides.** §0.13 determines the floor as
"whichever naive ranker carries the lowest mean regret" *within a comparison*, and every occurrence
of "comparison" in `DESIGN.md` presupposes a candidate ranker distinct from the naive floor set --
`METRIC.md` and `DECISION.md` both record that no candidate ranker has been characterised yet
(`DESIGN.md` §1.5). Nowhere does `DESIGN.md` say what a "comparison" is among *only* the three
pre-registered floor rankers, and applying §0.13's rule to that set literally is incoherent: the
floor is defined as whichever of the compared rankers has the lowest regret, so calling the other
member of the pair a "candidate" being reduced *against* the floor it lost to inverts the sign of
every S1/S3 check. Resolved here as the narrowest reading that needs no invented floor-vs-floor
semantics: **a comparison is one non-floor ranker in `rank_fns` (a name absent from
`rankers.FLOOR_RANKERS`) against the floor rankers present in `rank_fns`.** Under the default
`rank_fns` -- the floor set alone -- there is no such name, so `run_study` legitimately writes T3
with **zero rows**. That is not an omission: §1.5's own list of "measurements owed on the first run"
(the sampler's acceptance rate, the no-fixture-rule count, the DGW-exclusion materiality) needs only
T2 and the manifest, and none of them is a comparison. Flagged for a `DESIGN.md` pass rather than
silently generalised further.

**Import closure: `dal/`, `decisions.starting_xi.{harness,rankers,orderings,uncertainty,results,
sampler}`, and -- transitively, through `rankers.py` -- `model/`.** Nothing here is forbidden:
`operational/` is covered by no `.importlinter` contract in either direction (§3.8), and this is the
one call site `rankers.py`'s Tier B permission and `harness.py`/`sampler.py`'s Tier A `dal/` edge are
both meant to be exercised from. (`serve` also loads whenever this module does, because
`operational/__init__.py` eagerly re-exports `operational.recommend`, which imports it -- a
pre-existing property of the package `__init__`, not of anything `starting_xi.py` itself imports.)
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load
from decisions.starting_xi import orderings, rankers, results, sampler, uncertainty
from decisions.starting_xi.harness import BenchOrder, HarnessResult, RankFn
from decisions.starting_xi.harness import run as harness_run

# §0.15's materiality bar and §6.3's underpowered floor -- one bootstrap block (§0.14's `block = 4`).
MATERIALITY_THRESHOLD: Final[float] = 0.10
MIN_SCOREABLE_GW: Final[int] = 4

# §0.13's naive floor set -- every name `rankers.FLOOR_RANKERS` pre-registers. A `rank_fns` name
# absent from this set is a candidate; present in it, a floor member. See the module docstring's
# resolution of what a "comparison" is under the default (floor-only) `rank_fns`.
_FLOOR_NAMES: Final[frozenset[str]] = frozenset(rankers.FLOOR_RANKERS)


@dataclass(frozen=True)
class StartingXIRun:
    """One run's summary -- `run_id`, where it landed, and the two counts a caller checks first."""

    run_id: str
    results_dir: Path
    n_squad_weeks: int
    n_comparisons: int


# ---------------------------------------------------------------------------
# T3 assembly -- §5.1.2's named private functions
# ---------------------------------------------------------------------------


def _ranker_window(t2: pd.DataFrame, ranker: str) -> tuple[int, int]:
    """A ranker's replayed span, read off its own T2 rows rather than `rankers.DECLARED_WINDOWS`.

    `harness.run` is called at exactly that ranker's declared window (§6.3.1), so T2's own `gw`
    range for that ranker already *is* the declared window -- reading it back keeps T3 assembly a
    pure function of T2/T5, independent of `rankers.py`'s naming, and testable against a
    constructed frame with no fixed set of ranker names (§5.1.2's testability argument).
    """
    rows = t2.loc[t2["ranker"] == ranker, "gw"]
    if rows.empty:
        raise ValueError(f"T2 carries no rows for ranker {ranker!r}")
    return int(rows.min()), int(rows.max())


def _determine_floor(t2: pd.DataFrame, floor_names: Sequence[str], window: tuple[int, int]) -> tuple[str, float]:
    """§0.13: the floor is whichever naive ranker has the lowest mean regret on the comparison's
    window, after §0.8's zero-gap exclusion -- re-determined per comparison, never nominated."""
    first, last = window
    means: dict[str, float] = {}
    for name in floor_names:
        rows = t2.loc[(t2["ranker"] == name) & (t2["gw"] >= first) & (t2["gw"] <= last) & (~t2["is_zero_gap"])]
        means[name] = float(rows["regret"].mean()) if not rows.empty else math.nan
    finite = {name: mean for name, mean in means.items() if not math.isnan(mean)}
    if not finite:
        raise ValueError(f"no floor ranker among {list(floor_names)} has a scoreable row on window {window}")
    floor_ranker = min(finite, key=lambda name: finite[name])
    return floor_ranker, finite[floor_ranker]


def _difference_and_restrict(
    t2: pd.DataFrame, candidate: str, floor_ranker: str, window: tuple[int, int]
) -> pd.DataFrame:
    """§10.7: "the differencing is the caller's step" -- pivot T2 on `ranker`, subtract, drop
    zero-gap rows, restrict to the window. `value = floor's regret - candidate's regret`, so a
    positive value is the candidate reducing regret relative to the floor (§10.2's estimand).

    Returns a `(gw, squad_id, value)` panel -- `uncertainty.py`'s `PANEL_COLUMNS` shape (§5.1).
    """
    first, last = window
    subset = t2.loc[
        t2["ranker"].isin([candidate, floor_ranker]) & (t2["gw"] >= first) & (t2["gw"] <= last),
        ["squad_id", "gw", "ranker", "regret", "is_zero_gap"],
    ]
    pivoted = subset.pivot(index=["squad_id", "gw"], columns="ranker", values="regret")
    # is_zero_gap is a property of the squad-week, not the ranker (§10.4), so both rows in a pair
    # agree; `.any()` is a defensive OR rather than a claim that they could disagree.
    zero_gap = subset.groupby(["squad_id", "gw"])["is_zero_gap"].any()
    panel = pivoted.assign(value=pivoted[floor_ranker] - pivoted[candidate], is_zero_gap=zero_gap)
    panel = panel.loc[~panel["is_zero_gap"]].reset_index()
    return panel.loc[:, ["gw", "squad_id", "value"]]


def _derive_ordering_relevant_count(t5: pd.DataFrame, candidate: str, window: tuple[int, int]) -> int:
    """§7.2.1: a squad-week is ordering-relevant when a substitution fired **and** the compared
    orderings' `entered_outfield` sets are not all identical. Derived over the candidate's own T5
    rows -- the candidate is the ranker the comparison is evaluating, and §4.4 conditions the bench
    on that ranker's own XI. Always 0 under `orderings.PRE_REGISTERED_ORDERINGS` (one policy, so no
    two orderings can differ -- §5.4.1), and computed genuinely anyway so a second policy needs no
    change here.
    """
    first, last = window
    subset = t5.loc[(t5["ranker"] == candidate) & (t5["gw"] >= first) & (t5["gw"] <= last)]
    if subset.empty:
        return 0

    def _relevant(group: pd.DataFrame) -> bool:
        return bool(group["substitution_fired"].all()) and group["entered_outfield"].nunique() > 1

    relevant = subset.groupby(["squad_id", "gw"]).apply(_relevant, include_groups=False)
    return int(relevant.sum())


def _evaluate_bar(
    floor_mean_regret: float,
    candidate_mean_regret: float,
    ci_squads: tuple[float, float],
    ci_gw: tuple[float, float],
) -> tuple[float, float, bool, bool, bool, bool]:
    """§0.15: S1 (direction), S2 (significance -- both intervals exclude zero), S3 (materiality,
    10% of the floor's own mean regret). All three required; any two is a fail.

    Returns `(abs_reduction, rel_reduction, crit_direction, crit_significance, crit_materiality,
    passed)`.
    """
    abs_reduction = floor_mean_regret - candidate_mean_regret
    rel_reduction = abs_reduction / floor_mean_regret if floor_mean_regret != 0 else math.nan
    crit_direction = abs_reduction > 0
    crit_significance = (ci_squads[0] > 0 or ci_squads[1] < 0) and (ci_gw[0] > 0 or ci_gw[1] < 0)
    crit_materiality = not math.isnan(rel_reduction) and rel_reduction >= MATERIALITY_THRESHOLD
    passed = crit_direction and crit_significance and crit_materiality
    return abs_reduction, rel_reduction, crit_direction, crit_significance, crit_materiality, passed


def _base_row(candidate: str, floor_names: Sequence[str], window: tuple[int, int]) -> dict[str, object]:
    """§7.2's T3 columns (minus `run_id`), defaulted to `None` and filled in by identity fields
    every status carries (§7.5: "Identity, rankers and window populated" even when not evaluable).
    """
    row: dict[str, object] = dict.fromkeys(results.T3_COLUMNS[1:])
    row.update(
        comparison_id=candidate,
        rankers=[candidate, *floor_names],
        window_first_gw=window[0],
        window_last_gw=window[1],
    )
    return row


def _not_evaluable_row(candidate: str, floor_names: Sequence[str], window: tuple[int, int]) -> dict[str, object]:
    """§7.5: empty window intersection. Identity, rankers and window populated; every estimate null."""
    row = _base_row(candidate, floor_names, window)
    row["status"] = "not_evaluable"
    row["status_reason"] = f"empty window intersection {window} (DESIGN.md §6.3, §7.5)"
    return row


def _underpowered_row(
    candidate: str,
    floor_names: Sequence[str],
    window: tuple[int, int],
    floor_ranker: str,
    floor_mean_regret: float,
    candidate_mean_regret: float,
    n_scoreable_gw: int,
    counts: Mapping[str, int],
) -> dict[str, object]:
    """§7.5: fewer than `MIN_SCOREABLE_GW` scoreable gameweeks -- below one bootstrap block, so
    S2 cannot be evaluated. Point estimates and counts are populated because they need no interval;
    `crit_significance` and `passed` are null rather than false (§7.5's "Null is not false")."""
    abs_reduction = floor_mean_regret - candidate_mean_regret
    rel_reduction = abs_reduction / floor_mean_regret if floor_mean_regret != 0 else math.nan
    row = _base_row(candidate, floor_names, window)
    row.update(
        n_scoreable_gw=n_scoreable_gw,
        floor_ranker=floor_ranker,
        floor_mean_regret=floor_mean_regret,
        candidate_mean_regret=candidate_mean_regret,
        abs_reduction=abs_reduction,
        rel_reduction=None if math.isnan(rel_reduction) else rel_reduction,
        crit_direction=abs_reduction > 0,
        crit_materiality=(not math.isnan(rel_reduction)) and rel_reduction >= MATERIALITY_THRESHOLD,
        status="underpowered",
        status_reason=(
            f"{n_scoreable_gw} scoreable gameweek(s), below one bootstrap block of "
            f"{MIN_SCOREABLE_GW} (DESIGN.md §6.3, §0.14)"
        ),
        **counts,
    )
    return row


def _evaluated_row(
    candidate: str,
    floor_names: Sequence[str],
    window: tuple[int, int],
    floor_ranker: str,
    floor_mean_regret: float,
    candidate_mean_regret: float,
    n_scoreable_gw: int,
    ci_squads: tuple[float, float],
    ci_gw: tuple[float, float],
    counts: Mapping[str, int],
) -> dict[str, object]:
    """§7.5: the normal case. All fields populated, including both intervals and §0.15's bar."""
    abs_reduction, rel_reduction, crit_direction, crit_significance, crit_materiality, passed = _evaluate_bar(
        floor_mean_regret, candidate_mean_regret, ci_squads, ci_gw
    )
    row = _base_row(candidate, floor_names, window)
    row.update(
        n_scoreable_gw=n_scoreable_gw,
        floor_ranker=floor_ranker,
        floor_mean_regret=floor_mean_regret,
        candidate_mean_regret=candidate_mean_regret,
        abs_reduction=abs_reduction,
        rel_reduction=None if math.isnan(rel_reduction) else rel_reduction,
        ci_squads_lo=ci_squads[0],
        ci_squads_hi=ci_squads[1],
        ci_gw_lo=ci_gw[0],
        ci_gw_hi=ci_gw[1],
        crit_direction=crit_direction,
        crit_significance=crit_significance,
        crit_materiality=crit_materiality,
        passed=passed,
        status="evaluated",
        status_reason=None,
        **counts,
    )
    return row


def _assemble_comparison(
    candidate: str, floor_names: Sequence[str], t2: pd.DataFrame, t5: pd.DataFrame
) -> dict[str, object]:
    """One T3 row: §6.3's window intersection, §0.13's floor, §10.7's panel, §0.15's bar -- and the
    right §7.5 status for what the window and the panel actually support.
    """
    candidate_window = _ranker_window(t2, candidate)
    floor_windows = [_ranker_window(t2, name) for name in floor_names]
    first = max(candidate_window[0], *(w[0] for w in floor_windows))
    last = min(candidate_window[1], *(w[1] for w in floor_windows))
    window = (first, last)
    if first > last:
        return _not_evaluable_row(candidate, floor_names, window)

    floor_ranker, floor_mean_regret = _determine_floor(t2, floor_names, window)
    candidate_rows = t2.loc[
        (t2["ranker"] == candidate) & (t2["gw"] >= first) & (t2["gw"] <= last) & (~t2["is_zero_gap"])
    ]
    if candidate_rows.empty:
        return _not_evaluable_row(candidate, floor_names, window)
    candidate_mean_regret = float(candidate_rows["regret"].mean())

    window_rows = t2.loc[(t2["ranker"] == candidate) & (t2["gw"] >= first) & (t2["gw"] <= last)]
    counts = {
        "n_zero_gap_excluded": int(window_rows["is_zero_gap"].sum()),
        "substitution_count": int(candidate_rows["substitution_fired"].sum()),
        "uncovered_blank_count": int(candidate_rows["uncovered_blank"].sum()),
        "ordering_relevant_count": _derive_ordering_relevant_count(t5, candidate, window),
        "no_fixture_rule_count": int(candidate_rows["no_fixture_rule_changed_xi"].sum()),
    }

    panel = _difference_and_restrict(t2, candidate, floor_ranker, window)
    n_scoreable_gw = int(panel["gw"].nunique())

    if n_scoreable_gw < MIN_SCOREABLE_GW:
        return _underpowered_row(
            candidate,
            floor_names,
            window,
            floor_ranker,
            floor_mean_regret,
            candidate_mean_regret,
            n_scoreable_gw,
            counts,
        )

    gw_series = panel.groupby("gw")["value"].mean().sort_index().to_numpy()
    ci_squads = uncertainty.squad_stratified_ci(panel, n_scoreable_gw=n_scoreable_gw)
    ci_gw = uncertainty.gameweek_block_ci(gw_series, n_scoreable_gw=n_scoreable_gw)

    return _evaluated_row(
        candidate,
        floor_names,
        window,
        floor_ranker,
        floor_mean_regret,
        candidate_mean_regret,
        n_scoreable_gw,
        ci_squads,
        ci_gw,
        counts,
    )


def _assemble_comparisons(t2: pd.DataFrame, t5: pd.DataFrame, rank_fns: Mapping[str, RankFn]) -> pd.DataFrame:
    """§7.2's T3, one row per candidate in `rank_fns` that is not a member of the floor set.

    See the module docstring: under the default `rank_fns` (the floor set alone) there is no such
    candidate, and this returns a correctly-schematised, zero-row frame.
    """
    floor_names = sorted(set(rank_fns) & _FLOOR_NAMES)
    candidate_names = sorted(set(rank_fns) - _FLOOR_NAMES)
    columns = list(results.T3_COLUMNS[1:])
    if not candidate_names:
        return pd.DataFrame(columns=columns)
    rows = [_assemble_comparison(candidate, floor_names, t2, t5) for candidate in candidate_names]
    return pd.DataFrame(rows).loc[:, columns]


def _sampler_diagnostics(run_record: pd.DataFrame) -> list[dict[str, object]]:
    """§7.3's manifest metadata: the sampler's per-gameweek run record, as plain Python values.

    `DataFrame.to_dict` returns numpy scalars for numeric columns, which `json.dumps`
    (`results.manifest_document`) does not serialise; `.item()` narrows each cell back to a native
    type.
    """
    return [
        {key: (value.item() if hasattr(value, "item") else value) for key, value in row.items()}
        for row in run_record.to_dict("records")
    ]


# ---------------------------------------------------------------------------
# The run (§5.1.2)
# ---------------------------------------------------------------------------


def run_study(
    mart: pd.DataFrame,
    *,
    bench_order: BenchOrder = orderings.PRE_REGISTERED_ORDERINGS,
    rank_fns: Mapping[str, RankFn] = rankers.FLOOR_RANKERS,
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    results_root: Path,
) -> StartingXIRun:
    """Run the `starting_xi` study against a mart already in hand -- the DB-free core.

    Sequence (§5.1.2): sample squads once, replay each ranker at its own declared window
    (§6.3.1 -- never at a comparison's intersection), assemble T3 from T2/T5, build the manifest,
    write the artefact.

    Args:
        mart: the mart across every gameweek in `gameweeks`, already in hand.
        bench_order: §5.4's required-shape argument, defaulted to §5.4.1's sole pre-registered
            policy set. `harness.run` itself still receives it as an explicit, non-defaulted
            argument on every call this function makes.
        rank_fns: name -> `rank(mart) -> RankerOutput`. Defaults to §0.12's whole pre-registered,
            unconditional floor set.
        gameweeks: the build gameweeks, explicit (`sampler.sample_squads`'s own contract, §2.9).
        n_squads: squads per gameweek.
        seed: the master seed, required with no default (§2.9, §8.4).
        results_root: where `results.write` lands the run's directory (§7.4).

    Returns:
        A `StartingXIRun` summary.
    """
    sample = sampler.sample_squads(mart, gameweeks, n_squads, seed)

    squad_weeks: list[pd.DataFrame] = []
    ordering_replays: list[pd.DataFrame] = []
    ranker_windows: dict[str, tuple[int, int]] = {}
    for name, rank_fn in rank_fns.items():
        window = rankers.DECLARED_WINDOWS[name]
        result: HarnessResult = harness_run(sample.squads, rank_fn, bench_order, mart, window)
        squad_weeks.append(result.squad_weeks)
        ordering_replays.append(result.ordering_replays)
        ranker_windows[name] = window

    t2 = pd.concat(squad_weeks, ignore_index=True)
    t5 = pd.concat(ordering_replays, ignore_index=True)
    t3 = _assemble_comparisons(t2, t5, rank_fns)

    manifest = results.Manifest(
        mart_pin=asdict(sample.mart_pin),
        bench_order=[name for name, _ in bench_order],
        master_seed=seed,
        squad_set_id=sample.squad_set_id,
        build_gameweeks=list(gameweeks),
        ranker_windows=ranker_windows,
        sampler_diagnostics=_sampler_diagnostics(sample.run_record),
        gameweek_interval=results.GameweekIntervalParams(
            n=uncertainty.N_RESAMPLES, block=uncertainty.BLOCK_GWS, ci_level=uncertainty.CI_LEVEL, seed=uncertainty.SEED
        ),
        squad_interval=results.SquadIntervalParams(
            n=uncertainty.N_RESAMPLES, ci_level=uncertainty.CI_LEVEL, seed=uncertainty.SEED
        ),
    )

    identifier = results.write(t2, t5, t3, manifest, results_root)
    return StartingXIRun(
        run_id=identifier,
        results_dir=results_root / identifier,
        n_squad_weeks=len(t2),
        n_comparisons=len(t3),
    )


def build_and_run(
    *,
    bench_order: BenchOrder = orderings.PRE_REGISTERED_ORDERINGS,
    rank_fns: Mapping[str, RankFn] = rankers.FLOOR_RANKERS,
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    results_root: Path,
    db_path: Path = DB_PATH,
) -> StartingXIRun:
    """Read the mart via `dal/` and run the study against it. The one line that touches `dal/`."""
    return run_study(
        load(db_path).mart,
        bench_order=bench_order,
        rank_fns=rank_fns,
        gameweeks=gameweeks,
        n_squads=n_squads,
        seed=seed,
        results_root=results_root,
    )
