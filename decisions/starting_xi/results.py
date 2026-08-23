"""The results writer -- `DESIGN.md` §5.1, §7.2, §7.3, §7.4, §7.8.

**It serialises and it does not compute.** §7.8 states the boundary: this module writes frames it
is handed and reads no data of its own, so it needs neither `dal/` nor `model/`. Nothing here
re-derives a quantity `harness.py` or `formations.py` already produced, and nothing here computes
one that §7.2.1 assigns to assembly -- ordering-relevance and §4.6's B2 arrive inside T3's
`ordering_relevant_count`, already counted, because §5.1 has this module take *the comparison
results* rather than build them.

**The one exception, and §7.3 assigns it here explicitly.** `run_id` is a deterministic hash of the
run's identifying fields, and `harness.py` deliberately emits neither it nor the column that carries
it. Computing that hash and stamping the column onto every table is this module's job and the whole
of what it computes.

**Import closure: stdlib and pandas.** Tier A (§5.1), so no `model/`, no `research/`, no `serve/`,
and never `rankers.py`. **No `dal/` either** -- §7.8 makes that a property of the module's shape
rather than of §5.1's forbidden list, and `test_results.py` asserts it in a subprocess.

**No sibling slice module is imported, and one candidate was declined on merit.** §5.1.1 permits
this module its Tier A siblings and records that none is needed. The tempting edge is
`sampler.MartPin`, since §7.3 makes the pin an identity field -- but `sampler.py` imports `dal/`,
so taking the pin as a typed sibling object would pull `dal/` into this module's closure and
contradict §7.8. The pin is taken as a mapping of its own fields instead, which is the shape §5.1.1
says each module is built against: "the specified shape rather than the other module's code".
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

# ---------------------------------------------------------------------------
# §7.2's schemas, written out here because this module is where they become files
# ---------------------------------------------------------------------------

# Column order is §7.2's, `run_id` first, and it is a contract rather than a preference: §7.1
# requires the results document be producible from the artefact alone, which is only true if the
# artefact carries the columns §7.2 names. A frame missing one is rejected at this boundary rather
# than written and discovered later.
T1_COLUMNS: Final[tuple[str, ...]] = (
    "run_id",
    "squad_id",
    "gw",
    "ranker",
    "player_id",
    "position",
    "score",
    "rank",
    "is_unrankable",
    "no_fixture",
    "selected",
    "bench_slot",
    "entered_as_sub",
    "minutes_recorded",
    "points",
)
T2_COLUMNS: Final[tuple[str, ...]] = (
    "run_id",
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
T3_COLUMNS: Final[tuple[str, ...]] = (
    "run_id",
    "comparison_id",
    "rankers",
    "window_first_gw",
    "window_last_gw",
    "n_scoreable_gw",
    "floor_ranker",
    "floor_mean_regret",
    "candidate_mean_regret",
    "abs_reduction",
    "rel_reduction",
    "ci_squads_lo",
    "ci_squads_hi",
    "ci_gw_lo",
    "ci_gw_hi",
    "crit_direction",
    "crit_significance",
    "crit_materiality",
    "passed",
    "status",
    "status_reason",
    "n_zero_gap_excluded",
    "substitution_count",
    "uncovered_blank_count",
    "ordering_relevant_count",
    "no_fixture_rule_count",
)
T5_COLUMNS: Final[tuple[str, ...]] = (
    "run_id",
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

# §7.4: T1-T3 and T5 as parquet, T4 as JSON. The stems are §7.2's table names.
T2_FILE: Final[str] = "squad_weeks.parquet"
T3_FILE: Final[str] = "comparisons.parquet"
T5_FILE: Final[str] = "ordering_replays.parquet"
T4_FILE: Final[str] = "manifest.json"

# §7.5's three values. A `status` outside them would make the null-is-not-false rule unreadable.
STATUSES: Final[frozenset[str]] = frozenset({"evaluated", "underpowered", "not_evaluable"})


class T1HasNoProducer(NotImplementedError):
    """Raised by `write_t1`, which exists only to name the gap rather than paper over it.

    §7.2 specifies **T1 — `selections`**, one row per (run, squad, gameweek, ranker, player), and
    §7.4 has it written as parquet alongside the rest. §5.1's row for this module says it "writes
    T1-T5", but its *Takes* column names only the per-squad-week records, the per-ordering records,
    the comparison results and the manifest fields -- T1 is not among them, and §7.8 forbids this
    module reading data of its own to make up the difference.

    `DESIGN.md`'s Provenance already records the same finding from the harness side: §5.1's
    `harness.py` row returns T2 and T5 only and names no producer for T1, and it states that
    `results.py` is not the producer either because it serialises frames it is handed. Assigning
    T1's producer is a §5.1 pass. Until that pass runs, no module in the slice can emit T1, so this
    one raises rather than writing an empty or fabricated frame that would satisfy a schema check
    while carrying none of the three findings §7.1 says T1 exists to make representable.
    """


# ---------------------------------------------------------------------------
# §7.3's manifest -- T4
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameweekIntervalParams:
    """§8.2's interval: `n`, `block`, `ci_level`, `seed`."""

    n: int
    block: int
    ci_level: float
    seed: int


