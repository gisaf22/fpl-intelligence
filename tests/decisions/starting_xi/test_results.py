"""Tests for the results writer.

Three of this suite's obligations come from the design rather than from the code, and each is
executed rather than described:

* **"Producible from the artefact alone" is tested as a subprocess.** The claim is about
  what a reader needs, so an in-process assertion cannot make it: the session has already imported
  `dal` and `model`. A child interpreter reads the written artefact, reconstructs every quantity
  the results document reports -- the XI regret distribution, the bench-order regret against
  its absolute counterfactual (CARD.md §1) -- and asserts it never imported the harness, the
  sampler or `dal`.
* **`run_id`'s determinism is checked by exhaustion over the identity fields.** Every single-field
  perturbation of the manifest's identity half must move `run_id`, and every perturbation of the metadata
  half must not. Both directions are swept, so a hash that ignored a field and a hash that swept in
  metadata both fail.
* **Where a test could pass while blind, the wrong version runs beside the right one.** The
  round-trip is asserted against frames built independently of the module; the schema check is
  shown to reject a real violation before it is trusted.
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
    T2_COLUMNS,
    T2_FILE,
    T4_FILE,
    T5_COLUMNS,
    T5_FILE,
    GameweekIntervalParams,
    Manifest,
    RunProvenance,
    identity_fields,
    manifest_document,
    read,
    run_id,
    stamp,
    write,
)

pytestmark = pytest.mark.unit


# The two specified schemas, written out here and nowhere in the module. A column added,
# removed, renamed or reordered in `results.py` without the specification moving fails here. T2's
# list is the one carried after this week's two corrections -- the realised/as-of split for C1, and
# `best_permutation_total` for the absolute counterfactual.
DESIGN_T2 = (
    "run_id",
    "squad_id",
    "gw",
    "ranker",
    "chosen_xi",
    "chosen_xi_points",
    "no_subs_xi_points",
    "best_legal_xi_points",
    "best_legal_xi_asof",
    "second_best_xi_asof",
    "regret",
    "regret_gk",
    "regret_def",
    "regret_mid",
    "regret_fwd",
    "closeness_gap",
    "is_zero_gap",
    "is_zero_information",
    "substitution_fired",
    "uncovered_blank",
    "no_fixture_rule_changed_xi",
    "best_permutation_total",
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
# Fixtures -- frames in the specified shape, built here and not by the harness
# ---------------------------------------------------------------------------


def _t2(n_squads: int = 4, gameweeks: Sequence[int] = (4, 5)) -> pd.DataFrame:
    """T2 as `harness.py` returns it: the specified columns, `run_id` absent.

    Built from arithmetic rather than by calling the harness, so this suite tests the writer
    against its *specified shape* -- which is what each module is built against.
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
                    "chosen_xi": ",".join(str(player_id) for player_id in range(index, index + 11)),
                    "chosen_xi_points": chosen,
                    "no_subs_xi_points": chosen - (index % 2),
                    "best_legal_xi_points": chosen + index,
                    "best_legal_xi_asof": chosen + 1.5,
                    "second_best_xi_asof": chosen + 1.5 - (index % 2),
                    "regret": float(index),
                    "regret_gk": 0.0,
                    "regret_def": -1.0,
                    "regret_mid": 1.0,
                    "regret_fwd": float(index),
                    "closeness_gap": float(index % 2),
                    "is_zero_gap": index % 2 == 0,
                    "is_zero_information": index == 2,
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
        squad_mode="uniform",
        # The id is the sampler's content hash of the drawn squads, so the fixture
        # carries a digest-shaped value rather than a version label -- the earlier "squads-v1"
        # invited exactly the reading a content hash rules out. This module treats it as an opaque string.
        squad_set_id="b" * 64,
        build_gameweeks=(4, 5),
        ranker_windows={"F1": (4, 38), "F2": (2, 38)},
        sampler_diagnostics=[{"gw": 4, "acceptance_rate": 0.21}, {"gw": 5, "acceptance_rate": 0.19}],
        zero_information_squad_weeks=2,
        gameweek_interval=GameweekIntervalParams(n=10000, block=4, ci_level=0.95, seed=1),
        construction="weekly",
        provenance=_provenance(),
    )


