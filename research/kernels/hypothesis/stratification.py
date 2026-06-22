"""Quintile stratification for signal evaluation studies.

Splits a study population slice into five equal-rank groups and measures how
the target mean changes across groups. Used to decide whether a signal's
association with the target is practically meaningful (decision-relevant) beyond
merely having a non-zero rank correlation.

The ``bidirectional`` flag controls monotonicity semantics:
  - ``False`` (default): only monotone-increasing is accepted. Use for signals
    with positive expected direction (form, market, availability lenses).
  - ``True``: monotone-increasing OR monotone-decreasing is accepted, and the
    absolute Q5-Q1 gap is used for the decision-relevance threshold. Use when
    a signal's expected direction is negative (e.g. fixture difficulty rating).
"""

from __future__ import annotations

import pandas as pd

MIN_N = 25


def quintile_stratification(
    df: pd.DataFrame,
    signal: str,
    signal_id: str,
    position: str,
    block: str,
    target: str,
    bidirectional: bool = False,
) -> dict | None:
    """Compute quintile-stratified target means for a signal-position slice.

    Splits the population into five equal-rank groups on the signal and measures
    the target mean per group. Returns the five means, the Q5-Q1 gap, and whether
    the pattern is monotonic.

    The decision-relevance verdict (gap >= threshold and monotonic) is a study
    design decision — it belongs in the study's qualification gate, not here.
    The caller applies the threshold using the returned ``q5_q1_gap`` and
    ``is_monotonic`` fields.

    Args:
        df:            DataFrame containing ``signal`` and ``target`` columns.
        signal:        Predictor column name.
        signal_id:     Registry identifier for the signal (e.g. "FORM-001").
        position:      Position label for this slice (e.g. "DEF").
        block:         GW block label (e.g. "full", "early").
        target:        Target column name. Passed explicitly so the call site
                       documents whether it is same-GW or lag-1.
        bidirectional: If True, accepts monotone-decreasing as well as
                       monotone-increasing. ``is_monotonic`` covers both
                       directions. Default False.

    Returns:
        Dict with quintile means, q5_q1_gap, and is_monotonic, or None when
        there are fewer than MIN_N valid paired observations or quintile
        construction fails.
    """
    valid = df[[signal, target]].dropna()
    if len(valid) < MIN_N:
        return None
    try:
        ranked = valid.copy()
        ranked["quintile"] = pd.qcut(
            ranked[signal].rank(method="first"),
            5,
            labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
        )
        means_s = ranked.groupby("quintile", observed=True)[target].mean()
        if not all(f"Q{i}" in means_s.index for i in range(1, 6)):
            return None
        means = [float(means_s[f"Q{i}"]) for i in range(1, 6)]
        gap = means[4] - means[0]

        is_monotonic_up = all(means[i] <= means[i + 1] for i in range(4))
        if bidirectional:
            is_monotonic_down = all(means[i] >= means[i + 1] for i in range(4))
            is_monotonic = is_monotonic_up or is_monotonic_down
        else:
            is_monotonic = is_monotonic_up

        return {
            "signal_id": signal_id,
            "signal": signal,
            "position": position,
            "block": block,
            "target": target,
            "q1_mean": round(means[0], 3),
            "q2_mean": round(means[1], 3),
            "q3_mean": round(means[2], 3),
            "q4_mean": round(means[3], 3),
            "q5_mean": round(means[4], 3),
            "q5_q1_gap": round(gap, 3),
            "is_monotonic": is_monotonic,
        }
    except Exception:
        return None
