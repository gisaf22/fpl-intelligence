"""Tests for the results writer -- `DESIGN.md` §7.1, §7.2, §7.3, §7.4, §7.8, §5.1.

Three of this suite's obligations come from the design rather than from the code, and each is
executed rather than described:

* **§7.1's "producible from the artefact alone" is tested as a subprocess.** The claim is about
  what a reader needs, so an in-process assertion cannot make it: the session has already imported
  `dal` and `model`. A child interpreter reads the written artefact, reconstructs every quantity
  the results document reports -- §0.1's regret distribution, §4.4's ordering regret against
  §0.10's absolute counterfactual, §4.6's counts -- and asserts it never imported the harness, the
  sampler or `dal`.
* **§7.3's determinism is checked by exhaustion over the identity fields.** Every single-field
  perturbation of §7.3's identity half must move `run_id`, and every perturbation of the metadata
  half must not. Both directions are swept, so a hash that ignored a field and a hash that swept in
  metadata both fail.
* **Where a test could pass while blind, the wrong version runs beside the right one.** The
  round-trip is asserted against frames built independently of the module; the schema check is
  shown to reject a real violation before it is trusted; and the T1 gap is asserted to raise rather
  than being noted in a docstring.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from itertools import permutations
from pathlib import Path

import pandas as pd
import pytest

from decisions.starting_xi.results import (
    STATUSES,
    T1_COLUMNS,
    T2_COLUMNS,
    T2_FILE,
    T3_COLUMNS,
    T3_FILE,
    T4_FILE,
    T5_COLUMNS,
    T5_FILE,
    GameweekIntervalParams,
    Manifest,
    SquadIntervalParams,
    T1HasNoProducer,
    identity_fields,
    manifest_document,
    read,
    run_id,
    stamp,
    write,
    write_t1,
)

pytestmark = pytest.mark.unit


# `DESIGN.md` §7.2's four schemas, written out here and nowhere in the module. A column added,
# removed, renamed or reordered in `results.py` without §7.2 moving fails here. T2's list is the
# one §7.2 carries after this week's two corrections -- the realised/as-of split for C1, and
# `best_permutation_total` for §0.10's absolute counterfactual.
DESIGN_T1 = (
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
DESIGN_T2 = (
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
DESIGN_T3 = (
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
DESIGN_T5 = (
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


# ---------------------------------------------------------------------------
# Fixtures -- frames in §7.2's shape, built here and not by the harness
# ---------------------------------------------------------------------------


def _t2(n_squads: int = 4, gameweeks: Sequence[int] = (4, 5)) -> pd.DataFrame:
    """T2 as `harness.py` returns it: §7.2's columns, `run_id` absent.

    Built from arithmetic rather than by calling the harness, so this suite tests the writer
    against §7.2's *specified shape* -- which is what §5.1.1 says each module is built against.
    """
    rows = []
    for gw in gameweeks:
        for index in range(n_squads):
            chosen = 40.0 + index + gw
            rows.append(
                {
                    "squad_id": f"gw{gw:02d}-{index:04d}",
                    "gw": gw,
                    "ranker": "F_test",
                    "chosen_xi_points": chosen,
                    "best_legal_xi_points": chosen + index,
                    "best_legal_xi_asof": chosen + 1.5,
                    "second_best_xi_asof": chosen + 1.5 - (index % 2),
                    "regret": float(index),
                    "closeness_gap": float(index % 2),
                    "is_zero_gap": index % 2 == 0,
                    "substitution_fired": index != 0,
                    "uncovered_blank": index == 3,
                    "no_fixture_rule_changed_xi": index == 1,
                    "best_permutation_total": chosen + (index % 3),
                }
            )
    return pd.DataFrame(rows, columns=[c for c in DESIGN_T2 if c != "run_id"])


def _t5(t2: pd.DataFrame, orderings: Sequence[str] = ("by_rank", "reversed")) -> pd.DataFrame:
    """T5 as `harness.py` returns it: one row per squad-week per candidate ordering."""
    rows = []
    for row in t2.itertuples(index=False):
        for index, name in enumerate(orderings):
            rows.append(
                {
                    "squad_id": row.squad_id,
                    "gw": row.gw,
                    "ranker": row.ranker,
                    "ordering_name": name,
                    "is_primary": index == 0,
                    "substitution_fired": row.substitution_fired,
                    "realised_total": row.chosen_xi_points if index == 0 else row.chosen_xi_points - 1.0,
                    "entered_gk": None,
                    "entered_outfield": (7, 9) if index == 0 else (9,),
                }
            )
    return pd.DataFrame(rows, columns=[c for c in DESIGN_T5 if c != "run_id"])


def _t3() -> pd.DataFrame:
    """T3, already assembled -- including §4.6's B2, which §7.2.1 computes at assembly."""
    rows = [
        {
            "comparison_id": "c1",
            "rankers": "F1|F2",
            "window_first_gw": 4,
            "window_last_gw": 5,
            "n_scoreable_gw": 2,
            "floor_ranker": "F1",
            "floor_mean_regret": 2.0,
            "candidate_mean_regret": 1.5,
            "abs_reduction": 0.5,
            "rel_reduction": 0.25,
            "ci_squads_lo": 0.1,
            "ci_squads_hi": 0.9,
            "ci_gw_lo": 0.05,
            "ci_gw_hi": 0.95,
            "crit_direction": True,
            "crit_significance": True,
            "crit_materiality": True,
            "passed": True,
            "status": "evaluated",
            "status_reason": None,
            "n_zero_gap_excluded": 4,
            "substitution_count": 6,
            "uncovered_blank_count": 2,
            "ordering_relevant_count": 3,
            "no_fixture_rule_count": 1,
        },
        {
            "comparison_id": "c2",
            "rankers": "F1|F3",
            "window_first_gw": 4,
            "window_last_gw": 5,
            "n_scoreable_gw": 2,
            "floor_ranker": "F1",
            "floor_mean_regret": 2.0,
            "candidate_mean_regret": 2.0,
            "abs_reduction": 0.0,
            "rel_reduction": 0.0,
            # §7.5: intervals null and `crit_significance` null -- **not** false -- when the
            # comparison could not be evaluated. The writer must round-trip null as null.
            "ci_squads_lo": None,
            "ci_squads_hi": None,
            "ci_gw_lo": None,
            "ci_gw_hi": None,
            "crit_direction": False,
            "crit_significance": None,
            "crit_materiality": False,
            "passed": None,
            "status": "underpowered",
            "status_reason": "fewer than four scoreable gameweeks",
            "n_zero_gap_excluded": 4,
            "substitution_count": 6,
            "uncovered_blank_count": 2,
            "ordering_relevant_count": 0,
            "no_fixture_rule_count": 1,
        },
    ]
    return pd.DataFrame(rows, columns=[c for c in DESIGN_T3 if c != "run_id"])


