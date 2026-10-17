"""`METRIC.md` §2.1's verdict rule -- `DESIGN.MD` §7.5's in-slice statistical machinery.

Four pieces, in the order §2.1 applies them: a **block bootstrap of the mean** of a per-gameweek
paired regret series (§2.1 step 1's series, resampled at §3.1's unit -- gameweeks, not squads); a
**one-sided p-value** from those draws for `H0: mean regret <= 0` vs `H1: mean regret > 0`
(step 2); **Holm-Bonferroni step-down** across the family's p-values at family-wise alpha = 0.05
(step 3); and the **conjunctive PASS reduction** -- PASS iff every null in the family is rejected
in the favourable direction (step 4), returning the per-leg results alongside the boolean because
§2.2's whole argument for conjunctive-over-best-of-three is that nothing about how the verdict was
reached gets collapsed. Per §2.3's appended note, each leg carries its own effective `n`.

**Tier A, numpy-only. Re-derived, not imported -- `DESIGN.MD` §7.5.**
`research.kernels.inferential.resampling.block_bootstrap_ci` and
`research.kernels.hypothesis.multiplicity.holm_bonferroni` both exist and both are mirrored here
in semantics. Importing either takes a `decisions -> research` edge and pulls 25 project modules
in through `research/kernels/__init__.py`'s eager re-export chain, which the `.importlinter`
contract `DESIGN.MD` §4 commits to writing (the mirror of
`no_starting_xi_tier_a_to_downstream`, whose forbidden list names `research`) would forbid. This
is the third instance of the same call in this slice, made for the same reason as
`candidates.py`'s PPG derivations and `evaluate.py`'s local ranker: a block bootstrap of a mean
and a Holm step-down are each a few lines of numpy over a 32-element array, and the duplication is
small, bounded and stated rather than hidden.

The `(1 + k) / (1 + n)` p-value plug-in is likewise the repository's existing convention for a
bootstrap tail proportion (`research/kernels/diagnostic/panel.py:163`,
`research/kernels/inferential/resampling.py:210`), re-derived here in its one-sided form -- both
existing uses are two-sided, and §2.1 step 2's test is one-sided.

Deterministic given `seed`: the same series run twice produces the same p-value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

N_BOOTSTRAP: Final[int] = 10_000
"""Bootstrap resample count. Larger than `research.kernels`' 1000 because the one-sided p-value
here is read straight off the draws' lower tail and then multiplied by up to 3 by Holm: at 1000
draws the p-value's resolution is 1/1001, which is coarse relative to an alpha/3 = 0.0167 Holm
threshold. 10,000 draws over a 32-element array costs milliseconds."""

BOOTSTRAP_SEED: Final[int] = 0
"""Matches `research.kernels.inferential.resampling.BOOTSTRAP_SEED`, so this slice's intervals are
seeded the same way the research layer's are."""

FAMILY_WISE_ALPHA: Final[float] = 0.05
"""`METRIC.md` §2.1 step 3's family-wise error rate. Not a tunable."""

BLOCK_LENGTH: Final[int] = 2
"""Block length for the moving-block bootstrap, chosen from the *measured* serial dependence of
this slice's real regret series rather than assumed -- `DESIGN.MD` §7.7 left it explicitly
undetermined pending that measurement.

Measured on the six baseline-vs-baseline `ConstructionRegret` series over the 32 qualifying
gameweeks (`evaluate.build().construction_regret`), lag-1 through lag-4 autocorrelations are:

    C1 vs C2   ac1 -0.008  ac2  0.051  ac3 -0.258  ac4 -0.068
    C1 vs C3   ac1 -0.056  ac2  0.181  ac3  0.239  ac4 -0.078
    C2 vs C3   ac1  0.252  ac2  0.030  ac3  0.161  ac4 -0.078

(the reversed pairs are the exact negatives of these series, so their autocorrelations are
identical.) Every value lies inside the +/- 2/sqrt(32) = +/- 0.354 white-noise band, no lag carries
a consistent sign across the three series, and the largest magnitude (0.252 at lag 1 for C2 vs C3)
is not distinguishable from sampling noise at n = 32. So the realised dependence is weak, and the
choice is between the iid bootstrap (block = 1) and a short block.

`block = 2` is chosen: it is the shortest block that is still a block bootstrap, so it honours
§7.5's requirement to respect within-season serial dependence rather than assuming it away on a
measurement that cannot rule it out at this sample size, while costing almost nothing in interval
width. The kernel's own default of 4 is rejected here -- on a 32-week series it yields only 8
independent blocks per resample, which coarsens the bootstrap distribution materially for
dependence the data does not show."""


