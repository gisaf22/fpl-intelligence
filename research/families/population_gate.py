"""Population gate for family lens validate studies.

Asserts that the filtered study population has at least one row in every
position × GW-window cell before analysis begins. An empty cell means the
study's inference is undefined for that stratum — it must be caught here,
not silently propagated into results.
"""
from __future__ import annotations

import pandas as pd


def assert_population_gate(
    population: pd.DataFrame,
    gw_windows: dict[str, tuple[int, int]],
    positions: list[str] | None = None,
) -> None:
    """Raise ValueError if any position × GW-window cell has no rows.

    Args:
        population:  Filtered study population (minutes >= threshold, gw <= max).
        gw_windows:  Window name → (gw_lo, gw_hi) inclusive bounds.
        positions:   Position labels to check; defaults to all found in population.
    """
    if positions is None:
        positions = sorted(population["position_label"].unique())

    empty: list[str] = []
    for pos in positions:
        pos_df = population[population["position_label"] == pos]
        for window_name, (wlo, whi) in gw_windows.items():
            if pos_df[pos_df["gw"].between(wlo, whi)].empty:
                empty.append(f"{pos}/{window_name}")

    if empty:
        raise ValueError(
            f"Population gate failed — empty cells: {', '.join(empty)}. "
            "Study cannot proceed with no observations in these strata."
        )
