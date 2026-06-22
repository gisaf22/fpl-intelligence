"""Adaptive signal binning — Rung D (Descriptive).

Selects the appropriate bucketing scheme for a signal and computes per-bin
target statistics. Output feeds classify_geometry in
research.kernels.diagnostic.shape.

Constants inlined from domain.registry.schema to avoid import cycles.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# --- inlined from domain.registry.schema ---
MATCH_LEVEL_SIGNALS: frozenset[str] = frozenset({"was_home", "goals_conceded", "fixture_count", "fdr_avg", "is_dgw"})
POPULATION_ROBUSTNESS_VALUES: frozenset[str] = frozenset({"stable", "scope_sensitive", "untested"})
POPULATION_SCOPE_VALUES: frozenset[str] = frozenset({"primary", "secondary"})

# --- structural constants ---
POSITIONS: list[str] = ["GK", "DEF", "MID", "FWD"]
BLOCK_ORDER: list[str] = ["early", "mid", "late"]

# --- bucketing scheme constants ---
FDR_SIGNALS: frozenset[str] = frozenset({"fdr_avg"})
FDR_ORDINAL_BINS: list[float] = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
FDR_ORDINAL_LABELS: list[str] = ["1", "2", "3", "4", "5"]
DISCRETE_BINS: list[float] = [-np.inf, 0, 1, np.inf]
DISCRETE_LABELS: list[str] = ["0", "1", "2+"]
TWO_STAGE_NZ_LABELS: list[str] = ["low_nz", "mid_nz", "high_nz"]
QUANTILE_N_BINS: int = 5
MIN_N_SHAPE: int = 100
MIN_N_PER_BIN: int = 20
SPARSE_THRESHOLD: int = 10
MIN_ACTIVE_BINS: dict[str, int] = {
    "discrete": 2,
    "ordinal": 3,
    "two_stage": 3,
    "quantile": 4,
}


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
            subset["bin"] = pd.cut(sig, bins=bins, labels=labels, include_lowest=True)
        elif scheme_type == "two_stage":
            nz_mask = sig > 0
            nz_series = sig[nz_mask]
            q_bins = pd.qcut(nz_series, q=3, labels=TWO_STAGE_NZ_LABELS, duplicates="drop")
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