@dataclass(frozen=True)
class LegResult:
    """One leg of `METRIC.md` §2.1's family: one candidate-vs-baseline paired test.

    `n` is this leg's own effective sample size, reported per §2.3's instruction rather than
    assumed shared across the family.
    """

    name: str
    n: int
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    p_value: float
    p_adjusted: float
    rejected: bool


@dataclass(frozen=True)
class VerdictResult:
    """§2.1 step 4's verdict: the boolean, and every leg it was reduced from.

    §2.2 requires that the per-leg results stay visible -- a candidate that narrowly fails one leg
    while comfortably clearing the other two is reported as "did not pass", but the report must
    still show where it fell short.
    """

    passed: bool
    alpha: float
    legs: tuple[LegResult, ...]


def block_bootstrap_means(
    values: np.ndarray,
    block: int = BLOCK_LENGTH,
    n_resamples: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    """Moving-block bootstrap draws of the MEAN of a per-gameweek paired series.

    Mirrors `research.kernels.inferential.resampling.block_bootstrap_ci`'s resampling scheme
    exactly -- NaNs dropped, `ceil(n / block)` blocks of `block` consecutive positions drawn with
    replacement from every valid start, concatenated and truncated back to the series length --
    but returns the draws rather than a percentile interval, because §2.1 step 2 needs the draws
    themselves for a one-sided tail proportion.

    Returns an empty array when fewer than `block` non-NaN observations remain, matching the
    kernel's `(nan, nan)` degenerate case.
    """
    if block < 1:
        raise ValueError(f"block must be >= 1, got {block}")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1, got {n_resamples}")

    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size < block:
        return np.empty(0, dtype=float)

    rng = np.random.default_rng(seed)
    k = int(np.ceil(arr.size / block))
    draws = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        starts = rng.integers(0, arr.size - block + 1, size=k)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[: arr.size]
        draws[i] = arr[idx].mean()
    return draws


def one_sided_p_value(draws: np.ndarray) -> float:
    """`METRIC.md` §2.1 step 2's p-value: `H0: mean regret <= 0` vs `H1: mean regret > 0`.

    The evidence against H0 is the proportion of bootstrap draws of the mean that fall at or below
    zero -- a favourable series puts almost all of its draws above zero and leaves a small tail.

    Uses the `(1 + k) / (1 + n)` plug-in this repository already applies to bootstrap tail
    proportions (`research/kernels/diagnostic/panel.py:163`), so no finite draw count is ever
    reported as infinitely significant. One-sided, so no factor of 2 -- that factor is the only
    difference from the two existing two-sided uses.

    Returns NaN on an empty draw array, matching the kernel's degenerate-input convention.
    """
    arr = np.asarray(draws, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return float("nan")
    tail = int(np.sum(arr <= 0.0))
    return float(min(1.0, (1 + tail) / (1 + arr.size)))


def percentile_ci(draws: np.ndarray, ci_level: float = 0.95) -> tuple[float, float]:
    """Two-sided percentile interval over the non-NaN draws -- reporting, not the test.

    The verdict is decided by `one_sided_p_value` and Holm; this interval is carried on each
    `LegResult` so a reader can see the magnitude and precision behind a leg's p-value.
    """
    arr = np.asarray(draws, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (float("nan"), float("nan"))
    alpha = 1.0 - ci_level
    return (
        float(np.percentile(arr, 100 * alpha / 2)),
        float(np.percentile(arr, 100 * (1 - alpha / 2))),
    )


def holm_bonferroni(
    p_values: list[float] | np.ndarray,
    alpha: float = FAMILY_WISE_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    """`METRIC.md` §2.1 step 3's step-down correction, preserving input order.

    Sort ascending, multiply the i-th smallest by `(m - i)`, enforce monotone non-decreasing
    adjusted values from the smallest upward, clip to `[0, 1]`, reject where the adjusted value is
    at most `alpha`. Equal or greater power than plain Bonferroni, and family-wise valid without
    requiring the tests to be independent -- which matters here, since §2.1 step 3 notes all three
    legs are computed from overlapping realised-outcome data for the same candidate and gameweek
    set.

    Returns `(p_adjusted, rejected)`, both aligned to the input order. Empty input returns empty
    arrays.
    """
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1:
        raise ValueError("p_values must be one-dimensional")
    if p.size == 0:
        return (np.empty(0, dtype=float), np.empty(0, dtype=bool))
    if np.isnan(p).any():
        raise ValueError("p_values must not contain NaN")
    if ((p < 0.0) | (p > 1.0)).any():
        raise ValueError("p_values must lie in [0, 1]")

    m = p.size
    order = np.argsort(p, kind="stable")
    adjusted_sorted = np.clip(np.maximum.accumulate(p[order] * np.arange(m, 0, -1)), 0.0, 1.0)

    p_adjusted = np.empty(m, dtype=float)
    p_adjusted[order] = adjusted_sorted
    return (p_adjusted, p_adjusted <= alpha)


def leg_statistics(
    series: np.ndarray,
    block: int = BLOCK_LENGTH,
    n_resamples: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, dict[str, float | int]]:
    """One leg's raw p-value plus the descriptives its `LegResult` needs.

    Split out from `verdict` because Holm must see all of the family's raw p-values before any
    leg's rejection can be decided -- a leg cannot be finished in isolation.
    """
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    draws = block_bootstrap_means(arr, block=block, n_resamples=n_resamples, seed=seed)
    ci_lower, ci_upper = percentile_ci(draws)
    p_value = one_sided_p_value(draws)
    descriptives: dict[str, float | int] = {
        "n": int(arr.size),
        "mean": float(arr.mean()) if arr.size else float("nan"),
        "std": float(arr.std(ddof=1)) if arr.size > 1 else float("nan"),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }
    return p_value, descriptives


def verdict(
    series_by_leg: dict[str, np.ndarray],
    alpha: float = FAMILY_WISE_ALPHA,
    block: int = BLOCK_LENGTH,
    n_resamples: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> VerdictResult:
    """`METRIC.md` §2.1 end to end, over a pre-registered family of candidate-vs-baseline series.

    `series_by_leg` maps a leg name to that leg's per-gameweek `ConstructionRegret_{C,B}` series.
    The family is whatever is passed -- for `METRIC.md` §2's verdict that is exactly the three
    candidate-vs-baseline pairs, and `DESIGN.MD` §7.3 is explicit that the C4-nofdr ablation is a
    diagnostic and must **not** be added as a fourth member, since a post-hoc fourth arm is the
    multiplicity inflation §2 exists to control.

    PASS iff every leg is rejected after correction (§2.1 step 4). An empty family cannot satisfy
    a conjunctive rule about clearing the baselines, so it returns `passed=False` rather than a
    vacuous True.
    """
    names = list(series_by_leg)
    raw = []
    descriptives = []
    for name in names:
        p_value, stats = leg_statistics(series_by_leg[name], block=block, n_resamples=n_resamples, seed=seed)
        raw.append(p_value)
        descriptives.append(stats)

    p_adjusted, rejected = holm_bonferroni(np.asarray(raw, dtype=float), alpha=alpha)

    legs = tuple(
        LegResult(
            name=name,
            n=int(stats["n"]),
            mean=float(stats["mean"]),
            std=float(stats["std"]),
            ci_lower=float(stats["ci_lower"]),
            ci_upper=float(stats["ci_upper"]),
            p_value=float(p_raw),
            p_adjusted=float(p_adj),
            rejected=bool(reject),
        )
        for name, stats, p_raw, p_adj, reject in zip(names, descriptives, raw, p_adjusted, rejected, strict=True)
    )
    return VerdictResult(passed=bool(legs) and all(leg.rejected for leg in legs), alpha=alpha, legs=legs)
