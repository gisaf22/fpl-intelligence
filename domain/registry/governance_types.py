"""Runtime governance metadata contract.

The typed contract for per-signal-position governance verdicts read from
``model/governance/evaluation_metadata.yaml``. This is distinct from the
registry-CSV schema (``domain.registry.schema``): that file defines what a
valid registry *row* is; this one defines what a governance *verdict* is.
The access logic that populates these types lives in
``domain.registry.governance``.
"""

from __future__ import annotations

from dataclasses import dataclass

LIFECYCLE_STATE_VALUES: frozenset[str] = frozenset({"candidate", "excluded", "not_applicable", "approved"})
LEAKAGE_RISK_VALUES: frozenset[str] = frozenset({"none", "evaluation_circularity", "direct"})


@dataclass(frozen=True)
class GovernanceMetadata:
    """Runtime governance container for a single signal-position pair.

    Populated from evaluation_metadata.yaml via get_signal_governance().
    When a signal appears in multiple lens studies, the most favorable
    lifecycle_state is returned (approved > candidate > excluded > not_applicable).
    """

    signal: str
    position: str
    key: str  # composite finding key, e.g. "xgi_roll3@form:total_points" (ADR-003)
    lens: str  # e.g. "form"
    lifecycle_state: str  # approved | candidate | excluded | not_applicable
    downstream_status: str  # eligible | caveated | blocked
    leakage_risk: str  # none | evaluation_circularity | direct
    behavioral_reason: str
    source_gate_decisions: tuple[str, ...]
    rho_pooled: float | None
    ci_lower: float | None
    ci_upper: float | None


class GovernanceMetadataError(ValueError):
    """Raised when evaluation governance metadata is missing or unresolvable."""
