"""Tail-dependence correlation kernel — domain-agnostic haul-concentration analysis."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from domain.registry.association import HAUL_DROP_MATERIAL, HAUL_THRESHOLD_PTS


def measure_tail_event_dependence(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    haul_threshold: float = HAUL_THRESHOLD_PTS,
    min_n: int = 100,
    min_n_haul: int = 30,
    haul_drop_material: float = HAUL_DROP_MATERIAL,
) -> dict[str, Any]:
    """Measure how much of the observed signal-target association is driven by haul events.

    A haul event is a high-scoring GW (target > haul_threshold). If removing hauls
    collapses the correlation, the signal is only useful for predicting exceptional
    outcomes, not typical GW performance.

    tail_sensitive values:
      True  — assessed and found tail-concentrated (rho_drop > haul_drop_material)
      False — assessed and found non-tail-concentrated
      None  — not assessed (insufficient data); do not interpret as confirmed safe

    Note: only flags *positive* tail concentration (rho drops when hauls removed).
    A signal where removing hauls increases rho returns tail_sensitive=False by design.
    """
    subset = df[df["position"] == position][[signal, target]].dropna().copy()
    n = len(subset)

    if n < min_n:
        return {
            "rho_full": np.nan,
            "rho_no_haul": np.nan,
            "rho_drop": np.nan,
            "haul_pct": np.nan,
            "n_haul": 0,
            "tail_sensitive": None,
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

    rho_drop = round(float(rho_full) - float(rho_no_haul), 4) if not np.isnan(rho_no_haul) else np.nan
    if np.isnan(rho_drop):
        tail_sensitive = None  # too few haul events to assess — not confirmed safe
    else:
        tail_sensitive = bool(rho_drop > haul_drop_material)

    return {
        "rho_full": round(float(rho_full), 4),
        "rho_no_haul": round(float(rho_no_haul), 4) if not np.isnan(rho_no_haul) else np.nan,
        "rho_drop": rho_drop,
        "haul_pct": haul_pct,
        "n_haul": n_haul,
        "tail_sensitive": tail_sensitive,
        "support_flag": "",
    }
