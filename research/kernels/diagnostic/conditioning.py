"""Conditioning / heterogeneity utilities.

Tests whether a signal→target relationship is homogeneous across the strata of a
moderator, or whether it is a subgroup artifact (reverses sign or vanishes in some
strata). This is the class-5 kernel of the research funnel: a relationship that only
holds in one subgroup is not yet a trustworthy signal.

Callers supply the moderator already discretised into strata (e.g. minutes-regime
cohorts, fixture-difficulty quartiles). Binning policy is a domain decision and lives
in the calling study, not here.

Vocabulary:
  homogeneous            — same direction and comparable magnitude across strata
  heterogeneous_magnitude — same direction, but magnitude range exceeds tolerance
  heterogeneous_sign      — rho changes sign across strata (the relationship reverses)
  insufficient            — too few strata had enough data to classify
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

# Minimum observations within a stratum to compute a meaningful correlation.
MIN_N_PER_STRATUM = 30

# A sign flip across strata whose magnitudes both clear this floor is material;
# tiny rhos straddling zero are treated as noise, not a true reversal.
SIGN_FLIP_FLOOR = 0.10

# Spread in |rho| across strata above which a same-sign relationship is called
# magnitude-heterogeneous.
MAGNITUDE_SPREAD_THRESHOLD = 0.20


def compute_conditional_rho(
    df: pd.DataFrame,
    signal_col: str,
    target_col: str,
    moderator_col: str,
) -> pd.DataFrame:
    """Spearman rho between signal and target within each stratum of a moderator.

    Args:
        df:            Analytical dataset.
        signal_col:    Signal column name.
        target_col:    Target column name (typically 'total_points').
        moderator_col: Pre-discretised moderator column; each distinct value is a stratum.

    Returns:
        One row per stratum with columns [stratum, n, rho], ordered by stratum value.
        Strata with fewer than MIN_N_PER_STRATUM usable rows, or a constant
        signal/target, yield rho = NaN (and are excluded from classification).

    Raises:
        ValueError: if any required column is missing from df.
    """
    required = {signal_col, target_col, moderator_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    records: list[dict] = []
    for stratum, group in df.groupby(moderator_col, sort=True):
        pair = group[[signal_col, target_col]].dropna()
        n = len(pair)
        rho: float | None = np.nan
        if n >= MIN_N_PER_STRATUM and pair[signal_col].nunique() > 1 and pair[target_col].nunique() > 1:
            r, _ = stats.spearmanr(pair[signal_col], pair[target_col])
            rho = round(float(r), 4)
        records.append({"stratum": stratum, "n": n, "rho": rho})

    return pd.DataFrame.from_records(records, columns=["stratum", "n", "rho"])


def classify_heterogeneity(conditional_rho: pd.DataFrame) -> str:
    """Classify the cross-stratum stability of a signal→target relationship.

    Args:
        conditional_rho: Output of compute_conditional_rho.

    Returns:
        One of {'homogeneous', 'heterogeneous_magnitude', 'heterogeneous_sign',
        'insufficient'}. A sign flip is reported only when at least two strata clear
        SIGN_FLIP_FLOOR in opposite directions, so noise around zero is not mistaken
        for a reversal.
    """
    rhos = conditional_rho["rho"].dropna()
    if len(rhos) < 2:
        return "insufficient"

    material = rhos[rhos.abs() >= SIGN_FLIP_FLOOR]
    if (material > 0).any() and (material < 0).any():
        return "heterogeneous_sign"

    spread = float(rhos.abs().max() - rhos.abs().min())
    if spread >= MAGNITUDE_SPREAD_THRESHOLD:
        return "heterogeneous_magnitude"

    return "homogeneous"
