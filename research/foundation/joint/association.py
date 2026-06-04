"""Association-class helpers — study-layer copy.

Geometry constants inlined; no signals.* imports.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

HAUL_DROP_MATERIAL = 0.20
MONOTONIC_GEOMETRIES: frozenset[str] = frozenset(
    {"monotonic_positive", "monotonic_negative"}
)
UPPER_TAIL_GEOMETRIES: frozenset[str] = frozenset(
    {"threshold_positive", "threshold_negative", "saturation"}
)


def assign_association_class(row: dict[str, Any]) -> str:
    """Assign a structural association class to a registry row."""
    support_flags = str(row.get("support_flags", ""))
    geom = row.get("relationship_geometry", "")

    if "insufficient_support" in support_flags or geom == "unassessable":
        return "unassessable"

    if not geom or geom == "indeterminate":
        return "weak_association"

    if row.get("temporal_stability") == "unstable":
        return "temporally_unstable"

    rho_drop = row.get("rho_drop")
    if pd.notna(rho_drop) and rho_drop > HAUL_DROP_MATERIAL:
        return "tail_dependent"

    if geom in UPPER_TAIL_GEOMETRIES:
        return "upper_tail_concentrated"

    if geom in MONOTONIC_GEOMETRIES:
        if row.get("low_confidence", False):
            return "weak_association"
        if row.get("panel_class", "") in ("state_sensitive", "mixed"):
            return "continuous_monotonic"

    return "weak_association"


def consolidate_flags(*flag_strings: str) -> str:
    """Merge support-flag strings into one comma-separated, de-duplicated value."""
    parts = [flag.strip() for flag in flag_strings if flag and flag.strip()]
    return ",".join(dict.fromkeys(parts))
