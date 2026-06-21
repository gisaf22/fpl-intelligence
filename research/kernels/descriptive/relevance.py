"""(signal, position) relevance map for the descriptive foundation layer.

Extracts the "is this signal alive at this position?" determination that
previously lived inline in the deleted ``signal.ipynb`` so that the three
notebooks needing it — ``composition/signal_taxonomy``,
``exposure/signal_presence_by_band`` and ``exposure/signal_correlation`` —
share one source instead of each recomputing the heuristic.

This is an *extraction* of existing logic, not new methodology: the zero-mass /
near-zero-variance thresholds are preserved verbatim from the deleted notebook.

Two signal classes are derived from the domain sets (``domain/signal_layers.py``),
**never hardcoded**:

- **formula inputs** — ``layer_role`` in ``TAUTOLOGICAL_LAYER_ROLES``; their
  same-gameweek association with ``total_points`` is mechanically determined by
  the scoring formula. Valid for distribution / frequency / decomposition; not
  for association with the target.
- **leading indicators** — ``feature_candidate_eligible`` signals *not* in the
  tautological set; valid for association and X-vs-X correlation.

Each (signal, position[, band]) cell is classified into one of:
``formula_input`` / ``formula_input_dead`` / ``leading_alive`` /
``structural_zero``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from domain.fpl_signals import COMPOSITE_SIGNALS
from domain.signal_layers import SIGNAL_LAYER_MAPPING, TAUTOLOGICAL_LAYER_ROLES
from research.kernels.descriptive.distribution import compute_distribution_stats

POSITIONS: tuple[str, ...] = ("GK", "DEF", "MID", "FWD")

# Liveness heuristic — preserved verbatim from the deleted signal.ipynb.
NEAR_ZERO_VARIANCE: float = 2e-4   # catches xg/xa/xgi at GK (all components degenerate -> composite too)
HIGH_ZERO_MASS_PCT: float = 93.0   # data-calibrated: above this = structural absence by football logic

# Relevance classes.
FORMULA_INPUT = "formula_input"
FORMULA_INPUT_DEAD = "formula_input_dead"
LEADING_ALIVE = "leading_alive"
STRUCTURAL_ZERO = "structural_zero"

# Signal classes.
CLASS_FORMULA_INPUT = "formula_input"
CLASS_LEADING_INDICATOR = "leading_indicator"

# Composites that are (near-)exact functions of their parts: including them
# alongside their parts double-counts trivially (xgi = xg + xa; ict_index is
# FPL's weighted aggregate of influence/creativity/threat). Dropping them in
# favour of their parts loses no information. defensive_contribution is
# deliberately *excluded* from this set — it is not an exact sum (r ~ 0.81 with
# its parts), so it and its parts each carry independent signal and are kept.
EXACT_COMPOSITES: frozenset[str] = frozenset(COMPOSITE_SIGNALS) - {"defensive_contribution"}


def formula_input_signals() -> set[str]:
    """Signals whose same-GW association with ``total_points`` is tautological.

    Derived from ``layer_role in TAUTOLOGICAL_LAYER_ROLES``. Valid for
    distribution / frequency / decomposition only — never for association with
    the target.
    """
    return {
        sig
        for sig, meta in SIGNAL_LAYER_MAPPING.items()
        if meta["layer_role"] in TAUTOLOGICAL_LAYER_ROLES
    }


def leading_indicator_signals(*, drop_exact_composites: bool = False) -> set[str]:
    """``feature_candidate_eligible`` signals not in the tautological set.

    Valid for association and X-vs-X correlation.

    Parameters
    ----------
    drop_exact_composites:
        When ``True``, drop the (near-)exact composites ``xgi`` and
        ``ict_index`` in favour of their parts (``EXACT_COMPOSITES``) — used by
        ``signal_correlation`` to avoid trivial composite-vs-part correlations.
        ``defensive_contribution`` is retained (it is not an exact sum).
    """
    tautological = formula_input_signals()
    leading = {
        sig
        for sig, meta in SIGNAL_LAYER_MAPPING.items()
        if meta["feature_candidate_eligible"] and sig not in tautological
    }
    if drop_exact_composites:
        leading -= EXACT_COMPOSITES
    return leading


def signal_class(signal: str) -> str:
    """Return ``formula_input`` or ``leading_indicator`` for a signal."""
    return CLASS_FORMULA_INPUT if signal in formula_input_signals() else CLASS_LEADING_INDICATOR


def _classify(sig_class: str, degenerate: bool) -> str:
    """Map (signal class, degenerate flag) to a relevance class."""
    if sig_class == CLASS_FORMULA_INPUT:
        return FORMULA_INPUT_DEAD if degenerate else FORMULA_INPUT
    return STRUCTURAL_ZERO if degenerate else LEADING_ALIVE


def compute_relevance(
    df: pd.DataFrame,
    *,
    signals: Iterable[str] | None = None,
    group_cols: Sequence[str] = ("position",),
    near_zero_variance: float = NEAR_ZERO_VARIANCE,
    high_zero_mass_pct: float = HIGH_ZERO_MASS_PCT,
) -> pd.DataFrame:
    """Classify each (signal, *group_cols) cell into a relevance class.

    Parameters
    ----------
    df:
        Player-gameweek frame; must contain the signal columns and every column
        in ``group_cols``. The caller owns row filtering (study GW range,
        ``minutes > 0``, DGW exclusion, etc.).
    signals:
        Signals to classify. Defaults to the full relevance universe
        (formula inputs + leading indicators) intersected with ``df`` columns.
    group_cols:
        Columns to stratify by — ``("position",)`` for the (signal, position)
        map, ``("position", "band")`` for the band-aware presence read, or ``()``
        to classify each signal over the whole frame (e.g. a single position
        cohort already filtered by the caller).

    Returns
    -------
    Long DataFrame with columns ``[signal, *group_cols, n, variance,
    zero_mass_pct, signal_class, degenerate, relevance]``.
    """
    universe = (formula_input_signals() | leading_indicator_signals()) if signals is None else set(signals)
    cols = sorted(universe & set(df.columns))
    group_cols = list(group_cols)

    if group_cols:
        groups: Iterable[tuple[object, pd.DataFrame]] = df.groupby(group_cols, observed=True)
    else:
        groups = [((), df)]

    rows: list[dict[str, object]] = []
    for key, gdf in groups:
        key_tuple = key if isinstance(key, tuple) else (key,)
        group_vals = dict(zip(group_cols, key_tuple))
        for sig in cols:
            s = gdf[sig].dropna().astype(float)
            n = len(s)
            stats = compute_distribution_stats(s)
            variance = stats["variance"]
            zero_mass_pct = round((s == 0).mean() * 100, 1) if n else np.nan
            degenerate = bool(
                n == 0
                or (not np.isnan(variance) and variance < near_zero_variance)
                or (not np.isnan(zero_mass_pct) and zero_mass_pct >= high_zero_mass_pct)
            )
            sig_class = signal_class(sig)
            rows.append(
                {
                    "signal": sig,
                    **group_vals,
                    "n": n,
                    "variance": variance,
                    "zero_mass_pct": zero_mass_pct,
                    "signal_class": sig_class,
                    "degenerate": degenerate,
                    "relevance": _classify(sig_class, degenerate),
                }
            )
    return pd.DataFrame(rows)


def leading_alive_signals(relevance_df: pd.DataFrame) -> list[str]:
    """Sorted unique signals classified ``leading_alive`` in ``relevance_df``."""
    alive = relevance_df.loc[relevance_df["relevance"] == LEADING_ALIVE, "signal"]
    return sorted(alive.unique().tolist())
