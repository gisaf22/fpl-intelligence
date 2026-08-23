"""Tests for the two paired intervals -- `DESIGN.md` §5.1, §8.2, §10, §10.10.

Four of this suite's obligations come from the design rather than from the code:

* **Every guard is tested in both directions.** §10.10.1 sorts §10's four preconditions into those
  that hold on every caller (G1, G2) and those scoped to the primary comparison's dimensions
  (G3, G4). A test that only showed each firing would pass equally well against a module that
  rejected everything, so each guard is also shown **not** to fire on the input §10.10 says it must
  admit -- and G3 and G4 are shown not to live in the shared core, which is the structural content
  of §10.10.5's selection rather than a comment about it.
* **§10.5's two oracles are executed, not described.** The stratified interval must be strictly
  narrower than a flat bootstrap on the same rows with the gap growing in the induced
  between-gameweek offset, and the single-stratum case must equal an ordinary bootstrap of a mean.
  Both reference implementations are written here rather than imported, so a defect shared with the
  estimator cannot hide.
* **The §10.5 correction is asserted as arithmetic.** §10.5 claimed a thin stratum "contributes
  proportionate weight to the grand mean and proportionate noise to the replicate". At `n_g = 1`
  the second half is false -- the stratum redraws identically and contributes none -- which is
  `METRIC.md` §6.4.3's A1 and which `DESIGN.md`'s Provenance records as a real prior error in the
  document. It is pinned here so it cannot be reintroduced as an assumption.
* **Tier B's import closure is checked in a child interpreter**, on `test_results.py`'s precedent:
  the session has already imported everything, so an in-process assertion cannot make the claim.
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi.uncertainty import (
    BLOCK_GWS,
    CI_LEVEL,
    N_RESAMPLES,
    PANEL_COLUMNS,
    SEED,
    BenchOrderTreatmentUnselected,
    _stratified_resample,
    bench_order_ci,
    gameweek_block_ci,
    squad_stratified_ci,
)
from model.eval.metrics import block_bootstrap_ci

pytestmark = pytest.mark.unit

# Small enough to keep the suite fast, large enough that a percentile is not an artefact of a
# handful of draws. §10.8's pre-registered 10,000 is asserted as a default, not run here.
N_TEST = 2000


def _panel(rows: list[tuple[int, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(PANEL_COLUMNS))


def _balanced_panel(*, n_gw: int = 8, per_gw: int = 25, offset: float = 0.0, seed: int = 7) -> pd.DataFrame:
    """A balanced panel with a deliberately induced between-gameweek offset -- §10.5's first oracle."""
    rng = np.random.default_rng(seed)
    rows = [
        (gw, f"s{gw}_{squad}", offset * index + float(rng.normal(0.0, 1.0)))
        for index, gw in enumerate(range(4, 4 + n_gw))
        for squad in range(per_gw)
    ]
    return _panel(rows)


def _flat_bootstrap_ci(values: np.ndarray, *, n: int, ci_level: float, seed: int) -> tuple[float, float]:
    """The unstratified draw over the pooled rows -- U3, written here as §10.5's oracle reference."""
    rng = np.random.default_rng(seed)
    pooled = np.asarray(values, dtype=float)
    draws = np.array([rng.choice(pooled, size=len(pooled), replace=True).mean() for _ in range(n)])
    alpha = (1.0 - ci_level) / 2.0
    return (float(np.percentile(draws, 100 * alpha)), float(np.percentile(draws, 100 * (1 - alpha))))


def _width(interval: tuple[float, float]) -> float:
    return interval[1] - interval[0]


# ---------------------------------------------------------------------------
# G1 -- one row per (gw, squad_id). §10.5. Transfers (§10.10.1), so it lives in the core.
# ---------------------------------------------------------------------------


def test_g1_fires_on_a_duplicated_squad_week() -> None:
    """§10.5: a panel with two rows at one `(gw, squad_id)` is a §2.8 build bug whose only symptom
    downstream would be a wrongly narrow interval."""
    panel = _panel([(4, "a", 1.0), (4, "a", 2.0), (5, "b", 3.0)])
    with pytest.raises(ValueError, match="G1"):
        squad_stratified_ci(panel, n_scoreable_gw=2, n=N_TEST)


