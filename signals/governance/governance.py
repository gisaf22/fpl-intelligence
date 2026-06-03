"""Runtime access to per-signal-position evaluation governance metadata.

Loads evaluation_metadata.yaml once (cached) and exposes get_signal_governance()
as the single access point. Raises GovernanceMetadataError — never returns None —
so callers cannot silently operate on signals with missing governance records.

Multi-lens disambiguation: when a signal appears in more than one lens study at
the same position (e.g. minutes_roll3 in FORM-006 and AVAIL-001), the entry with
the most favorable lifecycle_state is returned:
  approved > candidate > excluded > not_applicable
Tiebreak: higher rho_pooled (None treated as 0.0).
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


def _build_metadata(signal_entry: dict[str, Any], position: str, pos_data: dict[str, Any]) -> GovernanceMetadata:
    source_decisions = pos_data.get("source_gate_decisions") or []
    return GovernanceMetadata(
        signal=signal_entry["signal"],
        position=position,
        signal_id=signal_entry["signal_id"],
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
