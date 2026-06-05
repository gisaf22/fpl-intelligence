"""ADR-009 Phase C — generator round-trip + drift guard.

The reproduce-before-retire gate: the committed evaluation_metadata.yaml must equal
what model/governance/generate_evaluation_metadata.py produces from the per-lens
verdict records + synth01_decisions.yaml (semantic dict equality — version_note text
and key ordering ignored). This is also the drift guard going forward: edit the
verdict records (or synth decisions) and regenerate, never hand-edit the YAML.
"""

import copy
from pathlib import Path

import pytest
import yaml

from model.governance.generate_evaluation_metadata import generate

pytestmark = pytest.mark.unit

EVAL_META_PATH = Path("model/governance/evaluation_metadata.yaml")


def _normalize(data: dict) -> dict:
    """Drop free-text version_note; index findings by key so list order is irrelevant."""
    out = copy.deepcopy(data)
    out.pop("version_note", None)
    out["evaluation_findings"] = {e["key"]: e for e in out["evaluation_findings"]}
    return out


def _committed() -> dict:
    with EVAL_META_PATH.open() as fh:
        return yaml.safe_load(fh)


def test_generated_matches_committed():
    """Generator output equals the committed decision-of-record (the C gate + drift guard)."""
    assert _normalize(generate()) == _normalize(_committed())


def test_every_committed_finding_is_reproduced():
    """No finding key is dropped or invented by the generator."""
    committed = {e["key"] for e in _committed()["evaluation_findings"]}
    generated = {e["key"] for e in generate()["evaluation_findings"]}
    assert committed == generated


def test_excluded_redundant_has_null_weight():
    """Synth merge records EXCLUDED-REDUNDANT pairs with null composition_weight, role=redundant."""
    for entry in generate()["evaluation_findings"]:
        for pos_data in entry["per_position"].values():
            if pos_data.get("synth01_decision") == "EXCLUDED-REDUNDANT":
                assert pos_data["composition_weight"] is None
                assert pos_data["composition_role"] == "redundant"


def test_approved_pairs_carry_synth_provenance():
    """Every lifecycle_state=approved pair has a synth01_decision_id pointer."""
    for entry in generate()["evaluation_findings"]:
        for pos, pos_data in entry["per_position"].items():
            if pos_data["lifecycle_state"] == "approved":
                assert pos_data.get("synth01_decision_id"), f"{entry['key']} {pos}: approved without synth provenance"
