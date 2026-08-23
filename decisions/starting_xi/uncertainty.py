"""The two paired intervals -- `DESIGN.md` §5.1, §8.2, §10, §10.10.

**Two intervals, two public functions, and they deliberately cannot share a signature.** §0.14
selects U1 and U2 and requires them reported as two. §10.6 states why one function cannot serve
both: they resample different objects -- an *ordered* series of gameweeks in blocks of 4, where
adjacency is the whole point, against a panel of *independent draws within a fixed gameweek margin*,
where adjacency is irrelevant and the margin is what must not move. A merged signature would carry a
`block` meaningless to one caller and a stratum key meaningless to the other, and would admit the
call §0.14 rejects as U3.

* `gameweek_block_ci` -- U2. A **reuse**, not a build: §8.2 fixes the call site as
  `model/eval/metrics.py:79` and requires every argument passed explicitly. This module adds §10.6's
  length assertion and nothing else.
* `squad_stratified_ci` -- U1. A **build**: `INVENTORY.md` §2.9 records no gameweek-stratified
  bootstrap of a mean in the repository, and §10.3 derives the one this slice needs.
* `bench_order_ci` -- **raises**. See `BenchOrderTreatmentUnselected`.

**One shared resampling core, and §10.10.4 makes that a design constraint rather than a
preference.** `_stratified_resample` holds the estimator §10.5 specifies; the public entry points
hold the preconditions that differ between them. A second copy of the resampling body would make the
split cost what §10.10.2's rejected option says it costs -- two copies of `size=len(strata[gw])`,
which §10.5 calls "the whole of the stratification", and two chances for one to be fixed and the
other not.

**§10.10.4's allocation rule decides where each guard lives.** A precondition that holds on every
caller lives in the core; a precondition that validates the panel against the *primary comparison's
dimensions* lives in the primary entry point. §10.10.1 sorts §10's four:

===  ================================================  ===============  ==================
Guard  What it requires                                Home             Transfers to B2?
===  ================================================  ===============  ==================
G1   one row per `(gw, squad_id)`                      core             yes (§10.10.1)
G2   the `gw` column present                           core             yes (§10.10.1)
G3   >1 distinct `gw` when the window has >1           `squad_...`      no  (A1, A3)
G4   series length == the scoreable-gameweek count     `gameweek_...`   no  (A2)
===  ================================================  ===============  ==================

So a future bench-order entry point over this core inherits G1 and G2 and does not inherit G3 or G4,
which is §10.10.5's selection expressed in the module's shape rather than in a comment.

**Import closure: `numpy`, `pandas`, and `model.eval.metrics`.** Tier B (§5.1, §8.2), so `model/`,
`dal/` and `domain/` are permitted and `research/`, `serve/`, `operational/` and every Tier A sibling
-- `harness.py`, `sampler.py`, `formations.py`, `results.py` -- are not. Only `model/` is actually
reached, and only for §8.2's reuse; `test_uncertainty.py` asserts the closure in a subprocess.
`results.py` carries `GameweekIntervalParams` and `SquadIntervalParams`, which would be the natural
argument types here and are not used: it is Tier A, so importing it is forbidden. The composition
root unpacks them at the call.
"""

from __future__ import annotations

from typing import Final, NoReturn

import numpy as np
import pandas as pd

from model.eval.metrics import block_bootstrap_ci

# §5.1's panel: `(gw, squad_id, value)`, one row per surviving squad-week, `value` already
# differenced by the caller (§10.4). The order is the documented one; presence is what is checked.
PANEL_COLUMNS: Final[tuple[str, ...]] = ("gw", "squad_id", "value")

# §10.8's pre-registered parameters, as signature defaults. They are defaults *and* passed
# explicitly at the call site: §0.14 requires `n = 10,000` be "passed explicitly at every call site
# in the slice", and `METRIC.md` §6.2's reason -- a count acquired by import path is acquired by
# accident -- applies to the block length and the coverage too (§8.2). The defaults exist so the
# pre-registered value is readable here and a test can assert it, not so a caller may omit it.
N_RESAMPLES: Final[int] = 10_000
CI_LEVEL: Final[float] = 0.95
SEED: Final[int] = 0
BLOCK_GWS: Final[int] = 4