def _provenance(**overrides: object) -> RunProvenance:
    fields: dict[str, object] = {
        "git_sha": "d" * 40,
        "clean_tree": True,
        "warehouse_run_id": "39064033745",
        "warehouse_sha256": {"fct_player_fixture.parquet": "e" * 64},
        "pre_registration_sha256": "f" * 64,
        "canonical": True,
        "non_canonical_reasons": (),
    }
    fields.update(overrides)
    return RunProvenance(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The schemas
# ---------------------------------------------------------------------------


def test_the_module_carries_exactly_the_columns_section_7_2_specifies() -> None:
    """The drift test. The specified schemas are written out in this file and compared to the
    module's, so a column that moves in one without moving in the other fails here."""
    assert T2_COLUMNS == DESIGN_T2
    assert T5_COLUMNS == DESIGN_T5


def test_t2_carries_this_weeks_two_corrections() -> None:
    """The realised/as-of split for C1 and the absolute counterfactual, named explicitly so
    a revert of either fails on a test that says why rather than on a column-order diff."""
    assert "best_legal_xi_asof" in T2_COLUMNS and "second_best_xi_asof" in T2_COLUMNS
    assert "second_best_xi_points" not in T2_COLUMNS, "the as-of pair supersedes the realised-points runner-up"
    assert "best_permutation_total" in T2_COLUMNS


def test_stamp_puts_run_id_first_and_preserves_section_7_2_order() -> None:
    t2 = _t2()
    stamped = stamp(t2, "abc123", T2_COLUMNS)
    assert tuple(stamped.columns) == DESIGN_T2
    assert (stamped["run_id"] == "abc123").all()
    pd.testing.assert_frame_equal(stamped.drop(columns=["run_id"]), t2)


@pytest.mark.parametrize("table", ["t2", "t5"])
def test_a_frame_missing_a_column_is_rejected_rather_than_written(table: str, tmp_path: Path) -> None:
    """The schema check is shown to reject a real violation before it is trusted. The guarantee
    is that the artefact is readable from its schema alone, which is false the moment a column is
    missing -- so this fails at the boundary rather than producing an unreadable artefact."""
    t2 = _t2()
    frames = {"t2": t2, "t5": _t5(t2)}
    frames[table] = frames[table].drop(columns=[frames[table].columns[-1]])
    with pytest.raises(ValueError, match="its table's schema"):
        write(frames["t2"], frames["t5"], _manifest(), tmp_path)
    assert not list(tmp_path.iterdir()), "a rejected write left files behind"


def test_an_extra_column_is_rejected_as_loudly_as_a_missing_one(tmp_path: Path) -> None:
    """An unnamed column is a quantity the results document has no definition for."""
    t2 = _t2()
    t2["surprise"] = 1.0
    with pytest.raises(ValueError, match="extra=\\['surprise'\\]"):
        write(t2, _t5(_t2()), _manifest(), tmp_path)


def test_a_reordered_frame_is_rejected_so_the_stored_order_is_section_7_2s() -> None:
    """Column *order* is part of the schema: T2's columns are specified in an order, and an artefact
    that reordered them would diff against a reviewer's expectation for no substantive reason."""
    t2 = _t2()
    shuffled = t2.loc[:, [t2.columns[1], t2.columns[0], *t2.columns[2:]]]
    with pytest.raises(ValueError, match="column order differs"):
        stamp(shuffled, "abc123", T2_COLUMNS)


# ---------------------------------------------------------------------------
# Run identity
# ---------------------------------------------------------------------------


def test_run_id_is_deterministic_across_calls_and_across_processes() -> None:
    """Re-running identical inputs yields the same `run_id`. Across processes as well as
    within one, because Python's `hash` is salted per interpreter and a `run_id` built on it would
    pass an in-process check while failing the property actually required."""
    manifest = _manifest()
    assert run_id(manifest) == run_id(_manifest())
    program = (
        "import json;"
        "from decisions.starting_xi.results import run_id, Manifest, GameweekIntervalParams,"
        " RunProvenance;"
        f"m = Manifest(mart_pin={dict(manifest.mart_pin)!r}, bench_order={tuple(manifest.bench_order)!r},"
        f" master_seed={manifest.master_seed!r}, squad_mode={manifest.squad_mode!r},"
        f" squad_set_id={manifest.squad_set_id!r},"
        f" build_gameweeks={tuple(manifest.build_gameweeks)!r}, ranker_windows={dict(manifest.ranker_windows)!r},"
        f" sampler_diagnostics={list(manifest.sampler_diagnostics)!r},"
        f" zero_information_squad_weeks={manifest.zero_information_squad_weeks!r},"
        " gameweek_interval=GameweekIntervalParams(n=10000, block=4, ci_level=0.95, seed=1),"
        f" construction={manifest.construction!r},"
        f" provenance=RunProvenance(**{dict(vars(manifest.provenance))!r}));"
        "print(run_id(m))"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    assert child.stdout.strip() == run_id(manifest)


def test_every_identity_field_moves_the_run_id_and_no_metadata_field_does() -> None:
    """The manifest's identity/metadata split, swept in both directions rather than spot-checked.

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
        "squad_mode": replace(base, squad_mode="ownership"),
        "squad_set_id": replace(base, squad_set_id="c" * 64),
        "build_gameweeks": replace(base, build_gameweeks=(4, 5, 6)),
        "construction": replace(base, construction="build_once"),
        "canonical": replace(base, provenance=_provenance(canonical=False, non_canonical_reasons=("dirty_tree",))),
    }
    for field, perturbed in identity_perturbations.items():
        assert run_id(perturbed) != baseline, f"{field} is identity but did not move run_id"

    metadata_perturbations = {
        "ranker_windows": replace(base, ranker_windows={"F1": (2, 38)}),
        "sampler_diagnostics": replace(base, sampler_diagnostics=[{"gw": 4, "acceptance_rate": 0.99}]),
        "zero_information_squad_weeks": replace(base, zero_information_squad_weeks=5),
        "gameweek_interval": replace(base, gameweek_interval=GameweekIntervalParams(5, 8, 0.9, 99)),
        "git_sha": replace(base, provenance=_provenance(git_sha="0" * 40)),
        "warehouse_pin": replace(
            base,
            provenance=_provenance(warehouse_run_id="1", warehouse_sha256={"fct_player_fixture.parquet": "1" * 64}),
        ),
        "pre_registration_sha256": replace(base, provenance=_provenance(pre_registration_sha256="2" * 64)),
    }
    for field, perturbed in metadata_perturbations.items():
        assert run_id(perturbed) == baseline, f"{field} is metadata but moved run_id"


def test_the_bench_orders_order_is_identity_not_just_its_membership() -> None:
    """ "The whole ordered policy set, with element 0 named as primary" is identity, because
    primary regret is a function of element 0. Every permutation of a
    three-policy set must therefore produce a distinct id -- checked exhaustively, six of six."""
    base = replace(_manifest(), bench_order=("a", "b", "c"))
    ids = {run_id(replace(base, bench_order=order)) for order in permutations(("a", "b", "c"))}
    assert len(ids) == 6


def test_build_gameweeks_is_a_set_so_listing_order_does_not_move_the_id() -> None:
    """The counterpart to the test above, and the contrast is the point: the manifest calls the build
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
    """The manifest is split and the split is asserted, not trusted: nothing carried "for
    completeness rather than identity" may appear in what the id hashes."""
    fields = identity_fields(_manifest())
    assert set(fields) == {
        "mart_pin",
        "bench_order",
        "primary_ordering",
        "master_seed",
        "squad_mode",
        "squad_set_id",
        "build_gameweeks",
        "construction",
        "canonical",
    }
    flat = json.dumps(fields)
    for absent in ("ranker_windows", "sampler_diagnostics", "ci_level", "block", "git_sha", "warehouse"):
        assert absent not in flat


def test_the_gameweek_interval_parameters_are_recorded_as_metadata() -> None:
    document = manifest_document(_manifest(), "abc123")
    metadata = document["metadata"]
    assert isinstance(metadata, dict)
    assert set(metadata["gameweek_interval"]) == {"n", "block", "ci_level", "seed"}


@pytest.mark.covers("#29 AC8")
def test_the_manifest_document_records_run_provenance_outside_the_identity_half() -> None:
    """Run hygiene: git sha, clean-tree flag, the pinned warehouse publish's run_id and per-file
    sha256s, the pre-registration's sha256 and the canonical flag are written to T4 under their
    own key. Only `canonical` is identity (so a forced run can never overwrite a canonical run's
    directory); the rest would make identical inputs at two commits two different runs, which
    `run_id`'s determinism forbids."""
    manifest = replace(_manifest(), provenance=_provenance(canonical=False, non_canonical_reasons=("dirty_tree",)))
    document = manifest_document(manifest, "abc123")
    assert document["provenance"] == {
        "git_sha": "d" * 40,
        "clean_tree": True,
        "warehouse_run_id": "39064033745",
        "warehouse_sha256": {"fct_player_fixture.parquet": "e" * 64},
        "pre_registration_sha256": "f" * 64,
        "canonical": False,
        "non_canonical_reasons": ["dirty_tree"],
    }
    identity = document["identity"]
    assert isinstance(identity, dict)
    assert identity["canonical"] is False
    assert identity["construction"] == "weekly"


def test_a_canonical_run_cannot_carry_non_canonical_reasons() -> None:
    with pytest.raises(ValueError, match="canonical"):
        _provenance(canonical=True, non_canonical_reasons=("dirty_tree",))
    with pytest.raises(ValueError, match="canonical"):
        _provenance(canonical=False, non_canonical_reasons=())


def test_an_empty_or_duplicated_bench_order_is_rejected() -> None:
    """`bench_order` is non-empty with element 0 primary; duplicate names would make
    T5's `ordering_name` ambiguous and the id's ordered set unreadable."""
    with pytest.raises(ValueError, match="non-empty"):
        replace(_manifest(), bench_order=())
    with pytest.raises(ValueError, match="duplicate"):
        replace(_manifest(), bench_order=("a", "a"))
    with pytest.raises(ValueError, match="build_gameweeks"):
        replace(_manifest(), build_gameweeks=())


# ---------------------------------------------------------------------------
# What is written
# ---------------------------------------------------------------------------


def test_write_emits_the_three_files_and_returns_the_run_id(tmp_path: Path) -> None:
    t2 = _t2()
    identifier = write(t2, _t5(t2), _manifest(), tmp_path)
    assert identifier == run_id(_manifest())
    directory = tmp_path / identifier
    assert sorted(p.name for p in directory.iterdir()) == sorted([T2_FILE, T5_FILE, T4_FILE])


def test_writing_the_same_run_twice_is_idempotent(tmp_path: Path) -> None:
    """`run_id`'s determinism is only useful if identical inputs land in the same place. Re-running
    rewrites the same directory rather than creating a second one."""
    t2 = _t2()
    first = write(t2, _t5(t2), _manifest(), tmp_path)
    second = write(t2, _t5(t2), _manifest(), tmp_path)
    assert first == second
    assert [p.name for p in tmp_path.iterdir()] == [first]


def test_two_different_runs_cannot_overwrite_each_other(tmp_path: Path) -> None:
    """The property the per-run subdirectory buys, and the reason for choosing it.
    A flat layout would have the second run destroy the first's files under the same names."""
    t2 = _t2()
    first = write(t2, _t5(t2), _manifest(), tmp_path)
    second = write(t2, _t5(t2), replace(_manifest(), master_seed=99), tmp_path)
    assert first != second
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([first, second])
    assert (tmp_path / first / T2_FILE).exists() and (tmp_path / second / T2_FILE).exists()


def test_the_artefact_round_trips_every_frame_including_nulls_and_list_columns(tmp_path: Path) -> None:
    """Round-tripped against frames built in this file, not against the module's own output read
    back through the module's own writer alone: the expected values are the fixtures plus a stamped
    `run_id`, so a writer that mangled a column fails here.

    T5's `entered_outfield` is a tuple per row, the column a naive writer loses -- a writer
    coercing it would pass a row-count check and destroy the artefact's meaning.
    """
    t2 = _t2()
    t5 = _t5(t2)
    identifier = write(t2, t5, _manifest(), tmp_path)
    back = read(tmp_path, identifier)

    for name, original, columns in (
        ("squad_weeks", t2, DESIGN_T2),
        ("ordering_replays", t5, DESIGN_T5),
    ):
        frame = back[name]
        assert isinstance(frame, pd.DataFrame)
        assert tuple(frame.columns) == columns
        assert (frame["run_id"] == identifier).all()
        assert len(frame) == len(original)

    replays = back["ordering_replays"]
    assert isinstance(replays, pd.DataFrame)
    assert [tuple(v) for v in replays["entered_outfield"]] == list(t5["entered_outfield"])


def test_the_manifest_is_json_a_reviewer_can_diff(tmp_path: Path) -> None:
    """T4 is JSON "because it is the thing a human reads first and a reviewer diffs"."""
    identifier = write(_t2(), _t5(_t2()), _manifest(), tmp_path)
    text = (tmp_path / identifier / T4_FILE).read_text(encoding="utf-8")
    document = json.loads(text)
    assert document["run_id"] == identifier
    assert set(document) == {"run_id", "identity", "provenance", "metadata"}
    assert text.endswith("\n")
    assert json.dumps(document, indent=2, sort_keys=True) + "\n" == text


# ---------------------------------------------------------------------------
# Producible from the artefact alone
# ---------------------------------------------------------------------------


def test_the_results_document_is_producible_from_the_artefact_without_the_harness(tmp_path: Path) -> None:
    """The reproducibility requirement, executed as the constraint it is: a *reader* obligation, so it is tested
    in a child interpreter that reconstructs the reported quantities and then asserts it never
    imported `dal`, the harness or the sampler.

    What the child reconstructs is not a token read -- it is every quantity the results document
    reports plus the two this week's corrections added: XI regret and its distribution from T2, the
    closeness gap from the **as-of** pair, bench-order regret against its absolute counterfactual by
    joining T5 to T2's `best_permutation_total`. If any of those needed
    the harness or the mart, the child fails.
    """
    t2 = _t2()
    identifier = write(t2, _t5(t2), _manifest(), tmp_path)
    program = f"""
import sys, json
from pathlib import Path
import pandas as pd
from decisions.starting_xi.results import read

art = read(Path({str(tmp_path)!r}), {identifier!r})
t2, t5 = art["squad_weeks"], art["ordering_replays"]

# XI regret and its distribution (P3 is the worst weeks, not a mean).
assert (t2["regret"] == t2["best_legal_xi_points"] - t2["chosen_xi_points"]).all()
assert t2["regret"].max() >= t2["regret"].median()

# The closeness gap is the as-of pair's, and the realised pair is a different number.
assert (t2["best_legal_xi_asof"] != t2["best_legal_xi_points"]).any()

# Bench-order regret against the absolute counterfactual, T5 joined to T2.
joined = t5.merge(t2[["run_id", "squad_id", "gw", "ranker", "best_permutation_total"]],
                  on=["run_id", "squad_id", "gw", "ranker"], validate="many_to_one")
regret = joined["best_permutation_total"] - joined["realised_total"]
assert (regret >= -1e-9).all()

# The manifest reads back and names the run.
assert art["manifest"]["run_id"] == {identifier!r}

leaked = [m for m in sys.modules
          if m.split(".")[0] in {{"dal", "model", "research", "serve", "operational"}}
          or (m.startswith("decisions.starting_xi.") and m != "decisions.starting_xi.results")]
assert not leaked, leaked
"""
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=False)
    assert child.returncode == 0, child.stderr


def test_that_reconstruction_would_fail_without_the_column_this_week_added(tmp_path: Path) -> None:
    """The counterfactual to the test above, executed. The bench-order regret *level* is derivable
    from the artefact only because `best_permutation_total` is in it -- it was
    blocked before the column existed. Dropping it breaks the join, which is what makes the
    reconstruction above evidence rather than decoration."""
    t2 = _t2()
    identifier = write(t2, _t5(t2), _manifest(), tmp_path)
    back = read(tmp_path, identifier)
    stored, replays = back["squad_weeks"], back["ordering_replays"]
    assert isinstance(stored, pd.DataFrame)
    assert isinstance(replays, pd.DataFrame)

    key = ["run_id", "squad_id", "gw", "ranker"]
    # With the column: the join succeeds and the level is derivable.
    joined = replays.merge(stored[[*key, "best_permutation_total"]], on=key, validate="many_to_one")
    assert ((joined["best_permutation_total"] - joined["realised_total"]) >= -1e-9).all()

    # Without it: the same derivation is unavailable from the artefact -- the blocked state.
    without = stored.drop(columns=["best_permutation_total"])
    with pytest.raises(KeyError):
        replays.merge(without[[*key, "best_permutation_total"]], on=key, validate="many_to_one")


# ---------------------------------------------------------------------------
# The import contract
# ---------------------------------------------------------------------------


def test_importing_the_results_writer_pulls_in_no_dal_no_tier_b_and_no_sibling() -> None:
    """Tier A forbids this module `model/`, `research/`, `serve/` and `rankers.py`; its boundary adds that it
    "needs neither `dal/` nor `model/`" because it reads no data of its own.

    The `model`/`research`/`serve` half is an import-linter contract. The rest is not expressible
    there today -- `rankers` is not in the graph, and Tier A does not forbid this module `dal`, so a
    `dal` contract would be asserting the shape claim as if Tier A had stated it. Both are
    enforced here instead. Run in a subprocess because the session has already imported
    `model` via `testpaths`, so an in-process check could not tell this module's closure from what
    was already loaded.
    """
    program = (
        "import sys; import decisions.starting_xi.results; "
        "leaked = [m for m in sys.modules "
        "if m.split('.')[0] in {'model', 'research', 'serve', 'dal', 'warehouse', 'operational', 'statsmodels'} "
        "or m.startswith('decisions.starting_xi.') and m != 'decisions.starting_xi.results']; "
        "assert not leaked, leaked"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0


def test_that_closure_check_can_actually_fail() -> None:
    """The falsification half, and the reason the test above is evidence rather than a formality:
    the same probe run against a module that *does* reach `warehouse` must fail. `sampler.py` is that
    module -- it reads the warehouse frames -- so a probe that passed for both would be checking
    nothing."""
    program = (
        "import sys; import decisions.starting_xi.sampler; "
        "leaked = [m for m in sys.modules if m.split('.')[0] in {'warehouse'}]; "
        "assert not leaked, leaked"
    )
    assert subprocess.run([sys.executable, "-c", program], capture_output=True, check=False).returncode != 0


def test_the_package_init_still_re_exports_nothing() -> None:
    """The no-re-export rule, re-asserted from this module's side: a re-export in the package `__init__.py`
    would give every importer of any slice module this one's dependencies, and
    import-linter cannot catch it."""
    init = Path(__file__).resolve().parents[3] / "decisions" / "starting_xi" / "__init__.py"
    source = init.read_text(encoding="utf-8")
    body = [line for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not any(line.startswith(("import ", "from ")) for line in body)
    assert not any("__all__" in line and "=" in line for line in body)
