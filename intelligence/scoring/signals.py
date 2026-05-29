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

# Signals that predate the lens-study methodology and have no evaluation_metadata.yaml record.
# These are raw FPL stats promoted via the signal registry before LENS-FORM/AVAIL/MARKET ran.
# Any signal absent from both this set and evaluation_metadata.yaml is an ungoverned signal —
# it must be either added to this allowlist (with justification) or evaluated through a lens.
_PRE_LENS_SIGNAL_ALLOWLIST: frozenset[str] = frozenset({
    "assists",
    "clean_sheets",
    "creativity",
    "goals_conceded",
    "goals_scored",
    "ict_index",
    "influence",
    "saves",
    "threat",
    "xa",
    "xg",
    "xgc",
    "xgi",
    "yellow_cards",
})

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
    no leakage or outcome-component exclusion, rho_pooled is non-null.

    Gate is CI-based (rho_pooled non-null = signal cleared the CI gate during
    lens evaluation). MIN_RHO was removed after SYNTH-01 approved three signals with
    rho < 0.15 via partial rho, confirming the magnitude threshold was not evidence-derived.

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


def _assert_governance_compliance(manifest: SignalManifest) -> None:
    """Raise if any confirmed signal violates evaluation governance.

    Checks each confirmed signal against evaluation_metadata.yaml. Three
    hard-fail conditions (per operational-convergence-plan.md governance pass):
      1. leakage_risk == "direct"       — signal is a scoring-target component
      2. lifecycle_state == "excluded"  — signal was rejected in lens evaluation
      3. downstream_status == "blocked" — evaluation blocked advancement

    Signals on _PRE_LENS_SIGNAL_ALLOWLIST are exempt — they predate the lens
    methodology and have no evaluation_metadata.yaml record by design.
    Any signal absent from both the allowlist and evaluation_metadata.yaml raises
    GovernanceMetadataError: it is ungoverned and must not enter the scoring manifest.
    """
    from signals.evaluation.governance import get_signal_governance
    from signals.lifecycle.lifecycle import LeakageViolationError, LifecycleViolationError
    from signals.lifecycle.schema import GovernanceMetadataError

    for sig in manifest.confirmed:
        try:
            gov = get_signal_governance(sig.signal, sig.position)
        except GovernanceMetadataError:
            if sig.signal not in _PRE_LENS_SIGNAL_ALLOWLIST:
                raise
            continue

        if gov.leakage_risk == "direct":
            raise LeakageViolationError(
                f"GOVERNANCE VIOLATION: {sig.signal}@{sig.position} has direct leakage "
                f"risk but appears as confirmed in scoring manifest. "
                f"Remove from registry. Source: {gov.signal_id}"
            )
        if gov.lifecycle_state == "excluded":
            raise LifecycleViolationError(
                f"GOVERNANCE VIOLATION: {sig.signal}@{sig.position} is excluded from "
                f"lifecycle evaluation but appears as confirmed in scoring manifest. "
                f"Lifecycle enforcement failed. Source: {gov.signal_id}"
            )
        if gov.downstream_status == "blocked":
            raise LifecycleViolationError(
                f"GOVERNANCE VIOLATION: {sig.signal}@{sig.position} has downstream "
                f"status 'blocked' but appears as confirmed in scoring manifest. "
                f"Source: {gov.signal_id}"
            )


def load_manifest_from_path(registry_path: str | Path) -> SignalManifest:
    """Load the registry CSV and return a SignalManifest.

    Enforces lifecycle governance: raises LifecycleViolationError if the
    registry path is an exploratory-state artifact (studies/eda/).
    Also asserts evaluation governance compliance for all confirmed signals.
    """
    from signals.lifecycle.lifecycle import assert_operational_safe
    from signals.lifecycle.loader import load_registry

    assert_operational_safe(registry_path)
    registry = load_registry(registry_path)
    manifest = load_manifest(registry)
    _assert_governance_compliance(manifest)
    return manifest