class BenchOrderTreatmentUnselected(NotImplementedError):
    """Raised by `bench_order_ci`, which names §10.10's open half rather than papering over it.

    §10.10 decides the **interface** a bench-order figure is computed through: the guards that
    transfer (G1, G2) live in the shared core, the guards that do not (G3, G4) stay in the primary
    entry points, and the ordering sample gets its own entry point rather than the guards becoming
    caller-supplied parameters. It explicitly does **not** select the **treatment**.

    `METRIC.md` §8's row #17 is unselected. §6.4.4 there characterises three candidates on the squad
    margin -- W1 stratify unchanged and report the occupancy profile beside the interval, W2 pool
    adjacent gameweeks to a minimum occupancy, W3 abandon the stratification -- and §6.4.5 three on
    the gameweek margin, V1 compact the series, V2 keep the season index carrying empties as
    missing, V3 report U1 only. They do not share a shape: W1 needs no parameter but a second
    return value, W2 needs a pooling width carrying a pre-registration obligation (§6.4.4 there),
    and V2 changes the input contract rather than any threshold on it.

    So the body cannot be written yet, and §4.11 states this document's own standard for writing it
    anyway: a rule written before the thing it quantifies has been characterised is a guess in the
    shape of a decision. `METRIC.md` §6.4.6 records that the two occupancy numbers the selection
    turns on are unmeasured and fall out of the first run.

    §10.10.6 records the entry point as "owed once #17 lands". It is present and raising rather than
    absent so a caller reaching for it gets that routing instead of an `AttributeError`, and so the
    guard allocation above is inherited by whatever body #17 selects.
    """


def _stratified_resample(
    panel: pd.DataFrame,
    *,
    n: int,
    ci_level: float,
    seed: int,
) -> tuple[float, float]:
    """§10.5's estimator: resample squad-weeks within gameweek, `n_g` held fixed per stratum.

    Module-private and **the only copy of the resampling body** (§10.10.4). It enforces G1 and G2,
    which §10.10.1 records as holding on every caller, and enforces neither G3 nor G4.

    §10.3 derives the draw: for every gameweek in the window, draw `n_g` rows uniformly with
    replacement from that gameweek's surviving rows, where `n_g` is the count that gameweek actually
    has; the replicate is the union across gameweeks and the statistic is the grand mean over it
    (§10.2). A row drawn twice counts twice.

    **`size=len(stratum)` is the whole of the stratification** (§10.5). Written as a constant it
    would rebalance the panel §10.4 establishes is unbalanced across weeks; dropped in favour of one
    draw over the flat panel it would be U3, which §0.14 rejects and §10.3 is written around.

    **No rounding.** §10.5 requires raw floats: §8.2 rejected the `research/kernels` implementation
    partly because `INVENTORY.md` §2.9 records `_percentile_ci` rounding endpoints to 4 dp, and
    §0.15's S2 is a boundary test on whether the interval excludes zero.

    **The draw follows §10.5's pseudocode literally** -- per replicate, per stratum -- rather than
    the faster arrangement that draws each stratum across all replicates at once. The two are the
    same estimator and differ only in the order the generator is called, so they disagree at a fixed
    seed. §10.8 pins the seed, so the call order is part of what makes a published interval
    reproducible; the literal form is 1.8s at §7.2's 35 strata x 300 rows and n = 10,000, which is a
    cost worth paying a handful of times per run.

    Two rejections here are **this module's own and are not among §10's four guards**, flagged as
    additions rather than presented as the design's: an empty panel, and a non-finite `value`. Both
    would otherwise return `(nan, nan)` from a function whose entire failure mode (§10.5, §10.6) is
    a plausible-looking number, and the second follows `formations.py`'s precedent that nulls are
    the caller's to resolve.
    """
    # G2 -- §10.6: "The `gw` column is therefore required, not optional". Under §10.3 the draw is
    # *within* stratum, so a caller who dropped `gw` would get a flat bootstrap that runs cleanly
    # and returns a wrongly narrow interval. §10.10.1 puts the presence check here because it holds
    # on every caller; the comparison against the comparison window is G3's and stays upstream.
    missing = [column for column in PANEL_COLUMNS if column not in panel.columns]
    if missing:
        raise ValueError(f"panel is missing {missing}; DESIGN.md §5.1 specifies (gw, squad_id, value) -- G2, §10.6")

    if panel.empty:
        raise ValueError("panel is empty; there is nothing to resample (this module's own check, not one of §10's)")

    values = panel["value"].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(
            "panel value contains a non-finite entry; nulls are the caller's to resolve "
            "(this module's own check, not one of §10's)"
        )

    # G1 -- §10.5: `squad_id` "is in the signature so the function can **assert** that guarantee --
    # one row per `(gw, squad_id)` -- rather than trusting the caller. A panel that violates it is a
    # build bug (§2.8) whose only symptom downstream would be a wrongly narrow interval, so the
    # assertion is where it is cheapest to catch." §10.10.1: it transfers to a filtered subpanel
    # unchanged, because B2 removes squad-weeks and never duplicates one.
    keys = panel[["gw", "squad_id"]]
    if bool(keys.duplicated().any()):
        offenders = keys[keys.duplicated(keep=False)].drop_duplicates().to_numpy().tolist()
        raise ValueError(f"panel has more than one row at some (gw, squad_id): {offenders}; §2.8, §10.5 -- G1")

    strata = [group.to_numpy(dtype=float) for _, group in panel.groupby("gw", sort=True)["value"]]

    rng = np.random.default_rng(seed)
    draws = np.empty(n, dtype=float)
    for replicate in range(n):
        rows = [rng.choice(stratum, size=len(stratum), replace=True) for stratum in strata]
        draws[replicate] = float(np.concatenate(rows).mean())

    alpha = (1.0 - ci_level) / 2.0
    return (float(np.percentile(draws, 100 * alpha)), float(np.percentile(draws, 100 * (1 - alpha))))


