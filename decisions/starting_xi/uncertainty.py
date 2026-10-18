"""The paired gameweek interval -- `report.py`'s 95% block-bootstrap range.

`gameweek_block_ci` is a thin call site over `model.eval.metrics.block_bootstrap_ci` with every
argument passed explicitly, plus one guard: the series length must equal the scoreable-gameweek
count.

**Import closure: `numpy` and `model.eval.metrics`.** `research/`, `serve/`, `operational/` and the
harness-side siblings (`harness.py`, `sampler.py`, `formations.py`, `results.py`) are not imported;
`test_uncertainty.py` asserts the closure in a subprocess.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from model.eval.metrics import block_bootstrap_ci

# §10.8's pre-registered parameters, as signature defaults. They are defaults *and* passed
# explicitly at the call site: §0.14 requires `n = 10,000` be "passed explicitly at every call site
# in the slice", and `archive/METRIC.md` §6.2's reason -- a count acquired by import path is acquired by
# accident -- applies to the block length and the coverage too (§8.2). The defaults exist so the
# pre-registered value is readable here and a test can assert it, not so a caller may omit it.
N_RESAMPLES: Final[int] = 10_000
CI_LEVEL: Final[float] = 0.95
SEED: Final[int] = 0
BLOCK_GWS: Final[int] = 4


def gameweek_block_ci(
    series: np.ndarray,
    *,
    n_scoreable_gw: int,
    n: int = N_RESAMPLES,
    block: int = BLOCK_GWS,
    ci_level: float = CI_LEVEL,
    seed: int = SEED,
) -> tuple[float, float]:
    """A per-gameweek series' 95% block-bootstrap range -- §0.14, §8.2, §10.6.

    A thin call site over `model.eval.metrics.block_bootstrap_ci`, which §8.2 selects on the import
    contract and confirms on merit: `archive/INVENTORY.md` §2.9 records the `research/kernels` alternative
    rounding both endpoints to 4 dp through `_percentile_ci`. This module adds G4 and passes every
    argument explicitly.

    Args:
        series: the ordered per-gameweek series, one entry per scoreable gameweek.
        n_scoreable_gw: the scoreable-gameweek count. Required with no
            default -- it is G4's reference quantity.
        n: §0.14's resample count, 10,000.
        block: §0.14's block length, 4. `archive/INVENTORY.md` §2.9 records both implementations already
            using it, so passing it records the value rather than fixing anything new (§8.2).
        ci_level: §8.4's coverage, 0.95.
        seed: §8.4's seed, 0.

    Returns:
        `(lo, hi)`.

    Raises:
        ValueError: on G4, and on this module's own non-finite check.

    **G4 lives here and is the only thing that catches a flattened panel.** §10.6 makes the two
    input shapes non-interchangeable -- a 1-D ordered array against a three-column panel -- and that
    does not catch this case, because a flattened squad-week series *is* a 1-D ordered array and
    enters without complaint. §10.6 adds the length assertion for exactly that reason: "A flattened
    panel has `n_squads x n_gw` entries and fails that assertion rather than silently producing a
    number." §10.10.3 turns on this being the sole check, which is why §10.10.5 keeps it here rather
    than making it a caller-supplied parameter.

    It does **not** transfer to a B2-filtered sample: `archive/METRIC.md` §6.4.3's A2 records that a
    gameweek with no surviving row has no per-gameweek mean at all, so an ordering sample's series
    is *punctured* rather than merely shorter and fails this assertion even where the treatment is
    well defined.

    **The non-finite check is this module's own and it is what makes G4 bind.** It is flagged as an
    addition rather than presented as §10's. `block_bootstrap_ci` reaches
    `model.eval.metrics.block_bootstrap_draws`, which strips NaN from the series before resampling,
    so a series that passes G4's length check can still present the block bootstrap with fewer
    values than `n_scoreable_gw` -- G4 would have checked a length the estimator does not use.
    Rejecting non-finite entries here closes that gap. The stripping behaviour is a repository fact
    this slice's documents do not carry; it is reported rather than asserted into `DESIGN.md`, and
    it bears on `archive/METRIC.md` §6.4.5's V1-against-V2 choice, since silently stripping empties is V1.
    """
    values = np.asarray(series, dtype=float)

    if values.ndim != 1:
        raise ValueError(f"series must be 1-D, got shape {values.shape}; §10.6's input shapes are non-interchangeable")

    # G4 -- §10.6.
    if values.size != n_scoreable_gw:
        raise ValueError(
            f"series carries {values.size} entries against {n_scoreable_gw} scoreable gameweeks; "
            "a flattened squad-week panel has n_squads x n_gw entries and lands here (§10.6, §0.14's U3) -- G4"
        )

    if not np.isfinite(values).all():
        raise ValueError(
            "series contains a non-finite entry; block_bootstrap_draws strips NaN, which would leave G4 "
            "checking a length the estimator does not use (this module's own check, not one of §10's)"
        )

    return block_bootstrap_ci(values, block=block, n=n, ci_level=ci_level, seed=seed)