def _manifest() -> Manifest:
    return Manifest(
        mart_pin={
            "slice_sha256": "a" * 64,
            "slice_rows": 1234,
            "gameweeks": (2, 3, 4, 5),
            "columns": ("player_id", "gw"),
            "mart_rows": 9999,
            "mart_gw_span": (1, 38),
        },
        bench_order=("by_rank", "reversed"),
        master_seed=0,
        # §5.3.2 fixes the id as the sampler's content hash of the drawn squads, so the fixture
        # carries a digest-shaped value rather than a version label -- the earlier "squads-v1"
        # invited exactly the reading §5.3.2 rejects. This module treats it as an opaque string.
        squad_set_id="b" * 64,
        build_gameweeks=(4, 5),
        ranker_windows={"F1": (4, 38), "F2": (2, 38)},
        sampler_diagnostics=[{"gw": 4, "acceptance_rate": 0.21}, {"gw": 5, "acceptance_rate": 0.19}],
        gameweek_interval=GameweekIntervalParams(n=10000, block=4, ci_level=0.95, seed=1),
        squad_interval=SquadIntervalParams(n=10000, ci_level=0.95, seed=2),
    )


# ---------------------------------------------------------------------------
# §7.2 -- the schemas
# ---------------------------------------------------------------------------


def test_the_module_carries_exactly_the_columns_section_7_2_specifies() -> None:
    """The drift test. §7.2's four schemas are written out in this file and compared to the
    module's, so a column that moves in one without moving in the other fails here."""
    assert T1_COLUMNS == DESIGN_T1
    assert T2_COLUMNS == DESIGN_T2
    assert T3_COLUMNS == DESIGN_T3
    assert T5_COLUMNS == DESIGN_T5


