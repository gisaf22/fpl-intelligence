"""Contract test for the composite signal-finding key scheme (ADR-003, Phase 6).

The ID-diet migration replaced opaque codes (FORM-006, AVAIL-001, G-SYNTH1-09) with
self-describing composite keys (signal@lens:target[#POSITION]).

Most of this contract was anchored on evaluation_metadata.yaml and the
governance_lookup/governance_types resolver, all since retired. What survives is the
check that still has a live artefact behind it: each per-position synth decision key
equals f"{finding_key}#{position}", so the parent-finding link self-validates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_SYNTH_PATH = Path("model/assemble/synth01_decisions.yaml")

# Lens label -> key token, matching governance._lens_token (lowercase, '-' -> '_').
# The synth study's target column maps to the finding-key target token.
_SYNTH_TARGET_TOKEN = {"total_points_next_gw": "total_points", "played_next_gw": "played_next_gw"}


def _load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _decisions() -> list[dict]:
    return _load(_SYNTH_PATH)["decisions"]


def test_synth_decision_key_is_parent_finding_plus_position():
    """A synth decision key equals its parent finding key + #POSITION (self-validating link)."""
    for d in _decisions():
        lens_tok = d["lens"].lower().replace("-", "_")
        # synth decisions only target total_points / played_next_gw via the lens
        target_tok = _SYNTH_TARGET_TOKEN.get(d.get("target", ""), None)
        finding_part, _, position = d["key"].partition("#")
        assert position == d["position"], f"{d['key']}: #position {position!r} != field {d['position']!r}"
        assert finding_part.startswith(f"{d['signal']}@{lens_tok}:"), (
            f"{d['key']}: finding part does not match signal@lens ({d['signal']}@{lens_tok})"
        )
        if target_tok is not None:
            assert finding_part == f"{d['signal']}@{lens_tok}:{target_tok}", (
                f"{d['key']}: target token mismatch (expected {target_tok})"
            )
