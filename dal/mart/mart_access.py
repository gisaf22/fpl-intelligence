"""Mart access — MartResult type returned by dal.pipeline.load()."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MartResult:
    """Typed result returned by dal.pipeline.load().

    mart            : full analytical dataset at (player_id, gw) grain
    signals         : governed signal columns present in mart (keyed from FEATURE_REGISTRY)
    gw_range        : (min_gw, max_gw) inclusive bounds present in mart
    data_cutoff_gw  : GW at which the mart was cut off (rows with gw > cutoff are excluded)
    """

    mart: pd.DataFrame
    signals: tuple[str, ...]
    gw_range: tuple[int, int]
    data_cutoff_gw: int