@dataclass(frozen=True)
class SquadIntervalParams:
    """§10.1's interval: `n`, `ci_level`, `seed`, and **no** `block` -- squads are unordered.

    Two dataclasses rather than one with an optional `block`, because §7.3 requires the parameters
    be "recorded per interval, because there are two sets and they differ", and states the cost of
    merging them: a reader could not tell which parameters produced which of T3's two column pairs.
    A single type with a nullable field would leave that distinction to a convention; two types
    make it unfakeable.
    """

    n: int
    ci_level: float
    seed: int


@dataclass(frozen=True)
class Manifest:
    """§7.3's run manifest, split into what identifies a run and what merely accompanies it.

    **The identity half** is what `run_id` hashes: the mart pin, the whole ordered bench-ordering
    policy set with element 0 primary, the master seed, the squad-set id, and the build gameweek
    set. **The metadata half** -- ranker windows, sampler diagnostics, both interval parameter sets
    -- is carried "for completeness rather than identity" (§7.3) and is excluded from the hash.

    **Two of §7.3's identity rows are not fields here, and their own reasons say why.** The
    *window* and the *floor ranker* are listed in §7.3's table as identity, each annotated **"per
    comparison, in T3"**: §0.13 re-determines the floor per comparison on the intersection of every
    ranker in it, and §7.3 states that "recording 'the floor' once at run level would be wrong". So
    T3 carries them per row, as §7.2's T3 schema does. They are also not hashable into a run's
    identity even in principle -- §0.13 determines the floor from the run's own results, so a
    `run_id` depending on it could not be computed before the run it identifies. Flagged in this
    module's report rather than resolved here: whether §7.3 intends the hash to span T3's
    per-comparison fields is a §7.3 question.
    """

    mart_pin: Mapping[str, object]
    bench_order: Sequence[str]
    master_seed: int
    squad_set_id: str
    build_gameweeks: Sequence[int]
    ranker_windows: Mapping[str, tuple[int, int]]
    sampler_diagnostics: Sequence[Mapping[str, object]]
    gameweek_interval: GameweekIntervalParams
    squad_interval: SquadIntervalParams

    def __post_init__(self) -> None:
        if not self.bench_order:
            raise ValueError("bench_order must be non-empty; element 0 is the primary ordering (DESIGN.md §5.4)")
        if len(set(self.bench_order)) != len(self.bench_order):
            raise ValueError(f"bench_order carries duplicate policy names: {list(self.bench_order)}")
        if not self.build_gameweeks:
            raise ValueError("build_gameweeks must be non-empty (DESIGN.md §7.3)")


def identity_fields(manifest: Manifest) -> dict[str, object]:
    """§7.3's identity half, as the exact structure `run_id` hashes.

    Separated from the hash itself so a caller -- and `test_results.py` -- can see what went into
    an id without recomputing it, and so the metadata half is visibly absent rather than absent by
    omission somewhere inside a digest.

    `bench_order` keeps its **order**: §7.3 makes the whole ordered set identity, element 0 named
    as primary, so two runs comparing the same policies in a different order are different runs.
    `build_gameweeks` is sorted and deduplicated, because it is a *set* in §7.3's sense and the
    order a caller happens to list it in is not a property of the run.
    """
    return {
        "mart_pin": _canonical(manifest.mart_pin),
        "bench_order": list(manifest.bench_order),
        "primary_ordering": manifest.bench_order[0],
        "master_seed": int(manifest.master_seed),
        "squad_set_id": str(manifest.squad_set_id),
        "build_gameweeks": sorted({int(gw) for gw in manifest.build_gameweeks}),
    }


