"""Association-class assignment and flag consolidation for governed signal registries.

These are governance decision functions — they map completed evidence records to
structural classification labels. They live in domain/ so both research/foundation/
and research/registry/ layers can import them without violating layer order.

Precedence in assign_association_class (highest to lowest):
  1. unassessable         — insufficient data or geometry cannot be determined
  2. temporally_unstable  — relationship reverses or vanishes across GW windows;
                            unreliable regardless of average strength
  3. tail_dependent       — association collapses when haul events are removed;
                            signal is only useful for predicting exceptional GWs
  4. upper_tail_concentrated — threshold or saturation geometry; relationship only
                                emerges at the top of the signal range
  5. continuous_monotonic — clean monotonic relationship, state-sensitive panel;
                            the most operationally useful classification
  6. weak_association     — catch-all for signals that are statistically real but
                            structurally unreliable, identity-dominant, or low-confidence

Note on identity_dominant panel class: a signal with panel_class == 'identity_dominant'
falls to weak_association even if geometry is monotonic. This is intentional — the
association is driven by stable between-player quality differences (Salah always
scores more), not by within-player state changes (Salah is in better form than usual).
FPL decisions require the latter. See statistical-framework.md Gap 8.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Inlined to avoid research.kernels.geometry import dependency.
_MONOTONIC_GEOMETRIES: frozenset[str] = frozenset(
    {"monotonic_positive", "monotonic_negative"}
)
_UPPER_TAIL_GEOMETRIES: frozenset[str] = frozenset(
    {"threshold_positive", "threshold_negative", "saturation"}
)

# Haul event constants — single source of truth.
# A haul is a GW where a player scores above HAUL_THRESHOLD_PTS.
# HAUL_DROP_MATERIAL: minimum rho drop (full minus ex-haul) to flag tail sensitivity.
# Both are operational heuristics; no statistical derivation.
HAUL_THRESHOLD_PTS: float = 12.0
HAUL_DROP_MATERIAL: float = 0.20

# Panel class thresholds — single source of truth.
# within_share = abs(rho_within) / abs(rho_pooled).
# Thresholds are operational heuristics; no statistical derivation.
PANEL_CLASS_THRESHOLDS: list[tuple[float, str]] = [
    (0.40, "state_sensitive"),   # within-player dominates — genuine state signal
    (0.20, "mixed"),             # both identity and state contribute
    (0.00, "identity_dominant"), # between-player identity dominates
]


def assign_association_class(row: dict[str, Any]) -> str:
    """Assign a structural association class to a registry row.

    Args:
        row: Registry row dict containing evidence fields. Expected keys:
             support_flags, relationship_geometry, temporal_stability,
             rho_drop, low_confidence, panel_class.
             Missing keys are treated as absent/null — no KeyError raised.

    Returns:
        One of: unassessable | temporally_unstable | tail_dependent |
                upper_tail_concentrated | continuous_monotonic | weak_association

    Note on low_confidence: set upstream when monotonicity_confidence < MONO_CONF_LOW
    (see research/kernels/geometry.py MONO_CONF_LOW). A monotonic signal below this
    bootstrap confidence threshold is classified weak_association, not continuous_monotonic.
    """
    support_flags = str(row.get("support_flags", ""))
    geom = row.get("relationship_geometry", "")

    if "insufficient_support" in support_flags or geom == "unassessable":
        return "unassessable"

    if not geom or geom == "indeterminate":
        return "weak_association"

    # Temporal instability outranks structural characterisation — a relationship
    # that reverses across GW windows cannot be trusted regardless of its shape.
    if row.get("temporal_stability") == "unstable":
        return "temporally_unstable"

    rho_drop = row.get("rho_drop")
    if rho_drop is not None and pd.notna(rho_drop) and float(rho_drop) > HAUL_DROP_MATERIAL:
        return "tail_dependent"

    if geom in _UPPER_TAIL_GEOMETRIES:
        return "upper_tail_concentrated"

    if geom in _MONOTONIC_GEOMETRIES:
        if row.get("low_confidence", False):
            return "weak_association"
        # identity_dominant: pooled rho driven by stable player quality differences,
        # not within-player state changes. Falls to weak_association deliberately.
        if row.get("panel_class", "") in ("state_sensitive", "mixed"):
            return "continuous_monotonic"

    return "weak_association"


def consolidate_flags(*flag_strings: str) -> str:
    """Merge support-flag strings into one comma-separated, de-duplicated value.

    Preserves insertion order of first occurrence. Empty and whitespace-only
    strings are ignored.
    """
    parts = [flag.strip() for flag in flag_strings if flag and flag.strip()]
    return ",".join(dict.fromkeys(parts))
