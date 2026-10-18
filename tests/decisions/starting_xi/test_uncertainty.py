"""Tests for `uncertainty.gameweek_block_ci`, the paired gameweek interval `report.py` uses."""

from __future__ import annotations

import inspect
import subprocess
import sys

import numpy as np
import pytest

from decisions.starting_xi.uncertainty import BLOCK_GWS, CI_LEVEL, N_RESAMPLES, SEED, gameweek_block_ci
from model.eval.metrics import block_bootstrap_ci

pytestmark = pytest.mark.unit

N_TEST = 2000


def test_the_signature_defaults_are_the_pre_registered_values() -> None:
    """Pinned here as well as in `PRE_REGISTRATION.yaml`, so a default that drifted from the
    freeze fails in the module that carries it."""
    assert (N_RESAMPLES, CI_LEVEL, SEED, BLOCK_GWS) == (10_000, 0.95, 0, 4)
    parameters = inspect.signature(gameweek_block_ci).parameters
    assert (parameters["n"].default, parameters["block"].default, parameters["seed"].default) == (10_000, 4, 0)
    assert parameters["n_scoreable_gw"].default is inspect.Parameter.empty


def test_g4_fires_on_a_flattened_squad_week_panel() -> None:
    """§10.6's named case: "A flattened panel has `n_squads x n_gw` entries and fails that assertion
    rather than silently producing a number." §10.10.3 turns on this being the only check that
    catches it, since such a series is a 1-D array the input shapes do not distinguish."""
    flattened = np.arange(300 * 35, dtype=float)
    with pytest.raises(ValueError, match="G4"):
        gameweek_block_ci(flattened, n_scoreable_gw=35, n=N_TEST)


def test_g4_fires_on_a_punctured_series() -> None:
    """`archive/METRIC.md` §6.4.3's A2: a gameweek with no surviving row has no per-gameweek mean, so an
    ordering sample's series is shorter than the window. §10.10 keeps the assertion and gives that
    sample its own entry point rather than relaxing it."""
    with pytest.raises(ValueError, match="G4"):
        gameweek_block_ci(np.arange(9, dtype=float), n_scoreable_gw=35, n=N_TEST)


def test_g4_does_not_fire_on_a_full_length_series() -> None:
    rng = np.random.default_rng(3)
    series = rng.normal(size=35)
    lo, hi = gameweek_block_ci(series, n_scoreable_gw=35, n=N_TEST)
    assert lo < hi


def test_the_gameweek_interval_delegates_to_the_call_site_8_2_selects() -> None:
    """§8.2 fixes the call site as `model/eval/metrics.py:79` and requires every argument passed
    explicitly. Asserted as equality with a direct call rather than by patching, so a future
    re-implementation inside this module fails here."""
    rng = np.random.default_rng(5)
    series = rng.normal(size=35)
    assert gameweek_block_ci(series, n_scoreable_gw=35, n=N_TEST, block=4, ci_level=0.95, seed=0) == block_bootstrap_ci(
        series, block=4, n=N_TEST, ci_level=0.95, seed=0
    )


def test_the_gameweek_interval_rejects_a_non_finite_entry() -> None:
    """This module's own check, flagged as an addition rather than one of §10's four.
    `block_bootstrap_draws` strips NaN before resampling, so without it a series could pass G4's
    length check and still present the estimator with fewer values than the window has."""
    series = np.arange(35, dtype=float)
    series[7] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        gameweek_block_ci(series, n_scoreable_gw=35, n=N_TEST)


def test_a_two_dimensional_input_is_rejected_before_g4() -> None:
    with pytest.raises(ValueError, match="1-D"):
        gameweek_block_ci(np.zeros((5, 7)), n_scoreable_gw=35, n=N_TEST)


def test_the_import_closure_is_tier_bs() -> None:
    """§5.1's row forbids `research/`, `serve/`, `operational/` and every Tier A sibling, and §8.2
    permits `model/` because the gameweek interval needs it. Run as a subprocess on
    `test_results.py`'s precedent: this session has already imported all of them, so an in-process
    check would pass against any module."""
    program = (
        "import sys;"
        "import decisions.starting_xi.uncertainty;"
        "banned = ('research', 'serve', 'operational',"
        " 'decisions.starting_xi.harness', 'decisions.starting_xi.sampler',"
        " 'decisions.starting_xi.formations', 'decisions.starting_xi.results');"
        "reached = sorted(m for m in sys.modules if m.startswith(banned));"
        "print(repr(reached));"
        "print('model.eval.metrics' in sys.modules)"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    reached, uses_model = child.stdout.splitlines()
    assert reached == "[]"
    assert uses_model == "True"