def squad_stratified_ci(
    panel: pd.DataFrame,
    *,
    n_scoreable_gw: int,
    n: int = N_RESAMPLES,
    ci_level: float = CI_LEVEL,
    seed: int = SEED,
) -> tuple[float, float]:
    """U1 for the **primary comparison** -- §0.14, §10.3, §10.5, §10.6.

    The squad interval on §7.2's T2, after the caller has pivoted on `ranker`, subtracted, dropped
    zero-gap rows and restricted to the window (§10.7: "The differencing is the caller's step").

    Args:
        panel: `(gw, squad_id, value)`, one row per surviving squad-week, `value` already
            differenced (§10.4). The estimator never sees two rankers, which is what makes the
            pairing structural rather than disciplinary.
        n_scoreable_gw: the comparison's scoreable-gameweek count, from §7.2's T3. Required with no
            default, because it is the reference quantity G3 checks against and a default would let
            a caller skip the guard -- §2.9's posture for the sampler's seed, applied here.
        n: §0.14's resample count, pre-registered at 10,000 (§10.8).
        ci_level: §8.4's coverage, 0.95.
        seed: §8.4's seed, 0.

    Returns:
        `(lo, hi)`, raw unrounded floats, for §7.2's T3 `ci_squads_lo` / `ci_squads_hi`.

    Raises:
        ValueError: on G1, G2 or G3, and on this module's own empty-panel and non-finite checks.

    **G3 lives here and not in the core**, per §10.10.1 and §10.10.4's allocation rule. §10.6:
    "the estimator asserts that the panel contains more than one distinct `gw` whenever the
    comparison window does (§10.7 supplies both)". A caller who passed a constant `gw` would get a
    flat bootstrap that runs cleanly and returns a wrongly narrow interval, which G2's presence
    check cannot see. The guard does **not** transfer to a B2-filtered sample: its reference
    quantity is the *window*, and `METRIC.md` §6.4.3's A1 and A3 make a single-occupied-gameweek
    ordering sample on a 35-gameweek window an expected occupancy rather than a pathology.

    **The condition is ">1 when the window has >1", not equality, and the weaker form is
    deliberate.** §10.5 records that "an empty stratum is simply a gameweek absent from the panel
    rather than a degenerate draw", so §0.8's exclusions may legitimately leave the panel with fewer
    distinct gameweeks than the window has. Equality would reject that.

    **`n_scoreable_gw` is not in §10.5's pseudocode signature and is not an invention here.** §10.5
    writes `squad_stratified_ci(panel, n=10000, ci_level=0.95, seed=0)`; §10.6 then adds the guard
    that needs the window and says §10.7 supplies it. The parameter is that later requirement made
    reachable, and the divergence from the earlier pseudocode is flagged rather than absorbed.
    """
    # G3 -- §10.6. Checked before the core so the failure names the guard the caller tripped rather
    # than surfacing as a suspiciously narrow interval. Guarded on the column's presence so that a
    # panel missing `gw` altogether raises G2 from the core -- the more fundamental of the two --
    # rather than a `KeyError` from this line.
    if "gw" in panel.columns and n_scoreable_gw > 1 and int(panel["gw"].nunique()) <= 1:
        raise ValueError(
            f"panel carries {int(panel['gw'].nunique())} distinct gw over a window of {n_scoreable_gw} "
            "scoreable gameweeks; a constant stratum key is a flat bootstrap wearing U1's name "
            "(§10.6, §0.14's U3) -- G3"
        )

    return _stratified_resample(panel, n=n, ci_level=ci_level, seed=seed)


