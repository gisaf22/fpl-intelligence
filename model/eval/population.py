"""Canonical evaluation populations - the single definition every phase filters to.

Extracted so ``minutes>0`` / DGW-excluded is defined once, not re-typed in every module. Two views:
the v1 conditional-on-appearance population (default), and the ex-ante full universe including
0-minute blanks (Phase-5 captaincy, where a pick that blanks must score 0).
"""

from __future__ import annotations

import pandas as pd


def canonical(mart: pd.DataFrame) -> pd.DataFrame:
    """v1 population: ``minutes > 0``, DGW excluded, sorted by (player, gw). Conditional on appearance."""
    df = mart[(pd.to_numeric(mart["minutes"], errors="coerce") > 0) & (~mart["is_dgw"].astype(bool))]
    return df.copy().sort_values(["player_id", "gw"]).reset_index(drop=True)


def full_universe(mart: pd.DataFrame) -> pd.DataFrame:
    """Ex-ante universe: DGW excluded but 0-minute blanks RETAINED (for scoring potential blanks)."""
    df = mart[~mart["is_dgw"].astype(bool)]
    return df.copy().sort_values(["player_id", "gw"]).reset_index(drop=True)
