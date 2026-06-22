"""Per-block signal distribution statistics — Rung D (Descriptive).

Computes distribution stats (median, IQR, quartiles, upper-tail percentiles)
for each (signal, position, GW block) slice. The median/IQR feed
assess_distribution_stability in research.kernels.diagnostic.stability; the
p90/p99 tail percentiles characterise how the haul ceiling moves across blocks
(stability of the centre says nothing about the tail).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Minimum observations required in a block to compute meaningful statistics.
MIN_N_FOR_BLOCK_STATS: int = 10


def compute_signal_block_distributions(
    df: pd.DataFrame,
    signals: list[str],
    positions: list[str],
    gw_column: str = "gw",
    gw_blocks: dict[str, tuple[int, int]] | None = None,
) -> pd.DataFrame:
    """Compute per-block distribution statistics for each signal-position pair.

    Args:
        df:         DataFrame containing gw, position, and signal columns.
        signals:    Signal column names to evaluate.
        positions:  Position values to iterate over.
        gw_column:  Name of the gameweek column.
        gw_blocks:  Mapping of block name → (min_gw, max_gw) inclusive.
                    Required — caller supplies the domain-specific block
                    structure; no default is assumed by this kernel.

    Returns:
        DataFrame with one row per (signal, position, block) and columns:
        signal, position, block, n, median, q1, q3, iqr, p90, p99, min_gw, max_gw.
        Rows with n < MIN_N_FOR_BLOCK_STATS have NaN for distribution columns.
    """
    if gw_blocks is None:
        raise ValueError("gw_blocks is required; pass the domain-specific block structure explicitly")

    required = {gw_column, "position"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    valid_signals = [s for s in signals if s in df.columns]
    if not valid_signals:
        return pd.DataFrame()

    # Assign block label once across the full DataFrame — vectorised, no per-row loop.
    _BLOCK_COL = "__block__"
    df = df.copy()
    df[_BLOCK_COL] = None
    for block_name, (min_gw, max_gw) in gw_blocks.items():
        df.loc[df[gw_column].between(min_gw, max_gw), _BLOCK_COL] = block_name

    df = df[df["position"].isin(positions) & df[_BLOCK_COL].notna()]

    rows: list[dict] = []
    for signal in valid_signals:
        for (position, block_name), grp in df.groupby(["position", _BLOCK_COL], observed=True):
            s = grp[signal].dropna()
            n = len(s)
            min_gw, max_gw = gw_blocks[block_name]
            if n < MIN_N_FOR_BLOCK_STATS:
                rows.append(
                    {
                        "signal": signal,
                        "position": position,
                        "block": block_name,
                        "n": n,
                        "median": float("nan"),
                        "q1": float("nan"),
                        "q3": float("nan"),
                        "iqr": float("nan"),
                        "p90": float("nan"),
                        "p99": float("nan"),
                        "min_gw": min_gw,
                        "max_gw": max_gw,
                    }
                )
            else:
                q1, q3 = float(np.percentile(s, 25)), float(np.percentile(s, 75))
                p90, p99 = float(np.percentile(s, 90)), float(np.percentile(s, 99))
                rows.append(
                    {
                        "signal": signal,
                        "position": position,
                        "block": block_name,
                        "n": n,
                        "median": float(np.median(s)),
                        "q1": q1,
                        "q3": q3,
                        "iqr": q3 - q1,
                        "p90": p90,
                        "p99": p99,
                        "min_gw": min_gw,
                        "max_gw": max_gw,
                    }
                )

    return pd.DataFrame(rows)
