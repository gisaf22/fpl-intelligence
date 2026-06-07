"""ADR-010 ruling (a) — synth01 is the single weighting authority; serve defers to it.

Model owns weighting. ``model/assemble/synth01_decisions.yaml`` (study-derived) is the
single weighting authority; ``serve/weight_registry.yaml`` must derive from or defer to
it and may not originate study-derived weighting provenance of its own.

Enforced as two checks:
  1. weight_registry declares the authority pointer (synth01_composition_weights).
  2. Every finding key weight_registry references (a component's ``signal_id`` or any
     ``derived_from.findings`` entry) is a finding the authority actually evaluated —
     i.e. its base key (signal@lens:target, position suffix stripped) appears among the
     synth01 decisions. Serve referencing a finding the authority never evaluated would
     be serve *originating* weighting provenance — a ruling-(a) violation.

Editorial components (``signal_id: null`` with no ``derived_from.findings`` — e.g.
fixture_context, goals_scored) are allowed: they are PROVISIONAL-EDITORIAL and make no
study-derivation claim, so they reference no authority finding.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent
WEIGHT_REGISTRY_PATH = REPO_ROOT / "serve/weight_registry.yaml"
SYNTH_DECISIONS_PATH = REPO_ROOT / "model/assemble/synth01_decisions.yaml"


def _base_key(finding_key: str) -> str:
    """Strip a #POSITION suffix (ADR-003), leaving signal@lens:target."""
    return finding_key.split("#", 1)[0]


def _authority_base_keys() -> set[str]:
    """Base finding keys the weighting authority (synth01) evaluated."""
    with SYNTH_DECISIONS_PATH.open() as fh:
        data = yaml.safe_load(fh)
    return {_base_key(d["key"]) for d in data["decisions"]}


def _weight_registry() -> dict:
    with WEIGHT_REGISTRY_PATH.open() as fh:
        return yaml.safe_load(fh)


def _referenced_finding_keys(registry: dict) -> set[str]:
    """All finding keys weight_registry references via signal_id or derived_from.findings."""
    refs: set[str] = set()
    for module in registry["modules"].values():
        for component in module["weights"].values():
            signal_id = component.get("signal_id")
            if signal_id:
                refs.add(signal_id)
            derived = component.get("derived_from") or {}
            for finding in derived.get("findings", []) or []:
                refs.add(finding)
    return refs


def test_weight_registry_declares_the_authority_pointer() -> None:
    """weight_registry points at synth01 as its weighting authority (ADR-010 ruling a)."""
    registry = _weight_registry()
    assert registry.get("synth01_composition_weights") == "model/assemble/synth01_decisions.yaml", (
        "serve/weight_registry.yaml must declare synth01_composition_weights pointing at the "
        "weighting authority model/assemble/synth01_decisions.yaml (ADR-010 ruling a)."
    )


def test_every_referenced_finding_is_backed_by_the_authority() -> None:
    """Serve may only reference weighting findings the authority evaluated (defers, not originates)."""
    authority = _authority_base_keys()
    referenced = {_base_key(k) for k in _referenced_finding_keys(_weight_registry())}
    unbacked = sorted(referenced - authority)
    assert not unbacked, (
        "serve/weight_registry.yaml references weighting findings absent from the authority "
        f"(model/assemble/synth01_decisions.yaml): {unbacked}. Serve must derive from or defer "
        "to the authority, not originate study-derived weighting (ADR-010 ruling a). Either add "
        "the finding to synth01, or drop the signal_id/derived_from claim and mark the component "
        "PROVISIONAL-EDITORIAL."
    )
