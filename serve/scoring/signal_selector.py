"""Signal selection and direction resolution against the governed registry.

Single source of truth for which signals enter the composite score and why.
No signal selection logic exists anywhere else in the scorer package.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from domain.registry.schema import PRE_LENS_SIGNAL_ALLOWLIST as _PRE_LENS_SIGNAL_ALLOWLIST
from serve.scoring.contracts import CaveatedSignal, ConfirmedSignal, SignalManifest

# Promotion classes eligible for scoring
_SCORING_CLASSES: frozenset[str] = frozenset({"core_signal", "review_signal"})

# layer_role values that represent leakage (signal is or directly derives the target)
_LEAKAGE_ROLES: frozenset[str] = frozenset({"points_component"})

# layer_role values that are outcome-components (mechanistically tautological to the target)
_OUTCOME_COMPONENT_ROLES: frozenset[str] = frozenset({"contribution_index"})


def _exclusion_reason(row: dict) -> str | None:
    """Return a human-readable exclusion reason, or None if the signal is clear."""
    caveat = str(row.get("interpretation_caveat") or "").lower()
    layer_role = str(row.get("layer_role") or "")

    if layer_role in _LEAKAGE_ROLES or "leakage" in caveat:
        return "leakage: signal is or directly encodes the scoring target"
    if layer_role in _OUTCOME_COMPONENT_ROLES:
        return "outcome-component: mechanistically tautological with FPL points"
    return None


def _governance_exclusion_reason(signal: str, position: str) -> str | None:
    """Return an exclusion reason if the decision-of-record excludes this signal-position.

    Consults evaluation_metadata.yaml (the decision-of-record). A registry may
    promote a signal as a scoring candidate while governance has since excluded
    it (registry↔governance drift); selection must respect the decision, not the
    finding. Signals absent from governance are left to _assert_governance_compliance,
    which enforces the allowlist / ungoverned policy.
    """
    from domain.registry.governance import get_signal_governance
    from domain.registry.schema import GovernanceMetadataError

    try:
        gov = get_signal_governance(signal, position)
    except GovernanceMetadataError:
        return None

    if gov.lifecycle_state == "excluded":
        return f"governance: excluded in lifecycle evaluation (source: {gov.key})"
    if gov.downstream_status == "blocked":
        return f"governance: downstream status blocked (source: {gov.key})"
    return None


def load_manifest(registry: pd.DataFrame) -> SignalManifest:
    """Build a SignalManifest from a validated governed registry DataFrame.

    Confirmed signals: promotion_class in (core_signal, review_signal),
    no leakage or outcome-component exclusion, rho_pooled is non-null.

    Gate is CI-based (rho_pooled non-null = signal cleared the CI gate during
    lens evaluation). MIN_RHO was removed after the synthesis study (set-synth-weights) approved three signals with
    rho < 0.15 via partial rho, confirming the magnitude threshold was not evidence-derived.

    Signals the decision-of-record (evaluation_metadata.yaml) marks excluded or
    blocked are routed to caveated even when the registry promotes them — the
    registry is the finding; governance is the decision, and selection respects
    the decision. All other core/review signals go to caveated with the
    exclusion reason. positions_covered reflects only confirmed signals.
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

        gov_reason = _governance_exclusion_reason(signal, position)
        if gov_reason is not None:
            caveated.append(
                CaveatedSignal(
                    signal=signal,
                    position=position,
                    reason=gov_reason,
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
    hard-fail conditions:
      1. leakage_risk == "direct"       — signal is a scoring-target component
      2. lifecycle_state == "excluded"  — signal was rejected in lens evaluation
      3. downstream_status == "blocked" — evaluation blocked advancement

    Signals on _PRE_LENS_SIGNAL_ALLOWLIST are exempt — they predate the lens
    methodology and have no evaluation_metadata.yaml record by design.
    Any signal absent from both the allowlist and evaluation_metadata.yaml raises
    GovernanceMetadataError: it is ungoverned and must not enter the scoring manifest.
    """
    from domain.registry.governance import get_signal_governance
    from domain.registry.lifecycle import LeakageViolationError, LifecycleViolationError
    from domain.registry.schema import GovernanceMetadataError

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
                f"Remove from registry. Source: {gov.key}"
            )
        if gov.lifecycle_state == "excluded":
            raise LifecycleViolationError(
                f"GOVERNANCE VIOLATION: {sig.signal}@{sig.position} is excluded from "
                f"lifecycle evaluation but appears as confirmed in scoring manifest. "
                f"Lifecycle enforcement failed. Source: {gov.key}"
            )
        if gov.downstream_status == "blocked":
            raise LifecycleViolationError(
                f"GOVERNANCE VIOLATION: {sig.signal}@{sig.position} has downstream "
                f"status 'blocked' but appears as confirmed in scoring manifest. "
                f"Source: {gov.key}"
            )


def load_manifest_from_path(registry_path: str | Path) -> SignalManifest:
    """Load the registry CSV and return a SignalManifest.

    Enforces lifecycle governance: raises LifecycleViolationError if the
    registry path is an exploratory-state artifact (research/findings/).
    Also asserts evaluation governance compliance for all confirmed signals.
    """
    from domain.registry.operational import load_registry

    registry = load_registry(registry_path, operational=True)
    manifest = load_manifest(registry)
    _assert_governance_compliance(manifest)
    return manifest