def test_g1_lives_in_the_core_so_every_caller_inherits_it() -> None:
    """§10.10.1 records G1 as transferring to a B2-filtered subpanel unchanged, and §10.10.4 puts
    the guards that transfer in the shared core. Asserted against the core directly, because that
    is what a future bench-order entry point calls."""
    panel = _panel([(4, "a", 1.0), (4, "a", 2.0)])
    with pytest.raises(ValueError, match="G1"):
        _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)


def test_g1_is_the_pair_check_10_5_specifies_not_2_8s_stronger_property() -> None:
    """§10.5 specifies "one row per `(gw, squad_id)`", which is weaker than §2.8's "a `squad_id`
    appears at exactly one `gw`". A squad recurring across gameweeks therefore passes.

    Pinned as specified rather than hardened: §10.3 cites §2.8 as the reason U3's first half is gone
    by construction, so the estimator asserting only the pair leaves that half unenforced here.
    Reported as a gap rather than closed by widening a guard this pass does not own."""
    panel = _panel([(4, "a", 1.0), (5, "a", 2.0)])
    lo, hi = squad_stratified_ci(panel, n_scoreable_gw=2, n=N_TEST)
    assert np.isfinite([lo, hi]).all()


# ---------------------------------------------------------------------------
# G2 -- the gw column is required. §10.6. Transfers (§10.10.1), so it lives in the core.
# ---------------------------------------------------------------------------


def test_g2_fires_when_the_gw_column_is_absent() -> None:
    """§10.6: under §10.3 the draw is *within* stratum, so a caller who dropped `gw` would get a
    flat bootstrap that runs cleanly and returns a wrongly narrow interval."""
    panel = _panel([(4, "a", 1.0), (5, "b", 2.0)]).drop(columns=["gw"])
    with pytest.raises(ValueError, match="G2"):
        squad_stratified_ci(panel, n_scoreable_gw=2, n=N_TEST)


def test_g2_lives_in_the_core_so_every_caller_inherits_it() -> None:
    """As G1: §10.10.4 places the presence check in the core because it holds on every caller."""
    panel = _panel([(4, "a", 1.0), (5, "b", 2.0)]).drop(columns=["gw"])
    with pytest.raises(ValueError, match="G2"):
        _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)


def test_a_panel_missing_gw_raises_g2_rather_than_g3() -> None:
    """The two are not the same guard (§10.6's closing paragraph, as §10.10 splits it). A panel with
    no `gw` at all must name the presence failure, not the stratum-count one."""
    panel = _panel([(4, "a", 1.0), (5, "b", 2.0)]).drop(columns=["gw"])
    with pytest.raises(ValueError, match="G2"):
        squad_stratified_ci(panel, n_scoreable_gw=35, n=N_TEST)


# ---------------------------------------------------------------------------
# G3 -- >1 distinct gw when the window has >1. §10.6. Does NOT transfer (§10.10.1: A1, A3).
# ---------------------------------------------------------------------------


def test_g3_fires_on_a_constant_stratum_key_over_a_multi_gameweek_window() -> None:
    """§10.6: the case G2's presence check cannot see -- the column is there and carries one value,
    which is a flat bootstrap wearing U1's name."""
    panel = _panel([(4, f"s{i}", float(i)) for i in range(20)])
    with pytest.raises(ValueError, match="G3"):
        squad_stratified_ci(panel, n_scoreable_gw=35, n=N_TEST)


def test_g3_does_not_fire_when_the_window_is_itself_one_gameweek() -> None:
    """§10.6 conditions the assertion on the window: "more than one distinct `gw` **whenever the
    comparison window does**". §10.5's second oracle is exactly this case."""
    panel = _panel([(4, f"s{i}", float(i)) for i in range(20)])
    lo, hi = squad_stratified_ci(panel, n_scoreable_gw=1, n=N_TEST)
    assert lo < hi


def test_g3_does_not_fire_when_exclusions_leave_fewer_gameweeks_than_the_window() -> None:
    """The condition is ">1 when the window has >1", not equality, and §10.5 gives the reason: "an
    empty stratum is simply a gameweek absent from the panel rather than a degenerate draw"."""
    panel = _panel([(gw, f"s{gw}_{i}", float(i)) for gw in (4, 9, 30) for i in range(5)])
    lo, hi = squad_stratified_ci(panel, n_scoreable_gw=35, n=N_TEST)
    assert lo < hi


