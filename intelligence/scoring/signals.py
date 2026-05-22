"""Signal selection and direction resolution against the governed registry.

Single source of truth for which signals enter the composite score and why.
No signal selection logic exists anywhere else in the scorer package.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from intelligence.scoring.contracts import CaveatedSignal, ConfirmedSignal, SignalManifest

# Promotion classes eligible for scoring
_SCORING_CLASSES: frozenset[str] = frozenset({"core_signal", "review_signal"})

# layer_role values that represent leakage (signal is or directly derives the target)
_LEAKAGE_ROLES: frozenset[str] = frozenset({"points_component"})

# layer_role values that are outcome-components (mechanistically tautological to the target)
_OUTCOME_COMPONENT_ROLES: frozenset[str] = frozenset({"contribution_index"})

# Minimum absolute rho required for a signal to carry meaningful directional information
MIN_RHO: float = 0.15


def _exclusion_reason(row: dict) -> str | None:
    """Return a human-readable exclusion reason, or None if the signal is clear."""
    caveat = str(row.get("interpretation_caveat") or "").lower()
    layer_role = str(row.get("layer_role") or "")

    if layer_role in _LEAKAGE_ROLES or "leakage" in caveat:
        return "leakage: signal is or directly encodes the scoring target"
    if layer_role in _OUTCOME_COMPONENT_ROLES:
        return "outcome-component: mechanistically tautological with FPL points"
    return None


def load_manifest(registry: pd.DataFrame) -> SignalManifest:
    """Build a SignalManifest from a validated governed registry DataFrame.

    Confirmed signals: promotion_class in (core_signal, review_signal),
    no leakage or outcome-component exclusion, abs(rho_pooled) >= MIN_RHO.

    All other core/review signals go to caveated with the exclusion reason.
    positions_covered reflects only confirmed signals.
    """
    eligible = registry[registry["promotion_class"].isin(_SCORING_CLASSES)].copy()

    confirmed: list[ConfirmedSignal] = []
    caveated: list[CaveatedSignal] = []

    for row in eligible.to_dict(orient="records"):
        signal = str(row["signal"])
        position = str(row["position"])
        promotion_class = str(row["promotion_class"])
        rho = row.get("rho_pooled")

        reason = _exclusion_reason(row)
        if reason is not None:
            caveated.append(
                CaveatedSignal(
                    signal=signal,
                    position=position,
                    reason=reason,
                    promotion_class=promotion_class,
                )
            )
            continue

        # rho must be present and meet the minimum strength threshold
        if rho is None or (rho != rho):  # NaN check via self-inequality
            caveated.append(
                CaveatedSignal(
                    signal=signal,
                    position=position,
                    reason="no directional information: rho_pooled is null",
                    promotion_class=promotion_class,
                )
            )
            continue

        if abs(rho) < MIN_RHO:
            caveated.append(
                CaveatedSignal(
                    signal=signal,
                    position=position,
                    reason=f"weak association: |rho|={abs(rho):.3f} below threshold {MIN_RHO}",
                    promotion_class=promotion_class,
                )
            )
            continue

        confirmed.append(
            ConfirmedSignal(
                signal=signal,
                position=position,
                rho_pooled=float(rho),
                direction=1 if rho > 0 else -1,
                promotion_class=promotion_class,
            )
        )

    positions_covered: dict[str, list[str]] = {}
    for sig in confirmed:
        positions_covered.setdefault(sig.position, []).append(sig.signal)

    return SignalManifest(
        confirmed=confirmed,
        caveated=caveated,
        positions_covered=positions_covered,
    )


def load_manifest_from_path(registry_path: str | Path) -> SignalManifest:
    """Load the registry CSV and return a SignalManifest.

    Enforces lifecycle governance: raises LifecycleViolationError if the
    registry path is an exploratory-state artifact (studies/eda/).
    """
    from signals.lifecycle.lifecycle import assert_operational_safe
    from signals.lifecycle.loader import load_registry

    assert_operational_safe(registry_path)
    registry = load_registry(registry_path)
    return load_manifest(registry)
