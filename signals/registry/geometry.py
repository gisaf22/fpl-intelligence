"""Reusable signal-target relationship geometry helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from signals.lifecycle.schema import (
    MATCH_LEVEL_SIGNALS,
    POPULATION_ROBUSTNESS_VALUES,
    POPULATION_SCOPE_VALUES,
)


POSITIONS: list[str] = ["GK", "DEF", "MID", "FWD"]
BLOCK_ORDER: list[str] = ["early", "mid", "late"]

FDR_SIGNALS: frozenset[str] = frozenset({"fdr_avg", "fdr_max", "fdr_min"})
FDR_ORDINAL_BINS: list[float] = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
FDR_ORDINAL_LABELS: list[str] = ["1", "2", "3", "4", "5"]

DISCRETE_BINS: list[float] = [-np.inf, 0, 1, np.inf]
DISCRETE_LABELS: list[str] = ["0", "1", "2+"]
TWO_STAGE_NZ_LABELS: list[str] = ["low_nz", "mid_nz", "high_nz"]
QUANTILE_N_BINS: int = 5

GEOMETRY_TAXONOMY: list[str] = [
    "monotonic_positive",
    "monotonic_negative",
    "threshold_positive",
    "threshold_negative",
    "saturation",
    "non_monotonic",
    "asymmetric_tail",
    "indeterminate",
    "unassessable",
]
MONOTONIC_GEOMETRIES: frozenset[str] = frozenset(
    {"monotonic_positive", "monotonic_negative"}
)
UPPER_TAIL_GEOMETRIES: frozenset[str] = frozenset(
    {"threshold_positive", "threshold_negative", "saturation"}
)

ASSOCIATION_CLASS_TAXONOMY: list[str] = [
    "continuous_monotonic",
    "upper_tail_concentrated",
    "tail_dependent",
    "temporally_unstable",
    "weak_association",
    "unassessable",
]

PANEL_CLASS_THRESHOLDS: list[tuple[float, str]] = [
    (0.40, "state_sensitive"),
    (0.20, "mixed"),
    (0.00, "identity_dominant"),
]

HAUL_THRESHOLD_PTS = 12
HAUL_DROP_MATERIAL = 0.20

MIN_N_SHAPE = 100
MIN_N_HAUL = 30
MIN_N_PANEL_PLAYERS = 20
MIN_N_PER_BIN = 20
SPARSE_THRESHOLD = 10

MIN_ACTIVE_BINS: dict[str, int] = {
    "discrete": 2,
    "ordinal": 3,
    "two_stage": 3,
    "quantile": 4,
}

MONO_CONF_LOW = 0.60
MONO_CONF_HIGH = 0.80

SUPPORT_TYPE_TAXONOMY: list[str] = [
    "sparse_event_process",
    "structural_binary",
    "near_constant_position",
    "ordinal_scheme_mismatch",
    "insufficient_n",
]



def select_bucketing_scheme(
    series: pd.Series,
    min_n: int = MIN_N_SHAPE,
    sparse_threshold: int = SPARSE_THRESHOLD,
    signal_name: str = "",
) -> tuple[str, Any]:
    """Return the appropriate bucketing scheme for a signal series."""
    n = len(series)
    if n < min_n:
        return "insufficient", None

    if signal_name in FDR_SIGNALS:
        return "ordinal", (FDR_ORDINAL_BINS, FDR_ORDINAL_LABELS)

    zero_frac = (series == 0).mean()
    n_unique_nz = int(series[series > 0].nunique())

    if n_unique_nz < sparse_threshold:
        return "discrete", (DISCRETE_BINS, DISCRETE_LABELS)
    if zero_frac > 0.60:
        return "two_stage", None
    return "quantile", QUANTILE_N_BINS


def bin_analysis(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    scheme: tuple[str, Any],
    min_n_per_bin: int = MIN_N_PER_BIN,
) -> tuple[pd.DataFrame | None, str]:
    """Bin one signal-position slice and compute per-bin target statistics."""
    subset = df[df["position"] == position][[signal, target]].dropna().copy()
    n = len(subset)
    scheme_type, param = scheme

    if scheme_type == "insufficient" or n < MIN_N_SHAPE:
        return None, "insufficient_support"

    sig = subset[signal].astype(float)
    if sig.nunique() <= 1:
        return None, "degenerate"

    try:
        if scheme_type in ("discrete", "ordinal"):
            bins, labels = param
            subset["bin"] = pd.cut(
                sig, bins=bins, labels=labels, include_lowest=True
            )
        elif scheme_type == "two_stage":
            nz_mask = sig > 0
            nz_series = sig[nz_mask]
            q_bins = pd.qcut(
                nz_series, q=3, labels=TWO_STAGE_NZ_LABELS, duplicates="drop"
            )
            subset["bin"] = "zero"
            subset.loc[nz_mask, "bin"] = q_bins.astype(str)
        else:
            n_bins = param
            subset["bin"] = pd.qcut(
                sig,
                q=n_bins,
                labels=[f"Q{i + 1}" for i in range(n_bins)],
                duplicates="drop",
            )
    except Exception:
        return None, "degenerate"

    bin_stats = (
        subset.groupby("bin", observed=True)[target]
        .agg(
            mean="mean",
            median="median",
            std="std",
            p25=lambda x: x.quantile(0.25),
            p75=lambda x: x.quantile(0.75),
            count="count",
        )
        .reset_index()
    )

    min_active = MIN_ACTIVE_BINS.get(scheme_type, 4)
    active_bins = int((bin_stats["count"] >= min_n_per_bin).sum())
    flag = "insufficient_support:bin_density" if active_bins < min_active else ""
    return bin_stats, flag


def classify_geometry(bin_stats: pd.DataFrame) -> str:
    """Classify X-Y relationship geometry from per-bin target means."""
    occupied = bin_stats[bin_stats["count"] > 0]
    if len(occupied) < 3:
        return "indeterminate"

    means = occupied["mean"].values
    signs = [np.sign(means[i + 1] - means[i]) for i in range(len(means) - 1)]
    n_pos = signs.count(1.0)
    n_neg = signs.count(-1.0)
    n_adj = len(signs)

    if n_pos == n_adj:
        return "monotonic_positive"
    if n_neg == n_adj:
        return "monotonic_negative"

    if len(means) >= 4:
        lower_range = np.ptp(means[:-1])
        top_lift = means[-1] - np.mean(means[:-1])
        if lower_range < 0.5 * top_lift and top_lift > 0:
            return "threshold_positive"

        bottom_drop = np.mean(means[1:]) - means[0]
        upper_range = np.ptp(means[1:])
        if upper_range < 0.5 * bottom_drop and bottom_drop > 0:
            return "threshold_negative"

    if len(means) >= 4:
        lower_gains = means[len(means) // 2] - means[0]
        upper_gains = means[-1] - means[len(means) // 2]
        if lower_gains > 0 and upper_gains >= 0 and lower_gains > 2 * upper_gains:
            return "saturation"

    mid_range = np.ptp(means[1:-1]) if len(means) > 2 else np.ptp(means)
    total_range = np.ptp(means)
    if total_range > 0 and mid_range / total_range < 0.15:
        return "asymmetric_tail"

    if n_pos >= 1 and n_neg >= 1:
        return "non_monotonic"

    return "indeterminate"


def get_bin_direction(bin_stats: pd.DataFrame) -> tuple[float, ...]:
    """Return signs between adjacent bin means."""
    means = bin_stats["mean"].values
    return tuple(
        float(np.sign(means[i + 1] - means[i])) for i in range(len(means) - 1)
    )


def monotonicity_confidence(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    original_bin_stats: pd.DataFrame,
    scheme: tuple[str, Any],
    n_bootstrap: int = 200,
    seed: int = 42,
) -> float:
    """Bootstrap stability of the original adjacent-bin direction pattern."""
    if n_bootstrap == 0:
        return np.nan

    subset = df[df["position"] == position][[signal, target]].dropna()
    if len(subset) < MIN_N_SHAPE:
        return np.nan

    original_direction = get_bin_direction(original_bin_stats)
    if not original_direction:
        return np.nan

    rng = np.random.default_rng(seed)
    agreements = 0
    attempts = 0

    for _ in range(n_bootstrap):
        sample = subset.sample(
            frac=1.0, replace=True, random_state=int(rng.integers(1_000_000))
        )
        bs_stats, _ = bin_analysis(
            sample.assign(position=position),
            signal,
            target,
            position,
            scheme,
        )
        if bs_stats is None or len(bs_stats) < 2:
            continue
        attempts += 1
        if get_bin_direction(bs_stats) == original_direction:
            agreements += 1

    if attempts == 0:
        return np.nan
    return round(agreements / attempts, 3)


def stability_classify(
    pooled_gap: float,
    block_gaps: dict[str, float | None],
) -> str:
    """Classify temporal stability of a signal's Q1-vs-top-bin gap."""
    valid_gaps = [
        value for value in block_gaps.values() if value is not None and not np.isnan(value)
    ]

    if len(valid_gaps) < 2 or np.isnan(pooled_gap):
        return "insufficient_data"

    all_pos = all(gap > 0 for gap in valid_gaps)
    all_neg = all(gap < 0 for gap in valid_gaps)
    if not (all_pos or all_neg):
        return "unstable"

    abs_gaps = [abs(gap) for gap in valid_gaps]
    min_gap, max_gap = min(abs_gaps), max(abs_gaps)
    gap_ratio = min_gap / max_gap if max_gap > 0 else 1.0

    if gap_ratio < 0.50:
        return "moderate_shift"
    return "stable"