def test_g3_does_not_live_in_the_core_which_is_10_10s_selection_made_structural() -> None:
    """The single most load-bearing test of §10.10.5.

    A single-occupied-gameweek panel on a wide window is what `METRIC.md` §6.4.3's A1 and A3 make
    the **expected** occupancy for a B2-filtered ordering sample. §10.10 decides that G3 stays in
    the primary entry point rather than becoming a caller-supplied parameter, which is only
    meaningful if the shared core admits the call. If G3 ever migrated into the core, the
    bench-order path would inherit a guard §10.10.1 says does not transfer, and this fails."""
    panel = _panel([(4, f"s{i}", float(i)) for i in range(20)])
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert lo < hi


# ---------------------------------------------------------------------------
# G4 -- series length == the scoreable-gameweek count. §10.6. Does NOT transfer (§10.10.1: A2).
# ---------------------------------------------------------------------------


def test_g4_fires_on_a_flattened_squad_week_panel() -> None:
    """§10.6's named case: "A flattened panel has `n_squads x n_gw` entries and fails that assertion
    rather than silently producing a number." §10.10.3 turns on this being the only check that
    catches it, since such a series is a 1-D array the input shapes do not distinguish."""
    flattened = np.arange(300 * 35, dtype=float)
    with pytest.raises(ValueError, match="G4"):
        gameweek_block_ci(flattened, n_scoreable_gw=35, n=N_TEST)


def test_g4_fires_on_a_punctured_series() -> None:
    """`METRIC.md` §6.4.3's A2: a gameweek with no surviving row has no per-gameweek mean, so an
    ordering sample's series is shorter than the window. §10.10 keeps the assertion and gives that
    sample its own entry point rather than relaxing it."""
    with pytest.raises(ValueError, match="G4"):
        gameweek_block_ci(np.arange(9, dtype=float), n_scoreable_gw=35, n=N_TEST)


def test_g4_does_not_fire_on_a_full_length_series() -> None:
    rng = np.random.default_rng(3)
    series = rng.normal(size=35)
    lo, hi = gameweek_block_ci(series, n_scoreable_gw=35, n=N_TEST)
    assert lo < hi


def test_g4_does_not_apply_to_the_squad_path() -> None:
    """§10.10.1 homes G4 in the gameweek function alone. The squad panel's row count is
    `n_squads x n_gw` by construction and must not be checked against the gameweek count."""
    panel = _balanced_panel(n_gw=8, per_gw=25)
    assert len(panel) == 200
    lo, hi = squad_stratified_ci(panel, n_scoreable_gw=8, n=N_TEST)
    assert lo < hi


# ---------------------------------------------------------------------------
# §10.5's thin-stratum correction -- zero variance at n_g = 1, not "proportionate noise"
# ---------------------------------------------------------------------------


def test_a_singleton_stratum_contributes_exactly_zero_variance() -> None:
    """`METRIC.md` §6.4.3's A1, and the correction `DESIGN.md`'s Provenance records: a stratum of
    one row "is redrawn identically in every replicate. It carries its full weight into the mean and
    **zero** variance into the interval."

    §10.5 previously said such a stratum "contributes proportionate ... noise to the replicate",
    which is false at `n_g = 1`. Pinned as exact equality, not a tolerance."""
    panel = _panel([(4, "a", 7.25)])
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert (lo, hi) == (7.25, 7.25)


def test_an_all_singleton_panel_has_zero_width_despite_real_spread() -> None:
    """The A1 failure made visible. Every stratum is a singleton, the values differ by orders of
    magnitude, and the interval is still exactly zero-wide -- which is the "too narrow by an amount
    that grows with how many there are" property, in its limiting case."""
    panel = _panel([(gw, f"s{gw}", value) for gw, value in zip(range(4, 10), [-100.0, 0.5, 3.0, 40.0, -7.0, 900.0])])
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert hi - lo == 0.0
    assert lo == pytest.approx(float(np.mean([-100.0, 0.5, 3.0, 40.0, -7.0, 900.0])))


def test_noise_is_not_proportionate_to_stratum_weight() -> None:
    """The correction stated as the comparison that exposes it. The same twenty values, the same
    grand mean, distributed two ways: twenty singleton strata contribute **zero** noise, one stratum
    of twenty contributes real noise. Under the withdrawn "proportionate noise" reading the two
    would differ in degree; they differ in kind."""
    values = [float(v) for v in range(20)]
    singletons = _panel([(4 + i, f"s{i}", v) for i, v in enumerate(values)])
    one_stratum = _panel([(4, f"s{i}", v) for i, v in enumerate(values)])

    assert _width(_stratified_resample(singletons, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)) == 0.0
    assert _width(_stratified_resample(one_stratum, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)) > 0.0


