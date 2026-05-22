"""EDA-2 signal distribution helpers.

Computation lives in analytics.signals.profiling and analytics.signals.scoping.
This module re-exports those symbols for notebook compatibility and owns
presentation-only helpers (findings template, formatting).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from studies.eda.profiling import (
    BINARY_SIGNALS,
    BLOCK_ORDER,
    CATEGORICAL_NEAR_CONSTANT_THRESHOLD,
    EXCLUDE_REASONS,
    EXTREME_ZERO_MASS_THRESHOLD,
    FLAG_REASONS,
    HIGH_REDUNDANCY_RHO,
    HIGH_ZERO_MASS_THRESHOLD,
    LOW_VARIANCE_CV_THRESHOLD,
    POSITION_MAP,
    POSITIONS,
    STRUCTURAL_ZERO_MAP,
    build_signal_status_table,
    compute_block_homogeneity,
    compute_block_variance,
    compute_variance_flags,
    compute_within_group_redundancy,
    compute_zero_mass,
    split_candidate_signals,
    summarize_signals,
)
from studies.eda.scoping import (
    EXPOSURE_SENSITIVITY_VALUES,
    PREFERRED_POPULATION_VALUES,
    RANK_STABILITY_ROBUST_THRESHOLD,
    RANK_STABILITY_SENSITIVE_THRESHOLD,
    SIGNAL_FAMILY,
    SUPPORT_COLLAPSE_DEGENERATE_THRESHOLD,
    VARIANCE_RATIO_DEGENERATE_THRESHOLD,
    ZERO_DELTA_HIGH_THRESHOLD,
    ZERO_DELTA_MOD_THRESHOLD,
    assign_preferred_population,
    build_exposure_aware_registry,
    compute_dual_scope_summary,
    compute_exposure_sensitivity,
    compute_zero_rate_comparison,
)

__all__ = [
    # profiling
    "BINARY_SIGNALS",
    "BLOCK_ORDER",
    "CATEGORICAL_NEAR_CONSTANT_THRESHOLD",
    "EXCLUDE_REASONS",
    "EXTREME_ZERO_MASS_THRESHOLD",
    "FLAG_REASONS",
    "HIGH_REDUNDANCY_RHO",
    "HIGH_ZERO_MASS_THRESHOLD",
    "LOW_VARIANCE_CV_THRESHOLD",
    "POSITION_MAP",
    "POSITIONS",
    "STRUCTURAL_ZERO_MAP",
    "build_signal_status_table",
    "compute_block_homogeneity",
    "compute_block_variance",
    "compute_variance_flags",
    "compute_within_group_redundancy",
    "compute_zero_mass",
    "split_candidate_signals",
    "summarize_signals",
    # scoping
    "EXPOSURE_SENSITIVITY_VALUES",
    "PREFERRED_POPULATION_VALUES",
    "RANK_STABILITY_ROBUST_THRESHOLD",
    "RANK_STABILITY_SENSITIVE_THRESHOLD",
    "SIGNAL_FAMILY",
    "SUPPORT_COLLAPSE_DEGENERATE_THRESHOLD",
    "VARIANCE_RATIO_DEGENERATE_THRESHOLD",
    "ZERO_DELTA_HIGH_THRESHOLD",
    "ZERO_DELTA_MOD_THRESHOLD",
    "assign_preferred_population",
    "build_exposure_aware_registry",
    "compute_block_variance_scoped",
    "compute_dual_scope_summary",
    "compute_exposure_sensitivity",
    "compute_variance_flags_scoped",
    "compute_zero_rate_comparison",
    # presentation (owned here)
    "build_eda2_findings_template",
]


def compute_variance_flags_scoped(
    dual_summary: pd.DataFrame,
    scope: str = "conditioned",
) -> pd.DataFrame:
    subset = dual_summary[dual_summary["scope"] == scope].copy()
    return compute_variance_flags(subset)


def compute_block_variance_scoped(
    state_conditioned: pd.DataFrame,
    numeric_signals: list[str],
    positions: list[int],
    gw_min: int,
    gw_upper: int,
    min_n: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    early = state_conditioned[state_conditioned["gw"].between(gw_min, 14)]
    mid   = state_conditioned[state_conditioned["gw"].between(15, 24)]
    late  = state_conditioned[state_conditioned["gw"].between(25, gw_upper)]
    blocks = {"early": early, "mid": mid, "late": late}
    return compute_block_variance(blocks, numeric_signals, positions, min_n)


# ---------------------------------------------------------------------------
# Presentation helpers — findings template and formatting
# ---------------------------------------------------------------------------

def build_eda2_findings_template(
    candidate_signals: list[str],
    gw_min: int,
    gw_upper: int,
    min_minutes: int,
    summary_csv_path: Path,
    missing_signals: list[str],
    zero_mass: pd.DataFrame,
    variance_flags: pd.DataFrame,
    variance_pivot: pd.DataFrame,
    homogeneity_numeric: pd.DataFrame,
    homogeneity_categorical: pd.DataFrame,
    redundancy: pd.DataFrame,
    status_table: pd.DataFrame,
) -> list[str]:
    lines = [
        "## EDA-2 — Signal Characterisation (X)",
        "",
        f"Population: GW {gw_min}–{gw_upper}, minutes >= {min_minutes} (mirrors EDA-1 state_primary)",
        f"Candidate signals entering EDA-2: {candidate_signals}",
        f"Signals unavailable in dataset: {missing_signals or 'none'}",
        "",
        "Q2.1 Marginal distributions:",
        f"  Summary CSV: {summary_csv_path}",
        "",
        "Q2.2 Zero mass annotations (diagnostic only — no auto-exclusion):",
    ]
    extreme = zero_mass[zero_mass["annotation"] == "EXTREME_ZERO_MASS"]
    high_zero = zero_mass[zero_mass["annotation"] == "HIGH_ZERO_MASS"]
    for _, row in extreme.iterrows():
        lines.append(f"  {row['signal']} x {row['position']}: zero_pct={row['zero_pct']:.1f}% -> EXTREME_ZERO_MASS (FLAG)")
    for _, row in high_zero.iterrows():
        lines.append(f"  {row['signal']} x {row['position']}: zero_pct={row['zero_pct']:.1f}% -> HIGH_ZERO_MASS (FLAG)")
    if extreme.empty and high_zero.empty:
        lines.append("  None")

    lines.extend(["", "Q2.3 Variance annotations (primary validity gate):"])
    non_ok = variance_flags[variance_flags["annotation"] != "OK"]
    if non_ok.empty:
        lines.append("  None")
    else:
        for _, row in non_ok.iterrows():
            lines.append(
                f"  {row['signal']} x {row['position']}: "
                f"std={row['std']:.4f} iqr={row['iqr']:.4f} cv={_fmt(row['cv'])} "
                f"-> {row['annotation']}"
            )

    lines.extend(["", "Q2.4 Variance across blocks (std % change vs mid):"])
    if not variance_pivot.empty:
        for _, row in variance_pivot.sort_values(["signal", "position"]).iterrows():
            lines.append(
                f"  {row['signal']} x {row['position']}: "
                f"early_vs_mid={_fmt(row.get('early_vs_mid_pct'))}% "
                f"late_vs_mid={_fmt(row.get('late_vs_mid_pct'))}%"
            )
    else:
        lines.append("  No data")

    lines.extend(["", "Q2.5 Distribution stability (KS / median_diff / p90_diff vs mid block):"])
    if not homogeneity_numeric.empty:
        for _, row in homogeneity_numeric.iterrows():
            lines.append(
                f"  {row['signal']} x {row['position']}: "
                f"ks_early={_fmt(row.get('ks_early_mid'))} "
                f"ks_late={_fmt(row.get('ks_late_mid'))} "
                f"median_diff_early={_fmt(row.get('median_diff_pct_early'))}% "
                f"median_diff_late={_fmt(row.get('median_diff_pct_late'))}%"
            )
    if not homogeneity_categorical.empty:
        for _, row in homogeneity_categorical.iterrows():
            lines.append(
                f"  {row['signal']} x {row['position']} (categorical): "
                f"mid_mode={row.get('mid_mode', 'n/a')} mid_top_pct={_fmt(row.get('mid_top_pct'))}"
            )

    lines.extend(["", "Q2.6 Redundancy (semantic groups + temporal variants):"])
    flagged_red = redundancy[redundancy["flag"] == True] if not redundancy.empty else pd.DataFrame()
    if flagged_red.empty:
        lines.append("  None above HIGH_REDUNDANCY threshold")
    else:
        for _, row in flagged_red.iterrows():
            lines.append(
                f"  {row['signal_a']} vs {row['signal_b']} x {row['position']}: "
                f"rho={row['rho']:.3f} -> HIGH_REDUNDANCY (FLAG)"
            )

    lines.extend(["", "Signal status summary:"])
    for status in ["KEEP", "FLAG", "EXCLUDE"]:
        subset = status_table[status_table["status"] == status]
        lines.append(f"  {status}: {len(subset)} signal-position pairs")

    return lines


def _fmt(val: Any) -> str:
    if pd.isna(val):
        return "n/a"
    return f"{val:.1f}"
