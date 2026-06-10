"""Target distribution visualisation helpers.

Matplotlib plots for EDA-01 target characterisation notebooks.
Owned here — matplotlib belongs in the notebook/presentation layer,
not in kernels or analysis modules.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_cohort_distributions(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
    title: str = "Overall Y Distribution by Cohort",
    figsize: tuple = (16, 4),
) -> plt.Figure:
    n_cohorts = len(cohorts)
    fig, axes = plt.subplots(1, n_cohorts, figsize=figsize, sharey=True)
    axes = [axes] if n_cohorts == 1 else axes

    for i, (cohort_name, cohort_df) in enumerate(cohorts.items()):
        series = cohort_df[value_col].dropna()
        axes[i].hist(series, bins=50, edgecolor="black", alpha=0.7, color="steelblue")
        axes[i].set_title(f"{cohort_name}\n(N={len(series):,})", fontweight="bold")
        axes[i].set_xlabel(value_col)
        if i == 0:
            axes[i].set_ylabel("frequency")
        axes[i].grid(alpha=0.3)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def plot_position_distributions_by_cohort(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
    figsize: tuple = (12, 8),
    position_map: dict | None = None,
) -> dict[str, plt.Figure]:
    figures = {}
    positions = ["GK", "DEF", "MID", "FWD"]

    for cohort_name, cohort_df in cohorts.items():
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        axes = axes.flatten()

        cohort_for_plot = cohort_df.copy()
        if position_map:
            cohort_for_plot["position_code"] = cohort_for_plot["position_code"].map(position_map)

        for i, pos in enumerate(positions):
            pos_data = cohort_for_plot[cohort_for_plot["position_code"] == pos][value_col].dropna()
            axes[i].hist(pos_data, bins=40, edgecolor="black", alpha=0.7, color="steelblue")
            axes[i].set_title(f"{pos} (N={len(pos_data):,})", fontweight="bold")
            axes[i].set_xlabel(value_col)
            axes[i].set_ylabel("frequency")
            axes[i].grid(alpha=0.3)

        fig.suptitle(
            f"{cohort_name.title()} — Y Distribution by Position",
            fontsize=13, fontweight="bold",
        )
        fig.tight_layout()
        figures[cohort_name] = fig

    return figures


def plot_gw_blocks_by_cohort(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
    figsize: tuple = (15, 4),
) -> dict[str, plt.Figure]:
    figures = {}
    colors = {"early": "#2E86AB", "mid": "#A23B72", "late": "#F18F01"}

    for cohort_name, cohort_df in cohorts.items():
        fig, axes = plt.subplots(1, 3, figsize=figsize, sharey=True)

        for i, block in enumerate(["early", "mid", "late"]):
            block_data = cohort_df[cohort_df["gw_block"] == block][value_col].dropna()
            axes[i].hist(block_data, bins=40, color=colors[block], edgecolor="black", alpha=0.7)
            axes[i].set_title(f"{block.capitalize()}\n(N={len(block_data):,})", fontweight="bold")
            axes[i].set_xlabel(value_col)
            if i == 0:
                axes[i].set_ylabel("frequency")
            axes[i].grid(alpha=0.3)

        fig.suptitle(
            f"{cohort_name.title()} — Y by GW Block",
            fontsize=13, fontweight="bold",
        )
        fig.tight_layout()
        figures[cohort_name] = fig

    return figures