def gameweek_block_ci(
    series: np.ndarray,
    *,
    n_scoreable_gw: int,
    n: int = N_RESAMPLES,
    block: int = BLOCK_GWS,
    ci_level: float = CI_LEVEL,
    seed: int = SEED,
) -> tuple[float, float]:
    """U2 for the **primary comparison** -- §0.14, §8.2, §10.6.

    A thin call site over `model.eval.metrics.block_bootstrap_ci`, which §8.2 selects on the import
    contract and confirms on merit: `INVENTORY.md` §2.9 records the `research/kernels` alternative
    rounding both endpoints to 4 dp through `_percentile_ci`, and §0.15's S2 is a boundary test on
    whether the interval excludes zero. This module adds G4 and passes every argument explicitly.

    Args:
        series: the ordered per-gameweek series of paired differences, one entry per scoreable
            gameweek (§5.1).
        n_scoreable_gw: the comparison's scoreable-gameweek count, from §7.2's T3. Required with no
            default -- it is G4's reference quantity.
        n: §0.14's resample count, 10,000.
        block: §0.14's block length, 4. `INVENTORY.md` §2.9 records both implementations already
            using it, so passing it records the value rather than fixing anything new (§8.2).
        ci_level: §8.4's coverage, 0.95.
        seed: §8.4's seed, 0.

    Returns:
        `(lo, hi)` for §7.2's T3 `ci_gw_lo` / `ci_gw_hi`.

    Raises:
        ValueError: on G4, and on this module's own non-finite check.

    **G4 lives here and is the only thing that catches a flattened panel.** §10.6 makes the two
    input shapes non-interchangeable -- a 1-D ordered array against a three-column panel -- and that
    does not catch this case, because a flattened squad-week series *is* a 1-D ordered array and
    enters without complaint. §10.6 adds the length assertion for exactly that reason: "A flattened
    panel has `n_squads x n_gw` entries and fails that assertion rather than silently producing a
    number." §10.10.3 turns on this being the sole check, which is why §10.10.5 keeps it here rather
    than making it a caller-supplied parameter.

    It does **not** transfer to a B2-filtered sample: `METRIC.md` §6.4.3's A2 records that a
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
    it bears on `METRIC.md` §6.4.5's V1-against-V2 choice, since silently stripping empties is V1.
    """
    values = np.asarray(series, dtype=float)

    if values.ndim != 1:
        raise ValueError(f"series must be 1-D, got shape {values.shape}; §10.6's input shapes are non-interchangeable")

    # G4 -- §10.6.
    if values.size != n_scoreable_gw:
        raise ValueError(
            f"series carries {values.size} entries against {n_scoreable_gw} scoreable gameweeks (T3); "
            "a flattened squad-week panel has n_squads x n_gw entries and lands here (§10.6, §0.14's U3) -- G4"
        )

    if not np.isfinite(values).all():
        raise ValueError(
            "series contains a non-finite entry; block_bootstrap_draws strips NaN, which would leave G4 "
            "checking a length the estimator does not use (this module's own check, not one of §10's)"
        )

    return block_bootstrap_ci(values, block=block, n=n, ci_level=ci_level, seed=seed)


def bench_order_ci(*_: object, **__: object) -> NoReturn:
    """The bench-order interval has no selected treatment. See `BenchOrderTreatmentUnselected`.

    Present as a named, raising entry point rather than absent, so a caller reaching for it gets
    §10.10's open half and its routing instead of an `AttributeError` that reads like a typo --
    `results.py`'s `write_t1` precedent for the same situation.
    """
    raise BenchOrderTreatmentUnselected(BenchOrderTreatmentUnselected.__doc__)
