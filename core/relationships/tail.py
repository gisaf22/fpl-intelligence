"""Tail-dependence relationship helpers."""

from __future__ import annotations

from typing import Any
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from core.relationships.geometry import (
    HAUL_DROP_MATERIAL,
    HAUL_THRESHOLD_PTS,
    MIN_N_HAUL,
    MIN_N_SHAPE,
)


def haul_concentration(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    haul_threshold: float = HAUL_THRESHOLD_PTS,
    min_n: int = MIN_N_SHAPE,
    min_n_haul: int = MIN_N_HAUL,
) -> dict[str, Any]:
    """Quantify how much of the observed association lives in haul events."""
    subset = df[df["position"] == position][[signal, target]].dropna().copy()
    n = len(subset)

    if n < min_n:
        return {
            "rho_full": np.nan,
            "rho_no_haul": np.nan,
            "rho_drop": np.nan,
            "haul_pct": np.nan,
            "n_haul": 0,
            "tail_sensitive": False,
            "support_flag": "insufficient_support",
        }

    sig = subset[signal].astype(float)
    tgt = subset[target].astype(float)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rho_full, _ = spearmanr(sig, tgt)

    no_haul = subset[tgt <= haul_threshold]
    rho_no_haul = np.nan
    if len(no_haul) >= min_n_haul:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rho_no_haul, _ = spearmanr(
                no_haul[signal].astype(float),
                no_haul[target].astype(float),
            )

    haul_mask = tgt > haul_threshold
    n_haul = int(haul_mask.sum())
    haul_pct = round(n_haul / n * 100, 2)

    rho_drop = (
        round(float(rho_full) - float(rho_no_haul), 4)
        if not np.isnan(rho_no_haul)
        else np.nan
    )
    tail_sensitive = not np.isnan(rho_drop) and rho_drop > HAUL_DROP_MATERIAL

    return {
        "rho_full": round(float(rho_full), 4),
        "rho_no_haul": round(float(rho_no_haul), 4)
        if not np.isnan(rho_no_haul)
        else np.nan,
        "rho_drop": rho_drop,
        "haul_pct": haul_pct,
        "n_haul": n_haul,
        "tail_sensitive": tail_sensitive,
        "support_flag": "",
    }
