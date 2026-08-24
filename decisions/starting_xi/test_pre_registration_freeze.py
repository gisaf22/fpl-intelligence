"""Freeze test for `PRE_REGISTRATION.yaml` -- `DESIGN.md` §7.4.

**What this pins, and why a test rather than a note.** §7.4 requires the parameters fixed before the
first harness run to live in `PRE_REGISTRATION.yaml`, pinned by a test, following the
`evidence.yaml` + freeze-test pattern `INVENTORY.md` §2.9 identifies as the repository's only
mechanism making a pre-registration enforceable rather than aspirational. Unlike that pattern --
which hardcodes expected values into the test itself -- most of what this file pins already has a
canonical value somewhere in code (`rankers.DECLARED_WINDOWS`, `uncertainty.N_RESAMPLES`, ...), so
this test reads the YAML and asserts it against those values directly. A future change to a Final
constant that is not mirrored here fails loudly instead of silently drifting from the frozen file.

**Two fields have no canonical code constant and are pinned as literals instead**, exactly as
`test_uncertainty.py::test_the_signature_defaults_are_the_pre_registered_values` already pins
`(10_000, 0.95, 0, 4)` as a literal rather than importing them from a second location:
`population.squads_per_gameweek` (300 is `run_study`'s own required argument, with no default and
no Final anywhere -- §0.16, §8.4) and `resampling_scheme.construction` (weekly resampling is a
structural property of the sampler, not a named constant -- §0.16).

**`significance.requires_both_intervals_exclude_zero` is pinned behaviourally.** §0.15's "S2 is
satisfied only if both ... intervals exclude zero" is a rule inside
`operational.starting_xi._evaluate_bar`, not a constant; this test calls it directly with one
interval excluding zero and the other not, and asserts `crit_significance` is False -- the case an
OR-of-two-intervals implementation would pass and an AND-of-two-intervals one must fail.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest
import yaml

from decisions.starting_xi import orderings, rankers, results, uncertainty
from operational import starting_xi

pytestmark = pytest.mark.unit

PRE_REGISTRATION_PATH = Path(__file__).parent / "PRE_REGISTRATION.yaml"


@pytest.fixture(scope="module")
def pre_registration() -> dict[str, Any]:
    payload: dict[str, Any] = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())
    return payload


def test_pre_registration_file_exists() -> None:
    """§7.4's one genuine "before": the file must exist before the first harness run."""
    assert PRE_REGISTRATION_PATH.exists()


def test_floor_rankers_match_declared_windows(pre_registration: dict[str, Any]) -> None:
    """§0.12, §6.3: the three floor rankers and their declared windows, against
    `rankers.DECLARED_WINDOWS` directly -- the source `rankers.py` states this literal is derived
    from and frozen against (F1's GW4 tied to `WARMUP_GW` by `test_rankers.py`'s own drift test)."""
    frozen = pre_registration["floor_rankers"]
    assert set(frozen) == set(rankers.FLOOR_RANKERS) == set(rankers.DECLARED_WINDOWS)
    for name, window in rankers.DECLARED_WINDOWS.items():
        assert frozen[name] == list(window)


def test_bench_ordering_matches_pre_registered_set(pre_registration: dict[str, Any]) -> None:
    """§4.12, §5.4.1: `orderings.PRE_REGISTERED_ORDERINGS`, ordered, element 0 primary."""
    assert pre_registration["bench_ordering"] == [name for name, _ in orderings.PRE_REGISTERED_ORDERINGS]


def test_build_gameweeks_match_study_scope(pre_registration: dict[str, Any]) -> None:
    """§0.7, §0.16: GW2-38, against `rankers.STUDY_FIRST_GW` / `STUDY_LAST_GW` -- this slice's own
    study-level scope constants ("No repository constant carries it" per `rankers.py`)."""
    build_gameweeks = pre_registration["population"]["build_gameweeks"]
    assert (build_gameweeks["first_gw"], build_gameweeks["last_gw"]) == (
        rankers.STUDY_FIRST_GW,
        rankers.STUDY_LAST_GW,
    )


def test_squads_per_gameweek_is_the_pre_registered_literal(pre_registration: dict[str, Any]) -> None:
    """§0.16: 300 per gameweek. No Final constant carries this value anywhere in code -- `n_squads`
    is `run_study`'s required argument with no default -- so it is pinned here as a literal."""
    assert pre_registration["population"]["squads_per_gameweek"] == 300


def test_resampling_scheme_matches_the_squad_interval_estimator(pre_registration: dict[str, Any]) -> None:
    """§0.16, §10.1, §10.3: weekly resampling (a literal -- no code constant names the construction),
    stratified by `gw`, no block for the squad interval, `block = 4` for the gameweek interval
    against `uncertainty.BLOCK_GWS`."""
    scheme = pre_registration["resampling_scheme"]
    assert scheme["construction"] == "weekly"
    assert scheme["squad_interval_stratified_by"] == "gw"
    assert scheme["squad_interval_block"] is None
    assert "block" not in inspect.signature(uncertainty.squad_stratified_ci).parameters
    assert scheme["gameweek_interval_block"] == uncertainty.BLOCK_GWS


def test_intervals_match_uncertainty_constants(pre_registration: dict[str, Any]) -> None:
    """§10.1, §10.8: `n`, `ci_level`, `seed`, against `uncertainty.py`'s own Final constants."""
    intervals = pre_registration["intervals"]
    assert intervals["n"] == uncertainty.N_RESAMPLES
    assert intervals["ci_level"] == uncertainty.CI_LEVEL
    assert intervals["seed"] == uncertainty.SEED


def test_master_seed_matches_the_slice_wide_seed_convention(pre_registration: dict[str, Any]) -> None:
    """§8.4: "seed = 0 at every call site in the slice" -- one convention governing both the two
    intervals' seed and the sampler's master seed, so the frozen master seed is checked against the
    same `uncertainty.SEED` the intervals use."""
    assert pre_registration["master_seed"] == uncertainty.SEED


def test_success_criteria_are_the_three_t3_criterion_columns(pre_registration: dict[str, Any]) -> None:
    """§0.15: S1/S2/S3, against the `crit_*` columns `results.T3_COLUMNS` actually carries."""
    assert set(pre_registration["success_criteria"]) == {"crit_direction", "crit_significance", "crit_materiality"}
    assert set(pre_registration["success_criteria"]) <= set(results.T3_COLUMNS)


def test_significance_requires_both_intervals_to_exclude_zero(pre_registration: dict[str, Any]) -> None:
    """§0.15: "S2 is satisfied only if both ... intervals exclude zero." Behavioural rather than a
    constant, so pinned by calling `_evaluate_bar` with one interval excluding zero and the other
    straddling it -- an AND-of-both implementation must fail this case; an OR would pass it."""
    assert pre_registration["significance"]["requires_both_intervals_exclude_zero"] is True

    *_, crit_significance, _materiality, _passed = starting_xi._evaluate_bar(
        floor_mean_regret=1.5,
        candidate_mean_regret=1.0,
        ci_squads=(0.1, 0.9),  # excludes zero
        ci_gw=(-0.1, 0.9),  # straddles zero
    )
    assert crit_significance is False


def test_materiality_threshold_matches_operational_constant(pre_registration: dict[str, Any]) -> None:
    """§0.15: 10%, relative to the floor's own mean regret, against
    `operational.starting_xi.MATERIALITY_THRESHOLD`."""
    materiality = pre_registration["materiality"]
    assert materiality["threshold"] == starting_xi.MATERIALITY_THRESHOLD
    assert materiality["relative_to"] == "floor_mean_regret"
