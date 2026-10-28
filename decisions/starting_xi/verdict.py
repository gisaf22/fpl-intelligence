"""Stage 5's verdict on the primary win share -- the one function the power lab and the real run call.

#55 decisions 10 and 11 (P3, P4, P6): each of four groups (overall and the three rank bands) gets a
two-sided crossed-bootstrap p-value for its win share against 50%, and the four are Holm-adjusted at a
family-wise alpha of 0.05. The input is a plain manager-week table -- `manager_id`, `gameweek`,
`outcome` (1 win, 0.5 tie, 0 loss) and `band` (`top`, `middle`, `bottom`, or null for no valid rank)
-- so nothing here reads the database.

**One implementation, two callers (#60 L).** `power_lab` measures this function and the real
Stage 5 run will import it; a test checks both resolve the same function object. Holm is the
research kernel's own `holm_bonferroni`, imported under an import contract limited to
`research.kernels` (#60 decision 1), not a copy.

**The crossed bootstrap.** Each repeat draws managers and calendar gameweeks with replacement,
independently; a manager-week counts once for every pairing of its manager draw and its gameweek
draw, i.e. with weight `manager_count x gameweek_count` (`crossed_share`).

**The p-value** reuses the repository's `(1 + k) / (1 + B)` plug-in convention, two-sided, and
deliberately does not round: P6's re-run rule compares a raw p-value with its Holm threshold to within
two standard errors, and a 4 dp rounding would move it by more than that at 100,000 repeats.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from research.kernels.hypothesis.multiplicity import holm_bonferroni

# The pre-registered parameters (#55 P6; PRE_REGISTRATION.yaml `stage5_verdict`).
GROUPS: Final[tuple[str, ...]] = ("overall", "top", "middle", "bottom")
BANDS: Final[tuple[str, ...]] = GROUPS[1:]
NULL_SHARE: Final[float] = 0.5
FAMILY_WISE_ALPHA: Final[float] = 0.05
N_RESAMPLES: Final[int] = 10_000
SEED: Final[int] = 0
RERUN_RESAMPLES: Final[int] = 100_000
RERUN_SEED: Final[int] = 1
P_VALUE_CONVENTION: Final[str] = "one_plus_k_over_one_plus_b"

OUTCOMES: Final[frozenset[float]] = frozenset({0.0, 0.5, 1.0})
COLUMNS: Final[tuple[str, ...]] = ("manager_id", "gameweek", "outcome", "band")

# Resample draws are built this many at a time, so memory stays bounded at 100,000 repeats.
_CHUNK: Final[int] = 500


@dataclass(frozen=True)
class Verdict:
    """The four groups' result, in `GROUPS` order.

    `rerun_needed` says whether any raw p-value landed within two standard errors of its own Holm
    threshold; `rerun` whether the 100,000-repeat re-run was applied (the lab counts the first and
    never applies it, #60 runtime (e)).
    """

    groups: tuple[str, ...]
    shares: np.ndarray
    p_raw: np.ndarray
    p_adj: np.ndarray
    reject: np.ndarray
    rerun_needed: bool
    rerun: bool


@dataclass(frozen=True)
class _Panel:
    """The table as dense (manager x group*gameweek) sums and counts, plus the label order."""

    sums: np.ndarray
    counts: np.ndarray
    managers: np.ndarray
    gameweeks: np.ndarray


def _panel(table: pd.DataFrame) -> _Panel:
    missing = [c for c in COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"table lacks column(s) {missing}; expected {list(COLUMNS)}")
    outcome = table["outcome"].to_numpy(dtype=float)
    bad = ~np.isin(outcome, list(OUTCOMES))
    if bad.any():
        raise ValueError(f"outcome must be 1, 0.5 or 0; got {sorted(set(outcome[bad].tolist()))[:5]}")
    bands = table["band"]
    unknown = sorted(set(bands.dropna()) - set(BANDS))
    if unknown:
        raise ValueError(f"band must be one of {list(BANDS)} or null; got {unknown}")
    if table.duplicated(["manager_id", "gameweek"]).any():
        raise ValueError("a manager-week appears more than once")

    m_idx, managers = pd.factorize(table["manager_id"], sort=True)
    g_idx, gameweeks = pd.factorize(table["gameweek"], sort=True)
    n_m, n_g = len(managers), len(gameweeks)
    sums = np.zeros((n_m, len(GROUPS) * n_g))
    counts = np.zeros_like(sums)
    np.add.at(sums, (m_idx, g_idx), outcome)
    np.add.at(counts, (m_idx, g_idx), 1.0)
    for k, band in enumerate(BANDS, start=1):
        rows = (bands == band).to_numpy()
        np.add.at(sums, (m_idx[rows], k * n_g + g_idx[rows]), outcome[rows])
        np.add.at(counts, (m_idx[rows], k * n_g + g_idx[rows]), 1.0)
    return _Panel(sums, counts, np.asarray(managers), np.asarray(gameweeks))


def _weighted_shares(panel: _Panel, manager_w: np.ndarray, gameweek_w: np.ndarray) -> np.ndarray:
    """Shares for each row of weights: (draws x managers), (draws x gameweeks) -> (draws x groups)."""
    n_g = len(panel.gameweeks)
    num = (manager_w @ panel.sums).reshape(-1, len(GROUPS), n_g)
    den = (manager_w @ panel.counts).reshape(-1, len(GROUPS), n_g)
    num = (num * gameweek_w[:, None, :]).sum(axis=2)
    den = (den * gameweek_w[:, None, :]).sum(axis=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


def crossed_share(
    table: pd.DataFrame, *, manager_counts: Mapping[object, int], gameweek_counts: Mapping[object, int]
) -> dict[str, float]:
    """Each group's share under one crossed draw, given how often each manager and gameweek was drawn.

    A manager-week's weight is its manager's count times its gameweek's count; a group with no
    weight left is NaN.
    """
    panel = _panel(table)
    manager_w = np.array([[manager_counts.get(m, 0) for m in panel.managers]], dtype=float)
    gameweek_w = np.array([[gameweek_counts.get(g, 0) for g in panel.gameweeks]], dtype=float)
    shares = _weighted_shares(panel, manager_w, gameweek_w)[0]
    return dict(zip(GROUPS, shares.tolist(), strict=True))


def _counts(rng: np.random.Generator, draws: int, n: int) -> np.ndarray:
    """Multiplicities of `n` items drawn `n` times with replacement, for each of `draws` repeats."""
    idx = rng.integers(0, n, size=(draws, n)) + (np.arange(draws) * n)[:, None]
    return np.bincount(idx.ravel(), minlength=draws * n).reshape(draws, n).astype(float)


def _bootstrap_shares(panel: _Panel, *, n_resamples: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_m, n_g = len(panel.managers), len(panel.gameweeks)
    out = np.empty((n_resamples, len(GROUPS)))
    for start in range(0, n_resamples, _CHUNK):
        b = min(_CHUNK, n_resamples - start)
        out[start : start + b] = _weighted_shares(panel, _counts(rng, b, n_m), _counts(rng, b, n_g))
    return out


def two_sided_p(draws: np.ndarray, *, null: float = NULL_SHARE) -> float:
    """Two-sided bootstrap p-value against `null`: `2 (1 + k) / (1 + B)`, clipped to 1, never rounded.

    `k` is the smaller tail count (draws at or below the null, or at or above it) over the non-NaN draws.
    """
    arr = np.asarray(draws, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return float("nan")
    tail = min(int(np.sum(arr <= null)), int(np.sum(arr >= null)))
    return float(min(1.0, 2.0 * (1 + tail) / (1 + arr.size)))


def _raw_p(panel: _Panel, *, n_resamples: int, seed: int) -> np.ndarray:
    draws = _bootstrap_shares(panel, n_resamples=n_resamples, seed=seed)
    return np.array([two_sided_p(draws[:, k]) for k in range(len(GROUPS))])


def raw_p_values(table: pd.DataFrame, *, n_resamples: int, seed: int) -> np.ndarray:
    """The four groups' raw two-sided p-values from one crossed bootstrap, in `GROUPS` order."""
    return _raw_p(_panel(table), n_resamples=n_resamples, seed=seed)


def needs_rerun(p_raw: np.ndarray, *, n_resamples: int, alpha: float) -> bool:
    """P6: is any raw p-value within two standard errors of its own Holm threshold?

    The p-value ranked r-th smallest (1-based) of m has threshold `alpha / (m - r + 1)`; its standard
    error is the binomial `sqrt(p (1 - p) / B)` of a tail proportion over B repeats.
    """
    p = np.asarray(p_raw, dtype=float)
    m = p.size
    order = np.argsort(p, kind="stable")
    thresholds = np.empty(m)
    thresholds[order] = alpha / np.arange(m, 0, -1)
    se = np.sqrt(p * (1 - p) / n_resamples)
    return bool(np.any(np.abs(p - thresholds) <= 2 * se))


def primary_verdict(
    table: pd.DataFrame,
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    rerun_resamples: int = RERUN_RESAMPLES,
    rerun_seed: int = RERUN_SEED,
    alpha: float = FAMILY_WISE_ALPHA,
    apply_rerun: bool = True,
) -> Verdict:
    """The four Holm-adjusted tests of the primary win share against 50% (#55 decision 11).

    If P6's re-run is needed and `apply_rerun`, all four tests are re-run at `rerun_resamples` under
    `rerun_seed`, and that result replaces the first in either direction.
    """
    panel = _panel(table)
    ones = np.ones((1, len(panel.managers)))
    shares = _weighted_shares(panel, ones, np.ones((1, len(panel.gameweeks))))[0]
    p_raw = _raw_p(panel, n_resamples=n_resamples, seed=seed)
    rerun_needed = needs_rerun(p_raw, n_resamples=n_resamples, alpha=alpha)
    if rerun_needed and apply_rerun:
        p_raw = _raw_p(panel, n_resamples=rerun_resamples, seed=rerun_seed)
    adjusted = holm_bonferroni(p_raw, alpha=alpha)
    return Verdict(
        groups=GROUPS,
        shares=shares,
        p_raw=p_raw,
        p_adj=adjusted["p_adj"],
        reject=adjusted["reject"],
        rerun_needed=rerun_needed,
        rerun=rerun_needed and apply_rerun,
    )