def test_a_two_row_stratum_does_contribute_noise() -> None:
    """The boundary is at one, not at "thin". §10.5's sentence is correct from `n_g = 2` up."""
    panel = _panel([(4, "a", 1.0), (4, "b", 3.0)])
    assert _width(_stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)) > 0.0


# ---------------------------------------------------------------------------
# §10.5's two oracles
# ---------------------------------------------------------------------------


def test_oracle_stratified_is_strictly_narrower_than_flat_and_the_gap_grows_with_the_offset() -> None:
    """§10.5's first oracle, verbatim: "the stratified interval must be **strictly narrower** than a
    flat bootstrap on the same rows, and the gap must grow with the offset". It tests the property
    the estimator exists for -- the between-gameweek component is held fixed, so it cannot enter the
    interval -- rather than a case where the estimator degenerates."""
    gaps = []
    for offset in (1.0, 3.0, 9.0):
        panel = _balanced_panel(offset=offset)
        stratified = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
        flat = _flat_bootstrap_ci(panel["value"].to_numpy(), n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
        assert _width(stratified) < _width(flat)
        gaps.append(_width(flat) - _width(stratified))

    assert gaps == sorted(gaps)


def test_with_no_between_gameweek_offset_the_two_draws_coincide() -> None:
    """The other half of the same oracle, which the first would pass while blind. §10.5 attributes
    the narrowing to "exactly the between-gameweek component", so with no offset there is nothing to
    remove and the two widths must agree up to Monte Carlo noise."""
    panel = _balanced_panel(offset=0.0)
    stratified = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    flat = _flat_bootstrap_ci(panel["value"].to_numpy(), n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert _width(stratified) == pytest.approx(_width(flat), rel=0.05)


def test_oracle_the_single_stratum_case_is_an_ordinary_bootstrap_of_a_mean() -> None:
    """§10.5's second oracle: "With one gameweek in the window the stratified draw *is* an ordinary
    bootstrap of a mean over that week's rows, which any reference implementation can be checked
    against directly." Bit-for-bit, because the draw sequence is the same one."""
    rng = np.random.default_rng(11)
    values = rng.normal(size=40)
    panel = _panel([(4, f"s{i}", float(v)) for i, v in enumerate(values)])

    assert _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED) == _flat_bootstrap_ci(
        values, n=N_TEST, ci_level=CI_LEVEL, seed=SEED
    )


# ---------------------------------------------------------------------------
# §10.2's estimand, §10.5's remaining properties
# ---------------------------------------------------------------------------


def test_the_statistic_is_the_grand_mean_not_the_unweighted_mean_of_per_gameweek_means() -> None:
    """§10.2 selects "the grand mean over surviving squad-weeks", and §10.4 records that §0.8's
    exclusions leave the strata unbalanced so the two readings differ. A panel of 100 zeroes at one
    gameweek and a single 100.0 at another separates them: the grand mean is ~0.99, the mean of
    per-gameweek means is 50."""
    panel = _panel([(4, f"s{i}", 0.0) for i in range(100)] + [(5, "x", 100.0)])
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert lo <= 100.0 / 101.0 <= hi
    assert hi < 10.0


def test_each_stratums_row_count_is_held_fixed() -> None:
    """§10.5: "`size=len(strata[gw])` is the whole of the stratification", and writing it as a
    constant "would rebalance the panel §10.4 establishes is unbalanced across weeks". The
    unbalanced panel above would centre near 50 if the strata were redrawn to a common size."""
    panel = _panel([(4, f"s{i}", 0.0) for i in range(100)] + [(5, "x", 100.0)])
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert not (lo <= 50.0 <= hi)


def test_the_endpoints_are_not_rounded() -> None:
    """§10.5 requires raw floats. §8.2 rejected the `research/kernels` implementation partly because
    `INVENTORY.md` §2.9 records `_percentile_ci` rounding endpoints to 4 dp, and §0.15's S2 is a
    boundary test on whether the interval excludes zero -- rounding can move a genuinely non-zero
    bound onto exactly 0."""
    panel = _balanced_panel(offset=1.0)
    lo, hi = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)
    assert (lo, hi) != (round(lo, 4), round(hi, 4))