def run_id(manifest: Manifest) -> str:
    """§7.3's deterministic hash of the identifying fields.

    Deterministic in the sense §7.3 requires -- re-running identical inputs yields the same id --
    which needs a canonical serialisation and not merely a stable hash function: `json.dumps` with
    sorted keys and no whitespace variance, digested with SHA-256 and truncated to 16 hex
    characters. Truncation is presentational; 64 bits is far beyond the collision exposure of a
    handful of one-off runs.
    """
    payload = json.dumps(identity_fields(manifest), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _canonical(value: object) -> object:
    """A JSON-serialisable form of a manifest value, with mappings key-sorted at every depth.

    The mart pin arrives as a mapping rather than a `sampler.MartPin` (see the module docstring),
    so its tuples -- `gameweeks`, `columns`, `mart_gw_span` -- have to survive to the digest in a
    form that does not depend on whether the caller passed a tuple or a list.
    """
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, str | bytes):
        return value.decode() if isinstance(value, bytes) else value
    if isinstance(value, Iterable):
        return [_canonical(item) for item in value]
    return value


def manifest_document(manifest: Manifest, identifier: str) -> dict[str, object]:
    """T4's JSON body: the id, the identity half, and the metadata half, kept apart.

    §7.4 makes T4 "the thing a human reads first and a reviewer diffs", which is the reason the two
    halves are nested under separate keys rather than flattened: a diff then shows at a glance
    whether what moved was identity -- in which case `run_id` moved too -- or merely accompanying
    detail.
    """
    return {
        "run_id": identifier,
        "identity": identity_fields(manifest),
        "metadata": {
            "ranker_windows": {name: list(window) for name, window in manifest.ranker_windows.items()},
            "sampler_diagnostics": [_canonical(row) for row in manifest.sampler_diagnostics],
            "gameweek_interval": {
                "n": manifest.gameweek_interval.n,
                "block": manifest.gameweek_interval.block,
                "ci_level": manifest.gameweek_interval.ci_level,
                "seed": manifest.gameweek_interval.seed,
            },
            "squad_interval": {
                "n": manifest.squad_interval.n,
                "ci_level": manifest.squad_interval.ci_level,
                "seed": manifest.squad_interval.seed,
            },
        },
    }


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def stamp(frame: pd.DataFrame, identifier: str, columns: Sequence[str]) -> pd.DataFrame:
    """Add `run_id` and put the frame in §7.2's column order.

    §7.2 keys every table on `run` and `harness.py` emits neither the value nor the column -- §7.3
    makes the id a hash of the run's identifying fields, which this module owns. Stamping it here
    is the one computation §7.8's boundary admits.

    Raises:
        ValueError: if the frame does not carry exactly §7.2's columns for its table, `run_id`
            aside. Extra columns fail as loudly as missing ones: a column the schema does not name
            is a quantity the results document has no definition for, and §7.1's guarantee is that
            the artefact is readable from §7.2 alone.
    """
    expected = tuple(column for column in columns if column != "run_id")
    got = tuple(frame.columns)
    if got != expected:
        missing = [column for column in expected if column not in got]
        extra = [column for column in got if column not in expected]
        detail = "column order differs" if not missing and not extra else f"missing={missing}, extra={extra}"
        raise ValueError(f"frame does not match DESIGN.md §7.2's schema: {detail}")
    if "run_id" in got:  # pragma: no cover - unreachable while `expected` excludes it
        raise ValueError("frame already carries run_id; results.py stamps it (DESIGN.md §7.3)")
    stamped = frame.copy()
    stamped.insert(0, "run_id", identifier)
    return stamped