def test_t2_carries_this_weeks_two_corrections() -> None:
    """§0.8's realised/as-of split for C1 and §0.10's absolute counterfactual, named explicitly so
    a revert of either fails on a test that says why rather than on a column-order diff."""
    assert "best_legal_xi_asof" in T2_COLUMNS and "second_best_xi_asof" in T2_COLUMNS
    assert "second_best_xi_points" not in T2_COLUMNS, "§7.2 supersedes the realised-points runner-up"
    assert "best_permutation_total" in T2_COLUMNS


def test_stamp_puts_run_id_first_and_preserves_section_7_2_order() -> None:
    t2 = _t2()
    stamped = stamp(t2, "abc123", T2_COLUMNS)
    assert tuple(stamped.columns) == DESIGN_T2
    assert (stamped["run_id"] == "abc123").all()
    pd.testing.assert_frame_equal(stamped.drop(columns=["run_id"]), t2)


@pytest.mark.parametrize("table", ["t2", "t5", "t3"])
def test_a_frame_missing_a_column_is_rejected_rather_than_written(table: str, tmp_path: Path) -> None:
    """The schema check is shown to reject a real violation before it is trusted. §7.1's guarantee
    is that the artefact is readable from §7.2 alone, which is false the moment a column is
    missing -- so this fails at the boundary rather than producing an unreadable artefact."""
    t2, t3 = _t2(), _t3()
    t5 = _t5(t2)
    frames = {"t2": t2, "t5": t5, "t3": t3}
    frames[table] = frames[table].drop(columns=[frames[table].columns[-1]])
    with pytest.raises(ValueError, match=r"§7\.2's schema"):
        write(frames["t2"], frames["t5"], frames["t3"], _manifest(), tmp_path)
    assert not list(tmp_path.iterdir()), "a rejected write left files behind"


def test_an_extra_column_is_rejected_as_loudly_as_a_missing_one(tmp_path: Path) -> None:
    """An unnamed column is a quantity the results document has no definition for."""
    t2 = _t2()
    t2["surprise"] = 1.0
    with pytest.raises(ValueError, match="extra=\\['surprise'\\]"):
        write(t2, _t5(_t2()), _t3(), _manifest(), tmp_path)


def test_a_reordered_frame_is_rejected_so_the_stored_order_is_section_7_2s() -> None:
    """Column *order* is part of the schema: §7.2 lists T2's columns in an order, and an artefact
    that reordered them would diff against a reviewer's expectation for no substantive reason."""
    t2 = _t2()
    shuffled = t2.loc[:, [t2.columns[1], t2.columns[0], *t2.columns[2:]]]
    with pytest.raises(ValueError, match="column order differs"):
        stamp(shuffled, "abc123", T2_COLUMNS)


def test_a_status_outside_section_7_5s_three_is_rejected(tmp_path: Path) -> None:
    """§7.5 defines three values and turns on the difference between null and false. A fourth
    would leave an unevaluated comparison indistinguishable from a failed one."""
    t3 = _t3()
    t3.loc[0, "status"] = "ok"
    with pytest.raises(ValueError, match="status values"):
        write(_t2(), _t5(_t2()), t3, _manifest(), tmp_path)
    assert STATUSES == {"evaluated", "underpowered", "not_evaluable"}