def test_the_interval_is_deterministic_in_the_seed_and_moves_with_it() -> None:
    """§7.2 stores the intervals precisely because they are "resampled and seed-dependent". Both
    halves are asserted: the same seed reproduces, a different seed does not."""
    panel = _balanced_panel(offset=1.0)
    first = _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=0)
    assert first == _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=0)
    assert first != _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=1)


def test_a_wider_coverage_gives_a_wider_interval() -> None:
    panel = _balanced_panel(offset=1.0)
    narrow = _stratified_resample(panel, n=N_TEST, ci_level=0.80, seed=SEED)
    wide = _stratified_resample(panel, n=N_TEST, ci_level=0.99, seed=SEED)
    assert _width(narrow) < _width(wide)


# ---------------------------------------------------------------------------
# §10.8's pre-registration, and §10.1's absent block parameter
# ---------------------------------------------------------------------------


def test_the_signature_defaults_are_the_pre_registered_values() -> None:
    """§10.8's table: `n` 10000, `ci_level` 0.95, `seed` 0 for both intervals, `block` 4 for the
    gameweek one. Pinned here as well as in `PRE_REGISTRATION.yaml` (§7.4) so a default that drifted
    from the freeze would fail in the module that carries it."""
    assert (N_RESAMPLES, CI_LEVEL, SEED, BLOCK_GWS) == (10_000, 0.95, 0, 4)

    squad = inspect.signature(squad_stratified_ci).parameters
    gameweek = inspect.signature(gameweek_block_ci).parameters
    assert (squad["n"].default, squad["ci_level"].default, squad["seed"].default) == (10_000, 0.95, 0)
    assert (gameweek["n"].default, gameweek["block"].default, gameweek["seed"].default) == (10_000, 4, 0)


def test_the_squad_interval_takes_no_block_parameter() -> None:
    """§10.1: "The squad interval takes no `block` parameter", because within a stratum the squads
    are unordered and there is nothing for a block to preserve. §10.8 pins it as n/a."""
    assert "block" not in inspect.signature(squad_stratified_ci).parameters
    assert "block" not in inspect.signature(_stratified_resample).parameters


def test_the_reference_quantities_have_no_defaults() -> None:
    """§2.9's posture for the sampler's seed, applied to G3's and G4's reference quantities: a
    default would let a caller skip the guard, which is the failure §10.10.3 rejects B for."""
    for function in (squad_stratified_ci, gameweek_block_ci):
        parameter = inspect.signature(function).parameters["n_scoreable_gw"]
        assert parameter.default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# §8.2 -- the gameweek interval is a reuse, not a build
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# This module's own checks, kept distinguishable from §10's four
# ---------------------------------------------------------------------------


def test_an_empty_panel_is_rejected_rather_than_returning_nan() -> None:
    with pytest.raises(ValueError, match="empty"):
        _stratified_resample(_panel([]), n=N_TEST, ci_level=CI_LEVEL, seed=SEED)


def test_a_non_finite_value_is_rejected_rather_than_returning_nan() -> None:
    """`formations.py`'s precedent: nulls are the caller's to resolve."""
    panel = _panel([(4, "a", 1.0), (5, "b", float("nan"))])
    with pytest.raises(ValueError, match="non-finite"):
        _stratified_resample(panel, n=N_TEST, ci_level=CI_LEVEL, seed=SEED)


# ---------------------------------------------------------------------------
# §10.10.6 -- the bench-order entry point is owed, not built
# ---------------------------------------------------------------------------


def test_the_bench_order_entry_point_raises_rather_than_faking_a_result() -> None:
    """`METRIC.md` §8's row #17 is unselected, so no treatment can be computed. §10.10.6 records the
    entry point as owed; `results.py`'s `T1HasNoProducer` is the precedent for naming it in code."""
    with pytest.raises(BenchOrderTreatmentUnselected):
        bench_order_ci()
    assert issubclass(BenchOrderTreatmentUnselected, NotImplementedError)


def test_the_bench_order_entry_point_names_the_open_selection() -> None:
    """A stub whose message did not route the reader would be worse than an `AttributeError`."""
    with pytest.raises(BenchOrderTreatmentUnselected) as raised:
        bench_order_ci(object(), n_scoreable_gw=35)
    assert "#17" in str(raised.value)


# ---------------------------------------------------------------------------
# §5.1 -- Tier B's import closure
# ---------------------------------------------------------------------------


def test_the_import_closure_is_tier_bs(tmp_path_factory: pytest.TempPathFactory) -> None:
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
