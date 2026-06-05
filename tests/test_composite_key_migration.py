"""Migration tests for the composite signal-finding key scheme (ADR-003, Phase 6).

The ID-diet migration replaced opaque codes (FORM-006, AVAIL-001, G-SYNTH1-09) with
self-describing composite keys (signal@lens:target[#POSITION]). These tests are the
contract that a botched migration must fail:

  resolves-all          — every materialised key in both governance YAMLs resolves via
                          the explicit composite lookup, and equals its derived form
                          (the key cannot drift from the row it labels).
  cross-ref consistency — each per-position synth01_decision_id equals
                          f"{finding_key}#{position}" (the parent-finding link self-validates).
  hard-fails-on-missing — a genuinely missing or malformed key raises GovernanceMetadataError,
                          never a silent default.
  collision resolved    — the minutes_roll3 finding (form-rejected vs avail-approved) resolves
                          to two distinct verdicts by key, the failure the bare column hides.
  namespaces retired     — FORM-*/AVAIL-*/MARKET-*/FIXTURE-*/G-SYNTH1-* no longer appear as
                          load-bearing key fields in either YAML.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from domain.registry.governance import (
    _derive_key,
    get_signal_governance_by_key,
)
from domain.registry.schema import GovernanceMetadata, GovernanceMetadataError

pytestmark = pytest.mark.unit

_EVAL_PATH = Path("model/governance/evaluation_metadata.yaml")
_SYNTH_PATH = Path("model/assemble/synth01_decisions.yaml")

# Lens label -> key token, matching governance._lens_token (lowercase, '-' -> '_').
# The synth study's target column maps to the finding-key target token.
_SYNTH_TARGET_TOKEN = {"total_points_next_gw": "total_points", "played_next_gw": "played_next_gw"}

_RETIRED_CODE = re.compile(r"\b(FORM|AVAIL|MARKET|FIXTURE)-\d{3}\b|\bG-SYNTH1-\d{2}\b")


def _load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _findings() -> list[dict]:
    return _load(_EVAL_PATH)["evaluation_findings"]


def _decisions() -> list[dict]:
    return _load(_SYNTH_PATH)["decisions"]


# ---------------------------------------------------------------------------
# resolves-all + derive-consistency
# ---------------------------------------------------------------------------


def test_every_finding_has_composite_key_not_old_code():
    """Every evaluation finding carries `key`, not the retired `signal_id` field."""
    for entry in _findings():
        assert "key" in entry, f"finding {entry.get('signal')!r} missing composite `key` field"
        assert "signal_id" not in entry, f"finding {entry['key']} still carries retired `signal_id`"


def test_finding_key_equals_derived_form():
    """Each stored finding key equals derive(signal, lens, target) — it cannot drift."""
    mismatches = []
    for entry in _findings():
        expected = _derive_key(entry)
        if entry["key"] != expected:
            mismatches.append(f"{entry['key']!r} != derived {expected!r}")
    assert not mismatches, "Finding keys drifted from their fields:\n" + "\n".join(mismatches)


def test_every_finding_key_resolves_by_key():
    """Every finding resolves at every studied position via the explicit composite lookup."""
    failures = []
    for entry in _findings():
        for pos in entry.get("per_position", {}):
            key = f"{entry['key']}#{pos}"
            try:
                gov = get_signal_governance_by_key(key)
                assert isinstance(gov, GovernanceMetadata)
                assert gov.key == entry["key"]
                assert gov.position == pos
            except Exception as exc:  # report which key failed
                failures.append(f"{key}: {type(exc).__name__}: {exc}")
    assert not failures, "Composite keys that failed to resolve:\n" + "\n".join(failures)


def test_every_synth_decision_key_resolves_to_a_finding():
    """Every synth decision key (signal@lens:target#POSITION) resolves to its parent finding."""
    failures = []
    for d in _decisions():
        key = d["key"]
        assert "decision_id" not in d, f"synth decision {key} still carries retired `decision_id`"
        try:
            gov = get_signal_governance_by_key(key)
            assert gov.signal == d["signal"]
            assert gov.position == d["position"]
        except Exception as exc:  # report which key failed
            failures.append(f"{key}: {type(exc).__name__}: {exc}")
    assert not failures, "Synth decision keys that failed to resolve:\n" + "\n".join(failures)


def test_synth_decision_key_is_parent_finding_plus_position():
    """A synth decision key equals its parent finding key + #POSITION (self-validating link)."""
    bad = []
    for d in _decisions():
        lens_tok = d["lens"].lower().replace("-", "_")
        # synth decisions only target total_points / played_next_gw via the lens
        target_tok = _SYNTH_TARGET_TOKEN.get(d.get("target", ""), None)
        # derive parent finding key from signal/lens, target inferred from the resolved finding
        finding_part, _, position = d["key"].partition("#")
        assert position == d["position"], f"{d['key']}: #position {position!r} != field {d['position']!r}"
        assert finding_part.startswith(f"{d['signal']}@{lens_tok}:"), (
            f"{d['key']}: finding part does not match signal@lens ({d['signal']}@{lens_tok})"
        )
        if target_tok is not None:
            assert finding_part == f"{d['signal']}@{lens_tok}:{target_tok}", (
                f"{d['key']}: target token mismatch (expected {target_tok})"
            )
    assert not bad


def test_eval_cross_reference_matches_finding_key_plus_position():
    """Each per-position synth01_decision_id equals f'{finding_key}#{position}'."""
    mismatches = []
    for entry in _findings():
        for pos, pos_data in entry.get("per_position", {}).items():
            xref = pos_data.get("synth01_decision_id")
            if xref is None:
                continue
            expected = f"{entry['key']}#{pos}"
            if xref != expected:
                mismatches.append(f"{entry['key']} {pos}: synth01_decision_id={xref!r} != {expected!r}")
    assert not mismatches, "Cross-references drifted from their finding key:\n" + "\n".join(mismatches)


def test_cross_reference_targets_exist_in_synth_decisions():
    """Every synth01_decision_id cross-reference names a real synth decision key."""
    decision_keys = {d["key"] for d in _decisions()}
    missing = []
    for entry in _findings():
        for pos, pos_data in entry.get("per_position", {}).items():
            xref = pos_data.get("synth01_decision_id")
            if xref is not None and xref not in decision_keys:
                missing.append(f"{entry['key']} {pos}: {xref!r} has no synth01_decisions entry")
    assert not missing, "Dangling cross-references:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# hard-fails-on-missing (no silent default)
# ---------------------------------------------------------------------------


def test_missing_key_raises():
    """A well-formed key naming no finding raises — never returns a default."""
    with pytest.raises(GovernanceMetadataError, match="No evaluation metadata"):
        get_signal_governance_by_key("ghost_signal@form:total_points")


def test_missing_position_in_key_raises():
    """A key naming a real finding but an unstudied position raises."""
    with pytest.raises(GovernanceMetadataError, match="no record"):
        get_signal_governance_by_key("xgi_roll3@form:total_points#NOWHERE")


@pytest.mark.parametrize("malformed", ["not_a_key", "signal@lens", "a@b:", "@form:total_points", "x@:total_points"])
def test_malformed_key_raises(malformed: str):
    """A malformed composite key raises GovernanceMetadataError, not a parse error or default."""
    with pytest.raises(GovernanceMetadataError, match=r"Malformed|No evaluation"):
        get_signal_governance_by_key(malformed)


# ---------------------------------------------------------------------------
# the collision the composite resolves (ADR-003 worked example)
# ---------------------------------------------------------------------------


def test_minutes_roll3_collision_resolves_to_opposite_verdicts_by_key():
    """Same column, opposite verdicts — disambiguated by the composite, not hidden by priority."""
    form = get_signal_governance_by_key("minutes_roll3@form:total_points#MID")
    avail = get_signal_governance_by_key("minutes_roll3@avail:played_next_gw#MID")

    assert form.lens == "FORM" and form.lifecycle_state == "excluded"
    assert avail.lens == "AVAIL" and avail.lifecycle_state == "approved"
    assert form.signal == avail.signal == "minutes_roll3"
    assert form.key != avail.key


# ---------------------------------------------------------------------------
# retired namespaces no longer appear as load-bearing key fields
# ---------------------------------------------------------------------------


def test_no_retired_codes_in_key_fields():
    """No `key:` / `synth01_decision_id:` value in either YAML is a retired code."""
    offenders = []
    for path in (_EVAL_PATH, _SYNTH_PATH):
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line.startswith(("- key:", "key:", "synth01_decision_id:")):
                if _RETIRED_CODE.search(line):
                    offenders.append(f"{path.name}: {line}")
    assert not offenders, "Retired codes still used as keys:\n" + "\n".join(offenders)