# ---------------------------------------------------------------------------
# §7.3 -- run identity
# ---------------------------------------------------------------------------


def test_run_id_is_deterministic_across_calls_and_across_processes() -> None:
    """§7.3: re-running identical inputs yields the same `run_id`. Across processes as well as
    within one, because Python's `hash` is salted per interpreter and a `run_id` built on it would
    pass an in-process check while failing the property §7.3 actually states."""
    manifest = _manifest()
    assert run_id(manifest) == run_id(_manifest())
    program = (
        "import json;"
        "from decisions.starting_xi.results import run_id, Manifest, GameweekIntervalParams, SquadIntervalParams;"
        f"m = Manifest(mart_pin={dict(manifest.mart_pin)!r}, bench_order={tuple(manifest.bench_order)!r},"
        f" master_seed={manifest.master_seed!r}, squad_set_id={manifest.squad_set_id!r},"
        f" build_gameweeks={tuple(manifest.build_gameweeks)!r}, ranker_windows={dict(manifest.ranker_windows)!r},"
        f" sampler_diagnostics={list(manifest.sampler_diagnostics)!r},"
        " gameweek_interval=GameweekIntervalParams(n=10000, block=4, ci_level=0.95, seed=1),"
        " squad_interval=SquadIntervalParams(n=10000, ci_level=0.95, seed=2));"
        "print(run_id(m))"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    assert child.stdout.strip() == run_id(manifest)


def test_every_identity_field_moves_the_run_id_and_no_metadata_field_does() -> None:
    """§7.3's table, swept in both directions rather than spot-checked.

    A hash that silently ignored an identity field would let two genuinely different runs share an
    id; a hash that swept in a metadata field would give one run two ids across cosmetic changes.
    Both are failures and both are exercised here -- the identity half exhaustively, one field at a
    time, and the metadata half likewise.
    """
    base = _manifest()
    baseline = run_id(base)

    identity_perturbations = {
        "mart_pin": replace(base, mart_pin={**base.mart_pin, "slice_rows": 4321}),
        "bench_order_membership": replace(base, bench_order=("by_rank", "other")),
        "master_seed": replace(base, master_seed=1),
        "squad_set_id": replace(base, squad_set_id="c" * 64),
        "build_gameweeks": replace(base, build_gameweeks=(4, 5, 6)),
    }
    for field, perturbed in identity_perturbations.items():
        assert run_id(perturbed) != baseline, f"{field} is identity per §7.3 but did not move run_id"

    metadata_perturbations = {
        "ranker_windows": replace(base, ranker_windows={"F1": (2, 38)}),
        "sampler_diagnostics": replace(base, sampler_diagnostics=[{"gw": 4, "acceptance_rate": 0.99}]),
        "gameweek_interval": replace(base, gameweek_interval=GameweekIntervalParams(5, 8, 0.9, 99)),
        "squad_interval": replace(base, squad_interval=SquadIntervalParams(5, 0.9, 99)),
    }
    for field, perturbed in metadata_perturbations.items():
        assert run_id(perturbed) == baseline, f"{field} is metadata per §7.3 but moved run_id"


def test_the_bench_orders_order_is_identity_not_just_its_membership() -> None:
    """§7.3 makes "the whole ordered policy set, with element 0 named as primary" identity, and
    §4.9 gives the reason: primary regret is a function of element 0. Every permutation of a
    three-policy set must therefore produce a distinct id -- checked exhaustively, six of six."""
    base = replace(_manifest(), bench_order=("a", "b", "c"))
    ids = {run_id(replace(base, bench_order=order)) for order in permutations(("a", "b", "c"))}
    assert len(ids) == 6


def test_build_gameweeks_is_a_set_so_listing_order_does_not_move_the_id() -> None:
    """The counterpart to the test above, and the contrast is the point: §7.3 calls the build
    gameweeks a *set*, so the order a caller lists them in is not a property of the run, while the
    bench ordering's order is. A hash treating both the same way fails one of the two tests."""
    base = _manifest()
    assert run_id(replace(base, build_gameweeks=(5, 4))) == run_id(base)
    assert run_id(replace(base, build_gameweeks=(4, 5, 4))) == run_id(base)


def test_the_mart_pin_hashes_the_same_whether_its_sequences_are_tuples_or_lists() -> None:
    """The pin is taken as a mapping rather than as `sampler.MartPin` (the module docstring gives
    the reason), so the digest must not depend on how a caller spelled its sequences."""
    base = _manifest()
    as_lists = {key: list(value) if isinstance(value, tuple) else value for key, value in base.mart_pin.items()}
    assert run_id(replace(base, mart_pin=as_lists)) == run_id(base)


def test_identity_fields_holds_the_identity_half_and_nothing_from_the_metadata_half() -> None:
    """§7.3 splits the manifest and the split is asserted, not trusted: nothing carried "for
    completeness rather than identity" may appear in what the id hashes."""
    fields = identity_fields(_manifest())
    assert set(fields) == {
        "mart_pin",
        "bench_order",
        "primary_ordering",
        "master_seed",
        "squad_set_id",
        "build_gameweeks",
    }
    flat = json.dumps(fields)
    for absent in ("ranker_windows", "sampler_diagnostics", "ci_level", "block"):
        assert absent not in flat


def test_the_two_interval_parameter_sets_stay_apart_and_only_one_carries_a_block() -> None:
    """§7.3: recorded per interval, "because there are two sets and they differ". The squad
    interval has no `block` -- squads are unordered (§10.1) -- and merging them would leave a
    reader unable to tell which parameters produced which of T3's two column pairs."""
    document = manifest_document(_manifest(), "abc123")
    metadata = document["metadata"]
    assert isinstance(metadata, dict)
    assert set(metadata["gameweek_interval"]) == {"n", "block", "ci_level", "seed"}
    assert set(metadata["squad_interval"]) == {"n", "ci_level", "seed"}
    assert "block" not in metadata["squad_interval"]


def test_an_empty_or_duplicated_bench_order_is_rejected() -> None:
    """§5.4 makes `bench_order` non-empty with element 0 primary; duplicate names would make
    T5's `ordering_name` ambiguous and the id's ordered set unreadable."""
    with pytest.raises(ValueError, match="non-empty"):
        replace(_manifest(), bench_order=())
    with pytest.raises(ValueError, match="duplicate"):
        replace(_manifest(), bench_order=("a", "a"))
    with pytest.raises(ValueError, match="build_gameweeks"):
        replace(_manifest(), build_gameweeks=())


# ---------------------------------------------------------------------------
# §7.4 -- what is written
# ---------------------------------------------------------------------------


def test_write_emits_the_four_files_it_can_and_returns_the_run_id(tmp_path: Path) -> None:
    t2 = _t2()
    identifier = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    assert identifier == run_id(_manifest())
    directory = tmp_path / identifier
    assert sorted(p.name for p in directory.iterdir()) == sorted([T2_FILE, T3_FILE, T5_FILE, T4_FILE])


def test_writing_the_same_run_twice_is_idempotent(tmp_path: Path) -> None:
    """§7.3's determinism is only useful if identical inputs land in the same place. Re-running
    rewrites the same directory rather than creating a second one."""
    t2 = _t2()
    first = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    second = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    assert first == second
    assert [p.name for p in tmp_path.iterdir()] == [first]


def test_two_different_runs_cannot_overwrite_each_other(tmp_path: Path) -> None:
    """The property the per-run subdirectory buys, and the reason for choosing it (§7.4 is silent).
    A flat layout would have the second run destroy the first's files under the same names."""
    t2 = _t2()
    first = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    second = write(t2, _t5(t2), _t3(), replace(_manifest(), master_seed=99), tmp_path)
    assert first != second
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([first, second])
    assert (tmp_path / first / T2_FILE).exists() and (tmp_path / second / T2_FILE).exists()


def test_the_artefact_round_trips_every_frame_including_nulls_and_list_columns(tmp_path: Path) -> None:
    """Round-tripped against frames built in this file, not against the module's own output read
    back through the module's own writer alone: the expected values are the fixtures plus a stamped
    `run_id`, so a writer that mangled a column fails here.

    Two columns are the ones a naive writer loses. T5's `entered_outfield` is a tuple per row, and
    T3's null intervals are §7.5's "null is not false" -- a writer coercing either would pass a
    row-count check and destroy the artefact's meaning.
    """
    t2 = _t2()
    t5, t3 = _t5(t2), _t3()
    identifier = write(t2, t5, t3, _manifest(), tmp_path)
    back = read(tmp_path, identifier)

    for name, original, columns in (
        ("squad_weeks", t2, DESIGN_T2),
        ("ordering_replays", t5, DESIGN_T5),
        ("comparisons", t3, DESIGN_T3),
    ):
        frame = back[name]
        assert isinstance(frame, pd.DataFrame)
        assert tuple(frame.columns) == columns
        assert (frame["run_id"] == identifier).all()
        assert len(frame) == len(original)

    replays = back["ordering_replays"]
    assert isinstance(replays, pd.DataFrame)
    assert [tuple(v) for v in replays["entered_outfield"]] == list(t5["entered_outfield"])

    comparisons = back["comparisons"]
    assert isinstance(comparisons, pd.DataFrame)
    underpowered = comparisons.loc[comparisons["comparison_id"] == "c2"].iloc[0]
    assert pd.isna(underpowered["ci_squads_lo"]) and pd.isna(underpowered["ci_gw_hi"])
    assert underpowered["crit_significance"] is None or pd.isna(underpowered["crit_significance"])
    assert bool(comparisons.loc[comparisons["comparison_id"] == "c1"].iloc[0]["crit_significance"]) is True


def test_a_writer_coercing_nulls_to_false_would_fail_that_round_trip(tmp_path: Path) -> None:
    """§7.5's rule executed as a counterfactual rather than cited: "Null is not false". A
    comparison that could not be evaluated must not read as one that failed, so the wrong version
    -- filling `crit_significance` -- is constructed here and shown to differ from what was
    written."""
    t3 = _t3()
    identifier = write(_t2(), _t5(_t2()), t3, _manifest(), tmp_path)
    stored = read(tmp_path, identifier)["comparisons"]
    assert isinstance(stored, pd.DataFrame)

    # What was written: null survives as null on the underpowered row, true stays true on the other.
    underpowered = stored.loc[stored["comparison_id"] == "c2", "crit_significance"].iloc[0]
    evaluated = stored.loc[stored["comparison_id"] == "c1", "crit_significance"].iloc[0]
    assert pd.isna(underpowered), "null was coerced; §7.5 turns on null not being false"
    assert bool(evaluated) is True

    # The wrong version, constructed and shown to differ: a writer filling nulls would make the
    # two rows indistinguishable from "evaluated and failed", which is what §7.5 forbids.
    coerced = stored["crit_significance"].fillna(False)
    assert coerced.loc[stored["comparison_id"] == "c2"].iloc[0] is not underpowered
    assert not coerced.isna().any()
    assert stored["crit_significance"].isna().any(), "the artefact carries no null to distinguish"


def test_the_manifest_is_json_a_reviewer_can_diff(tmp_path: Path) -> None:
    """§7.4: T4 is JSON "because it is the thing a human reads first and a reviewer diffs"."""
    identifier = write(_t2(), _t5(_t2()), _t3(), _manifest(), tmp_path)
    text = (tmp_path / identifier / T4_FILE).read_text(encoding="utf-8")
    document = json.loads(text)
    assert document["run_id"] == identifier
    assert set(document) == {"run_id", "identity", "metadata"}
    assert text.endswith("\n")
    assert json.dumps(document, indent=2, sort_keys=True) + "\n" == text


# ---------------------------------------------------------------------------
# §7.1 -- producible from the artefact alone
# ---------------------------------------------------------------------------


def test_the_results_document_is_producible_from_the_artefact_without_the_harness(tmp_path: Path) -> None:
    """§7.1's requirement, executed as the constraint it is: a *reader* obligation, so it is tested
    in a child interpreter that reconstructs the reported quantities and then asserts it never
    imported `dal`, the harness or the sampler.

    What the child reconstructs is not a token read -- it is every quantity §7.1 names plus the two
    this week's corrections added: §0.1's regret and its distribution from T2, §0.8's closeness gap
    from the **as-of** pair, §4.4's ordering regret against §0.10's absolute counterfactual by
    joining T5 to T2's `best_permutation_total`, and §4.6's counts from T3. If any of those needed
    the harness or the mart, the child fails.
    """
    t2 = _t2()
    identifier = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    program = f"""
import sys, json
from pathlib import Path
import pandas as pd
from decisions.starting_xi.results import read

art = read(Path({str(tmp_path)!r}), {identifier!r})
t2, t5, t3 = art["squad_weeks"], art["ordering_replays"], art["comparisons"]

# §0.1 -- regret and its distribution (P3 is the worst weeks, not a mean).
assert (t2["regret"] == t2["best_legal_xi_points"] - t2["chosen_xi_points"]).all()
assert t2["regret"].max() >= t2["regret"].median()

# §0.8 -- the closeness gap is the as-of pair's, and the realised pair is a different number.
assert (t2["best_legal_xi_asof"] != t2["best_legal_xi_points"]).any()

# §4.4 / §0.10 -- ordering regret against the absolute counterfactual, T5 joined to T2.
joined = t5.merge(t2[["run_id", "squad_id", "gw", "ranker", "best_permutation_total"]],
                  on=["run_id", "squad_id", "gw", "ranker"], validate="many_to_one")
regret = joined["best_permutation_total"] - joined["realised_total"]
assert (regret >= -1e-9).all()

# §4.6 -- the counts, read off T3 where assembly wrote them.
assert set(t3["status"]) <= {{"evaluated", "underpowered", "not_evaluable"}}
assert int(t3["ordering_relevant_count"].sum()) >= 0

# §7.3 -- the manifest reads back and names the run.
assert art["manifest"]["run_id"] == {identifier!r}

leaked = [m for m in sys.modules
          if m.split(".")[0] in {{"dal", "model", "research", "serve", "operational"}}
          or (m.startswith("decisions.starting_xi.") and m != "decisions.starting_xi.results")]
assert not leaked, leaked
"""
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr


def test_that_reconstruction_would_fail_without_the_column_this_week_added(tmp_path: Path) -> None:
    """The counterfactual to the test above, executed. §0.10's ordering-regret *level* is derivable
    from the artefact only because `best_permutation_total` is in it -- §9.2 recorded exactly this
    as blocked before the column existed. Dropping it breaks the join, which is what makes the
    reconstruction above evidence rather than decoration."""
    t2 = _t2()
    identifier = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    back = read(tmp_path, identifier)
    stored, replays = back["squad_weeks"], back["ordering_replays"]
    assert isinstance(stored, pd.DataFrame)
    assert isinstance(replays, pd.DataFrame)

    key = ["run_id", "squad_id", "gw", "ranker"]
    # With the column: the join succeeds and the level is derivable.
    joined = replays.merge(stored[[*key, "best_permutation_total"]], on=key, validate="many_to_one")
    assert ((joined["best_permutation_total"] - joined["realised_total"]) >= -1e-9).all()

    # Without it: the same derivation is unavailable from the artefact -- §9.2's blocked state.
    without = stored.drop(columns=["best_permutation_total"])
    with pytest.raises(KeyError):
        replays.merge(without[[*key, "best_permutation_total"]], on=key, validate="many_to_one")


# ---------------------------------------------------------------------------
# §5.1 -- T1 has no producer
# ---------------------------------------------------------------------------


def test_t1_is_specified_but_no_module_produces_it_and_the_writer_says_so() -> None:
    """§7.2 specifies T1 and §5.1's row says this module "writes T1-T5" -- but its *Takes* column
    does not hand it T1, and §7.8 forbids it reading data of its own. `DESIGN.md`'s Provenance
    already records the same gap from the harness side and states that assigning T1's producer is
    a §5.1 pass. Asserted as a raise rather than left as a comment, so the gap cannot be closed by
    accident with an empty frame that satisfies a schema check and carries none of the three
    findings §7.1 says T1 exists to make representable."""
    with pytest.raises(T1HasNoProducer):
        write_t1(pd.DataFrame())
    assert issubclass(T1HasNoProducer, NotImplementedError)


def test_the_writer_does_not_silently_emit_a_t1_file(tmp_path: Path) -> None:
    """The other half: `write` must not invent one either."""
    t2 = _t2()
    identifier = write(t2, _t5(t2), _t3(), _manifest(), tmp_path)
    names = [p.name for p in (tmp_path / identifier).iterdir()]
    assert not any("selection" in name for name in names)
    assert len(names) == 4


# ---------------------------------------------------------------------------
# §7.8 / §5.1 -- the import contract
# ---------------------------------------------------------------------------


def test_importing_the_results_writer_pulls_in_no_dal_no_tier_b_and_no_sibling() -> None:
    """§5.1 forbids this module `model/`, `research/`, `serve/` and `rankers.py`; §7.8 adds that it
    "needs neither `dal/` nor `model/`" because it reads no data of its own.

    The `model`/`research`/`serve` half is an import-linter contract. The rest is not expressible
    there today -- `rankers` is not in the graph, and §5.1 does not forbid this module `dal`, so a
    `dal` contract would be asserting §7.8's shape claim as if §5.1 had stated it. Both are
    enforced here instead. Run in a subprocess for §5.6's reason: the session has already imported
    `model` via `testpaths`, so an in-process check could not tell this module's closure from what
    was already loaded.
    """
    program = (
        "import sys; import decisions.starting_xi.results; "
        "leaked = [m for m in sys.modules "
        "if m.split('.')[0] in {'model', 'research', 'serve', 'dal', 'operational', 'statsmodels'} "
        "or m.startswith('decisions.starting_xi.') and m != 'decisions.starting_xi.results']; "
        "assert not leaked, leaked"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0


def test_that_closure_check_can_actually_fail() -> None:
    """The falsification half, and the reason the test above is evidence rather than a formality:
    the same probe run against a module that *does* reach `dal` must fail. `sampler.py` is that
    module -- §5.1 permits it the mart -- so a probe that passed for both would be checking
    nothing."""
    program = (
        "import sys; import decisions.starting_xi.sampler; "
        "leaked = [m for m in sys.modules if m.split('.')[0] in {'dal'}]; "
        "assert not leaked, leaked"
    )
    assert subprocess.run([sys.executable, "-c", program], capture_output=True, check=False).returncode != 0


def test_the_package_init_still_re_exports_nothing() -> None:
    """§5.6's rule, re-asserted from this module's side: a re-export in the package `__init__.py`
    would give every importer of any slice module this one's dependencies, and `INVENTORY.md`
    §2.11 records that import-linter cannot catch it."""
    source = Path(__file__).with_name("__init__.py").read_text(encoding="utf-8")
    body = [line for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not any(line.startswith(("import ", "from ")) for line in body)
    assert not any("__all__" in line and "=" in line for line in body)
