"""Population validity utilities for EDA-4.

Computes dual-scope rho comparisons and classifies population robustness
for each signal-position pair.

Vocabulary: schema uses {stable, scope_sensitive, untested}.
The EDA_DESIGN.md alternative {robust, moderate_shift, unstable} was not
committed to the schema and is not used here. The thresholds below implement
the design doc definitions mapped onto the schema vocabulary:
  stable          — rho shift < 0.10 AND geometry type unchanged
  scope_sensitive — rho shift 0.10–0.25 OR geometry type changes
  untested        — insufficient data in one or both scopes to compare
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

POPULATION_ROBUSTNESS_VALUES: frozenset[str] = frozenset(
    {"stable", "scope_sensitive", "untested"}
)

# Thresholds are operational heuristics, not significance tests.
# A 0.10 absolute rho shift is the boundary between stable and scope_sensitive.
# For signals with low base rho this is conservative; for high base rho it is
# permissive. Treat classifications as analytical guidance, not statistical claims.
RHO_SHIFT_STABLE_THRESHOLD = 0.10
RHO_SHIFT_SCOPE_SENSITIVE_THRESHOLD = 0.25

MIN_N_FOR_RHO = 30  # minimum observations to compute a meaningful rho


def classify_population_robustness(
    rho_filtered: float | None,
    rho_minimal: float | None,
    geometry_filtered: str,
    geometry_minimal: str,
) -> str:
    """Classify population robustness from a dual-scope rho comparison.

    Args:
        rho_filtered:  Spearman rho on the exposure-filtered population (minutes >= 60).
        rho_minimal:   Spearman rho on the minimally filtered population (any minutes > 0).
        geometry_filtered: Relationship geometry on the filtered population.
        geometry_minimal:  Relationship geometry on the minimal population.

    Returns:
        One of {stable, scope_sensitive, untested}.
    """
    if (
        rho_filtered is None
        or rho_minimal is None
        or np.isnan(rho_filtered)
        or np.isnan(rho_minimal)
    ):
        return "untested"

    rho_shift = abs(rho_filtered - rho_minimal)
    geometry_changed = geometry_filtered != geometry_minimal

    if rho_shift < RHO_SHIFT_STABLE_THRESHOLD and not geometry_changed:
        return "stable"

    if rho_shift <= RHO_SHIFT_SCOPE_SENSITIVE_THRESHOLD or geometry_changed:
        return "scope_sensitive"

    # rho_shift > 0.25 — still classified as scope_sensitive; the shift is
    # material but the vocabulary has no "unstable" tier. The downstream
    # caveat is carried in the magnitude of rho_shift itself.
    return "scope_sensitive"


def compute_dual_scope_rho(
    df: pd.DataFrame,
    signals: list[str],
    positions: list[str],
    target: str = "total_points",
    minutes_col: str = "minutes",
    minutes_threshold: int = 60,
) -> pd.DataFrame:
    """Compute Spearman rho for each signal-position pair under two population scopes.

    Filtered scope:  rows where minutes >= minutes_threshold (primary population).
    Minimal scope:   rows where minutes > 0 (any playing time recorded).

    Args:
        df:                 Prepared analytical dataset with position, signal, target columns.
        signals:            Signal column names to evaluate.
        positions:          Position values to iterate over.
        target:             Target column name.
        minutes_col:        Column used for population scoping.
        minutes_threshold:  Minutes cutoff for the filtered population.

    Returns:
        DataFrame with one row per (signal, position) and columns:
        signal, position, n_filtered, n_minimal, rho_filtered, rho_minimal,
        rho_shift, population_robustness.
    """
    required = {minutes_col, target, "position"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    filtered_pop = df[df[minutes_col] >= minutes_threshold]
    minimal_pop = df[df[minutes_col] > 0]

    rows: list[dict] = []
    for signal in signals:
        if signal not in df.columns:
            continue
        for position in positions:
            f_pos = filtered_pop[filtered_pop["position"] == position][[signal, target]].dropna()
            m_pos = minimal_pop[minimal_pop["position"] == position][[signal, target]].dropna()

            rho_f = _spearman_rho(f_pos, signal, target)
            rho_m = _spearman_rho(m_pos, signal, target)
            rho_shift = (
                round(abs(rho_f - rho_m), 4)
                if rho_f is not None and rho_m is not None
                else None
            )

            rows.append(
                {
                    "signal": signal,
                    "position": position,
                    "n_filtered": len(f_pos),
                    "n_minimal": len(m_pos),
                    "rho_filtered": rho_f,
                    "rho_minimal": rho_m,
                    "rho_shift": rho_shift,
                }
            )

    return pd.DataFrame(rows)


def _spearman_rho(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
) -> float | None:
    """Return Spearman rho or None if the sample is too small or degenerate."""
    if len(df) < MIN_N_FOR_RHO:
        return None
    if df[x_col].nunique() <= 1 or df[y_col].nunique() <= 1:
        return None
    rho, _ = stats.spearmanr(df[x_col], df[y_col])
    return round(float(rho), 4)
