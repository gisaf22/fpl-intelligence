"""Read-side lookup of per-signal-position governance decisions.

Consume-side only: this resolves and reads governance decisions; it does not make
them. The decisions live in ``model/governance/evaluation_metadata.yaml`` (the
decision-of-record, authored by governance). This module exists in ``domain`` —
the shared leaf — solely so ``serve`` can consult those decisions at scoring time
without importing ``model`` (forbidden by ``no_serve_to_research_or_model``).

Loads evaluation_metadata.yaml once (cached). Two access points, both raising
GovernanceMetadataError — never returning None — so callers cannot silently
operate on signals with missing governance records:

  get_signal_governance(signal, position)
      The consumer-facing lookup. The scorer holds only a signal column + a
      position, not a lens/target, so this resolves by (signal, position) and,
      when a signal was evaluated under more than one lens at that position
      (the minutes_roll3 collision: form vs avail), returns the entry with the
      most favorable lifecycle_state — approved > candidate > excluded >
      not_applicable, tiebreak higher rho_pooled. This priority disambiguation
      is what the composite key (ADR-003) makes explicit.

  get_signal_governance_by_key(key)
      The explicit composite lookup. Parses a finding key
      signal@lens:target[#POSITION] (ADR-003) and resolves it directly by
      (signal, lens, target) — collision-free, no priority needed. Raises on a
      missing or malformed key.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

from domain.registry.finding_key import FindingKeyError, parse_key
from domain.registry.governance_types import GovernanceMetadata, GovernanceMetadataError

_EVAL_METADATA_PATH = Path("model/governance/evaluation_metadata.yaml")

_LIFECYCLE_PRIORITY: dict[str, int] = {
    "approved": 0,
    "candidate": 1,
    "excluded": 2,
    "not_applicable": 3,
}


@functools.lru_cache(maxsize=1)
def _load_findings() -> list[dict[str, Any]]:
    """Load and cache the evaluation_metadata.yaml findings list.

    The lens is the canonical lowercase token itself (ADR-003 amendment), so key-based
    lookups compare ``entry["lens"]`` directly — no per-entry normalisation step.
    """
    path = _EVAL_METADATA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Evaluation metadata not found at {path}. Run from the project root directory.")
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Evaluation metadata at {path} must be a YAML mapping, got {type(data).__name__}")
    findings: list[dict[str, Any]] = data["evaluation_findings"]
    return findings


# Cautious-grade derivation (ADR-009 §1): a signal that has only a foundation
# downstream_status (no lens study) gets a *provisional* lifecycle. Nothing is
# auto-approved without a study; clearly-unusable foundation verdicts are excluded.
# Unknown/missing status is fail-closed to excluded.
_FOUNDATION_LIFECYCLE: dict[str, str] = {
    "eligible": "candidate",
    "caveated": "candidate",
    "approved": "candidate",
    "blocked": "excluded",
}


def derive_lifecycle_state(downstream_status: str) -> str:
    """Derive a provisional lifecycle_state from a foundation downstream_status (ADR-009 §1).

    Used for signals with no lens record in evaluation_metadata.yaml: their governance
    comes from the foundation registry verdict, mapped cautiously (eligible/caveated →
    candidate, blocked/unknown → excluded). Replaces the former PRE_LENS_SIGNAL_ALLOWLIST.
    """
    return _FOUNDATION_LIFECYCLE.get(downstream_status, "excluded")


def resolve_governance(signal: str, position: str, downstream_status: str = "eligible") -> GovernanceMetadata:
    """Return one normalized governance verdict for a signal-position (ADR-009 §4).

    The single consume-side accessor unifying the two evaluation tiers: if a lens
    record exists in evaluation_metadata.yaml it is returned verbatim; otherwise a
    verdict is *derived* from the foundation ``downstream_status`` (cautious-grade,
    ADR-009 §1) so every governed signal resolves to one shape. Callers never branch
    on "has a lens record" or catch GovernanceMetadataError.
    """
    try:
        return get_signal_governance(signal, position)
    except GovernanceMetadataError:
        return GovernanceMetadata(
            signal=signal,
            position=position,
            key=f"foundation:{signal}",
            lens="FOUNDATION",
            lifecycle_state=derive_lifecycle_state(downstream_status),
            downstream_status=downstream_status,
            leakage_risk="none",  # raw-signal leakage is caught by layer_role at manifest build
            behavioral_reason="foundation-derived verdict (no lens study); ADR-009 §1",
            source_gate_decisions=(),
            rho_pooled=None,
            ci_lower=None,
            ci_upper=None,
        )


def clear_cache() -> None:
    """Drop the cached evaluation metadata.

    Escape hatch for the lru-cached load — call after the YAML is regenerated
    (e.g. a long-running process or a test that rewrites the decision-of-record).
    """
    _load_findings.cache_clear()


def _build_metadata(signal_entry: dict[str, Any], position: str, pos_data: dict[str, Any]) -> GovernanceMetadata:
    source_decisions = pos_data.get("source_gate_decisions") or []
    return GovernanceMetadata(
        signal=signal_entry["signal"],
        position=position,
        key=signal_entry["key"],
        lens=signal_entry["lens"],
        lifecycle_state=pos_data["lifecycle_state"],
        downstream_status=pos_data["downstream_status"],
        leakage_risk=pos_data["leakage_risk"],
        behavioral_reason=pos_data["behavioral_reason"],
        source_gate_decisions=tuple(source_decisions),
        rho_pooled=pos_data.get("rho_pooled"),
        ci_lower=pos_data.get("rho_ci_lower"),
        ci_upper=pos_data.get("rho_ci_upper"),
    )


def get_signal_governance(signal: str, position: str) -> GovernanceMetadata:
    """Return governance metadata for a signal-position pair.

    When a signal appears in multiple lens studies at the same position, returns
    the entry with the most favorable lifecycle_state (approved > candidate >
    excluded > not_applicable). Tiebreak: higher rho_pooled.

    Raises GovernanceMetadataError if no entry exists.
    """
    findings = _load_findings()
    matches: list[GovernanceMetadata] = []

    for entry in findings:
        if entry["signal"] != signal:
            continue
        per_position = entry.get("per_position", {})
        if position not in per_position:
            continue
        matches.append(_build_metadata(entry, position, per_position[position]))

    if not matches:
        raise GovernanceMetadataError(
            f"No evaluation metadata found for signal={signal!r}, position={position!r}. "
            "Add an entry to model/governance/evaluation_metadata.yaml."
        )

    def _sort_key(m: GovernanceMetadata) -> tuple[int, float]:
        priority = _LIFECYCLE_PRIORITY.get(m.lifecycle_state, 99)
        rho_desc = -(m.rho_pooled or 0.0)
        return (priority, rho_desc)

    return min(matches, key=_sort_key)


def get_signal_governance_by_key(key: str) -> GovernanceMetadata:
    """Resolve a composite finding key directly (ADR-003).

    ``key`` is ``signal@lens:target`` for a lens finding, or
    ``signal@lens:target#POSITION`` for a position-scoped (synth-composition)
    finding. Resolution is by (signal, lens, target) — collision-free, no
    lifecycle-priority tiebreak. When the key carries a ``#POSITION`` suffix
    that position's record is returned; otherwise every studied position must be
    resolvable individually via get_signal_governance and the caller should pass
    a position-scoped key.

    Raises GovernanceMetadataError if the key is malformed or names no finding.
    """
    try:
        parsed = parse_key(key)
    except FindingKeyError as exc:
        raise GovernanceMetadataError(str(exc)) from exc
    signal, lens, target, position = parsed.signal, parsed.lens, parsed.target, parsed.position

    for entry in _load_findings():
        if entry["signal"] != signal or entry["lens"] != lens or entry["target"] != target:
            continue
        per_position = entry.get("per_position", {})
        if position:
            if position not in per_position:
                raise GovernanceMetadataError(
                    f"Composite key {key!r} names position {position!r} with no record in "
                    f"finding {signal}@{lens}:{target}. Add it to model/governance/evaluation_metadata.yaml."
                )
            return _build_metadata(entry, position, per_position[position])
        # No position suffix: the finding exists; return its first studied position.
        # Callers needing a specific position should pass a #POSITION key.
        first_pos = next(iter(per_position))
        return _build_metadata(entry, first_pos, per_position[first_pos])

    raise GovernanceMetadataError(
        f"No evaluation metadata found for composite key {key!r}. "
        "Add a finding to model/governance/evaluation_metadata.yaml."
    )
