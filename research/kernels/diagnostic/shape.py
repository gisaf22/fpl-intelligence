"""Relationship shape classification — Rung Dg (Diagnostic).

Given per-bin target statistics from research.kernels.descriptive.binning,
classifies the structural shape of a signal→target relationship.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

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
SUPPORT_TYPE_TAXONOMY: list[str] = [
    "sparse_event_process",
    "structural_binary",
    "near_constant_position",
    "ordinal_scheme_mismatch",
    "insufficient_n",
]
MONO_CONF_LOW: float = 0.60
MONO_CONF_HIGH: float = 0.80
MIN_N_HAUL: int = 30
MIN_N_PANEL_PLAYERS: int = 20


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
