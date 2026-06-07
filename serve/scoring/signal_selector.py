"""Signal selection and direction resolution against the governed registry.

Single source of truth for which signals enter the composite score and why.
No signal selection logic exists anywhere else in the scorer package.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from domain.registry.verdict import SignalVerdict, resolve_verdict
from domain.signal_layers import LEAKAGE_LAYER_ROLES, OUTCOME_COMPONENT_LAYER_ROLES
from serve.scoring.contracts import CaveatedSignal, ConfirmedSignal, SignalManifest

# Promotion classes eligible for scoring
_SCORING_CLASSES: frozenset[str] = frozenset({"core_signal", "review_signal"})

# Leakage / outcome-component classification is owned by the domain ontology (ADR-010 ruling d):
# serve enforces these at scoring time but references the canonical sets rather than re-listing them.
_LEAKAGE_ROLES = LEAKAGE_LAYER_ROLES
_OUTCOME_COMPONENT_ROLES = OUTCOME_COMPONENT_LAYER_ROLES


def _exclusion_reason(verdict: SignalVerdict) -> str | None:
    """Return a human-readable exclusion reason for one verdict, or None if clear.

    Covers both the foundation-tier checks (leakage/outcome-component via layer_role,
    the rho CI gate) and the governance-decision checks (lifecycle excluded, downstream
    blocked) — read uniformly from the one normalized verdict (ADR-009 §4).
    """
    if verdict.layer_role in _LEAKAGE_ROLES or "leakage" in verdict.interpretation_caveat.lower():
        return "leakage: signal is or directly encodes the scoring target"
    if verdict.layer_role in _OUTCOME_COMPONENT_ROLES:
        return "outcome-component: mechanistically tautological with FPL points"
    if verdict.rho_pooled is None:
        return "no directional information: rho_pooled is null"
    if verdict.lifecycle_state == "excluded":
        return f"governance: excluded in lifecycle evaluation (source: {verdict.source_key})"
    if verdict.downstream_status == "blocked":
        return f"governance: downstream status blocked (source: {verdict.source_key})"
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
    confirmed: list[ConfirmedSignal] = []
    caveated: list[CaveatedSignal] = []

    for row in registry.to_dict(orient="records"):
        verdict = resolve_verdict(row)
        if verdict.promotion_class not in _SCORING_CLASSES:
            continue  # not a scoring candidate (blocked rows have no promotion_class)

        reason = _exclusion_reason(verdict)
        if reason is not None:
            caveated.append(
                CaveatedSignal(
                    signal=verdict.signal,
                    position=verdict.position,
                    reason=reason,
                    promotion_class=verdict.promotion_class,
                )
            )
            continue

        rho = verdict.rho_pooled  # non-null here: _exclusion_reason gates null rho
        assert rho is not None  # narrow float | None -> float (gated above); fail-closed if that ever changes
        confirmed.append(
            ConfirmedSignal(
                signal=verdict.signal,
                position=verdict.position,
                rho_pooled=rho,
                direction=1 if rho > 0 else -1,
                promotion_class=verdict.promotion_class,
                downstream_status=verdict.downstream_status,
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

    Each confirmed signal resolves to one normalized verdict via ``resolve_governance``
    (ADR-009 §4): the lens record if it exists, else a foundation-derived verdict. The
    same three hard-fail conditions apply uniformly to both tiers — no per-tier branching.
    """
    from domain.registry.governance_lookup import resolve_governance
    from domain.registry.lifecycle import LeakageViolationError, LifecycleViolationError

    for sig in manifest.confirmed:
        gov = resolve_governance(sig.signal, sig.position, sig.downstream_status)

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