def _check_statuses(comparisons: pd.DataFrame) -> None:
    """§7.5's three values, and nothing else.

    Checked rather than assumed because §7.5's rule -- "Null is not false" -- is only legible if
    `status` is one of the three it defines. A fourth value would leave a reader unable to tell an
    unevaluated comparison from a failed one, which is the exact confusion §7.5 exists to prevent.
    """
    unknown = sorted({str(value) for value in comparisons["status"]} - STATUSES)
    if unknown:
        raise ValueError(f"T3 carries status values §7.5 does not define: {unknown}")


def write_t1(*_: object, **__: object) -> None:
    """T1 has no producer. See `T1HasNoProducer`.

    Present as a named, raising entry point rather than absent, so that a caller reaching for T1
    gets §5.1's open gap and its routing instead of an `AttributeError` that reads like a typo.
    """
    raise T1HasNoProducer(T1HasNoProducer.__doc__)


def write(
    squad_weeks: pd.DataFrame,
    ordering_replays: pd.DataFrame,
    comparisons: pd.DataFrame,
    manifest: Manifest,
    root: Path,
) -> str:
    """Write the run's artefact under `root` and return its `run_id` (§5.1, §7.4).

    Args:
        squad_weeks: §7.2's T2, as `harness.py` returns it -- without `run_id`.
        ordering_replays: §7.2's T5, likewise.
        comparisons: §7.2's T3, already assembled. Its derived fields -- `ordering_relevant_count`
            above all -- are computed at assembly (§7.2.1) and this module never recomputes one:
            §5.1 has it take *the comparison results*, and §7.8 forbids it computing its own.
        manifest: §7.3's fields. `run_id` is hashed from the identity half.
        root: the results directory, `decisions/starting_xi/results/` in the repository (§7.4).

    Returns:
        The `run_id`, per §5.1's row.

    Raises:
        ValueError: if any frame departs from §7.2's schema, or if T3 carries a `status` outside
            §7.5's three.

    **T1 is not written, and its absence is a documented gap rather than an omission here** --
    §5.1's *Takes* column does not hand this module T1 and no module in the slice produces it. See
    `T1HasNoProducer`.

    **The per-run subdirectory is this module's reading of §7.4, and §7.4 does not state it.**
    §7.4 fixes the directory and the formats and is silent on whether two runs share files. The id
    is used as a subdirectory because §7.3 makes it deterministic *so that re-running identical
    inputs yields the same id*, which is only useful if identical inputs land in the same place and
    different inputs cannot overwrite each other. A flat layout would make a second run either
    destroy the first or silently accumulate rows into a file §7.2 describes as one run's. Flagged
    in this module's report as a §7.4 question.
    """
    identifier = run_id(manifest)
    _check_statuses(comparisons)

    t2 = stamp(squad_weeks, identifier, T2_COLUMNS)
    t5 = stamp(ordering_replays, identifier, T5_COLUMNS)
    t3 = stamp(comparisons, identifier, T3_COLUMNS)

    directory = root / identifier
    directory.mkdir(parents=True, exist_ok=True)
    t2.to_parquet(directory / T2_FILE, index=False)
    t5.to_parquet(directory / T5_FILE, index=False)
    t3.to_parquet(directory / T3_FILE, index=False)
    (directory / T4_FILE).write_text(
        json.dumps(manifest_document(manifest, identifier), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return identifier


def read(root: Path, identifier: str) -> dict[str, object]:
    """Read one run's artefact back -- the other half of §7.1's requirement.

    §7.1 requires the results document be producible from the artefact **alone**, without
    re-running the harness. A writer alone cannot demonstrate that; a reader that touches neither
    `dal/` nor the harness can, and `test_results.py` uses this to reconstruct every quantity the
    results document reports in a subprocess that never imports either.

    Returns the three frames under their §7.2 table names and the manifest document, as read.
    """
    directory = root / identifier
    return {
        "squad_weeks": pd.read_parquet(directory / T2_FILE),
        "ordering_replays": pd.read_parquet(directory / T5_FILE),
        "comparisons": pd.read_parquet(directory / T3_FILE),
        "manifest": json.loads((directory / T4_FILE).read_text(encoding="utf-8")),
    }
