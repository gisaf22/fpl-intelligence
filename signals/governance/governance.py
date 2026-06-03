"""Runtime access to per-signal-position evaluation governance metadata.

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

from signals.governance.schema import GovernanceMetadata, GovernanceMetadataError

_EVAL_METADATA_PATH = Path("signals/governance/evaluation_metadata.yaml")

_LIFECYCLE_PRIORITY: dict[str, int] = {
    "approved": 0,
    "candidate": 1,
    "excluded": 2,
    "not_applicable": 3,
}


@functools.lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    """Load and cache the raw evaluation_metadata.yaml findings list."""
    path = _EVAL_METADATA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Evaluation metadata not found at {path}. Run from the project root directory.")
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Evaluation metadata at {path} must be a YAML mapping, got {type(data).__name__}")
    findings: list[dict[str, Any]] = data["evaluation_findings"]
    return findings


def _lens_token(lens: str) -> str:
    """Normalise a lens label to its key token (ADR-003): lowercase, '-' -> '_'."""
    return lens.lower().replace("-", "_")


def _derive_key(signal_entry: dict[str, Any]) -> str:
    """Composite finding key signal@lens:target for an entry (ADR-003).

    Derived from the entry's own fields so the key cannot drift from the row it
    labels; a meta-test asserts the stored ``key`` equals this derivation.
    """
    return f"{signal_entry['signal']}@{_lens_token(signal_entry['lens'])}:{signal_entry['target']}"


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
    findings = _load_raw()
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
            "Add an entry to signals/governance/evaluation_metadata.yaml."
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
    finding_part, sep, position = key.partition("#")
    try:
        signal, lens_target = finding_part.split("@", 1)
        lens_token, target = lens_target.split(":", 1)
    except ValueError as exc:
        raise GovernanceMetadataError(
            f"Malformed composite key {key!r}. Expected 'signal@lens:target[#POSITION]' (ADR-003)."
        ) from exc
    if not signal or not lens_token or not target or (sep and not position):
        raise GovernanceMetadataError(
            f"Malformed composite key {key!r}. Expected 'signal@lens:target[#POSITION]' (ADR-003)."
        )

    for entry in _load_raw():
        if entry["signal"] != signal or _lens_token(entry["lens"]) != lens_token or entry["target"] != target:
            continue
        per_position = entry.get("per_position", {})
        if position:
            if position not in per_position:
                raise GovernanceMetadataError(
                    f"Composite key {key!r} names position {position!r} with no record in "
                    f"finding {finding_part!r}. Add it to signals/governance/evaluation_metadata.yaml."
                )
            return _build_metadata(entry, position, per_position[position])
        # No position suffix: the finding exists; return its first studied position.
        # Callers needing a specific position should pass a #POSITION key.
        first_pos = next(iter(per_position))
        return _build_metadata(entry, first_pos, per_position[first_pos])

    raise GovernanceMetadataError(
        f"No evaluation metadata found for composite key {key!r}. "
        "Add a finding to signals/governance/evaluation_metadata.yaml."
    )
