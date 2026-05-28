"""Tests for Phase 4: Runtime Metadata Propagation (Governance Consolidation).

Covers:
- GovernanceMetadata dataclass and GovernanceMetadataError in schema
- get_signal_governance(): happy path, missing entry, multi-lens disambiguation
- get_signal_governance() returns complete GovernanceMetadata for all YAML entries
- _assert_governance_compliance(): LifecycleViolationError for excluded/blocked signals
- _assert_governance_compliance(): LeakageViolationError for direct leakage signals
- Evaluation metadata YAML completeness (all entries have required Phase 4 fields)
"""

from __future__ import annotations

import pytest

from signals.lifecycle.schema import (
    GovernanceMetadata,
    GovernanceMetadataError,
    LEAKAGE_RISK_VALUES,
    LIFECYCLE_STATE_VALUES,
)


# ---------------------------------------------------------------------------
# GovernanceMetadata schema
# ---------------------------------------------------------------------------


class TestGovernanceMetadataSchema:
    def test_frozen_dataclass(self) -> None:
        gov = GovernanceMetadata(
            signal="xgi_roll3",
            position="DEF",
            signal_id="FORM-001",
            lens="FORM",
            lifecycle_state="candidate",
            downstream_status="eligible",
            leakage_risk="none",
            behavioral_reason="test reason",
            source_gate_decisions=("G1-PASS", "G2-PASS"),
            rho_pooled=0.123,
            ci_lower=0.084,
            ci_upper=0.161,
        )
        assert gov.signal == "xgi_roll3"
        assert gov.source_gate_decisions == ("G1-PASS", "G2-PASS")

    def test_immutable(self) -> None:
        gov = GovernanceMetadata(
            signal="xgi_roll3",
            position="DEF",
            signal_id="FORM-001",
            lens="FORM",
            lifecycle_state="candidate",
            downstream_status="eligible",
            leakage_risk="none",
            behavioral_reason="test",
            source_gate_decisions=(),
            rho_pooled=None,
            ci_lower=None,
            ci_upper=None,
        )
        with pytest.raises(Exception):
            gov.signal = "other"  # type: ignore[misc]

    def test_governance_metadata_error_is_value_error(self) -> None:
        exc = GovernanceMetadataError("missing signal")
        assert isinstance(exc, ValueError)

    def test_leakage_risk_vocabulary(self) -> None:
        assert "none" in LEAKAGE_RISK_VALUES
        assert "evaluation_circularity" in LEAKAGE_RISK_VALUES
        assert "direct" in LEAKAGE_RISK_VALUES

    def test_lifecycle_state_vocabulary(self) -> None:
        assert "candidate" in LIFECYCLE_STATE_VALUES
        assert "excluded" in LIFECYCLE_STATE_VALUES
        assert "not_applicable" in LIFECYCLE_STATE_VALUES


# ---------------------------------------------------------------------------
# get_signal_governance — happy path
# ---------------------------------------------------------------------------


class TestGetSignalGovernance:
    def test_known_approved_signal(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("xgi_roll3", "DEF")
        assert gov.signal == "xgi_roll3"
        assert gov.position == "DEF"
        assert gov.signal_id == "FORM-001"
        assert gov.lifecycle_state == "approved"
        assert gov.downstream_status == "approved"
        assert gov.leakage_risk == "none"
        assert gov.rho_pooled == pytest.approx(0.123)
        assert gov.ci_lower == pytest.approx(0.084)
        assert gov.ci_upper == pytest.approx(0.161)

    def test_known_excluded_signal(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("fdr_avg", "DEF")
        assert gov.lifecycle_state == "excluded"
        assert gov.downstream_status == "blocked"
        assert gov.leakage_risk == "none"

    def test_evaluation_circularity_signal(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("points_roll3", "DEF")
        assert gov.leakage_risk == "evaluation_circularity"
        assert gov.lifecycle_state == "excluded"
        assert gov.downstream_status == "blocked"
        assert "G-EDA7-02" in " ".join(gov.source_gate_decisions)

    def test_points_roll5_mid_conditional(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("points_roll5", "MID")
        assert gov.leakage_risk == "evaluation_circularity"
        assert gov.lifecycle_state == "excluded"
        assert gov.downstream_status == "blocked"

    def test_not_applicable_signal(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("xgi_roll3", "GK")
        assert gov.lifecycle_state == "not_applicable"
        assert gov.downstream_status == "blocked"
        assert "G-EDA3-01" in " ".join(gov.source_gate_decisions)

    def test_synth01_approved_purchase_price_def(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("purchase_price", "DEF")
        assert gov.lifecycle_state == "approved"
        assert gov.downstream_status == "approved"

    def test_missing_signal_raises(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        with pytest.raises(GovernanceMetadataError, match="No evaluation metadata"):
            get_signal_governance("nonexistent_signal", "DEF")

    def test_missing_position_raises(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        with pytest.raises(GovernanceMetadataError, match="No evaluation metadata"):
            get_signal_governance("xgi_roll3", "UNKNOWN_POS")

    def test_behavioral_reason_populated(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("transfers_in", "MID")
        assert gov.behavioral_reason
        assert len(gov.behavioral_reason) > 10

    def test_source_gate_decisions_populated(self) -> None:
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("transfers_in", "MID")
        assert len(gov.source_gate_decisions) >= 2
        assert "G1-PASS" in gov.source_gate_decisions


# ---------------------------------------------------------------------------
# Multi-lens disambiguation: minutes_roll3 appears in FORM-006 and AVAIL-001
# ---------------------------------------------------------------------------


class TestMultiLensDisambiguation:
    def test_minutes_roll3_mid_returns_approved(self) -> None:
        """FORM-006 MID is excluded; AVAIL-001 MID is approved (G-SYNTH1-09) — should return approved."""
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("minutes_roll3", "MID")
        assert gov.lifecycle_state == "approved"
        assert gov.lens == "AVAIL"
        assert gov.signal_id == "AVAIL-001"

    def test_minutes_roll3_def_returns_excluded(self) -> None:
        """Both FORM-006 DEF and AVAIL-001 DEF are excluded — should return excluded."""
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("minutes_roll3", "DEF")
        assert gov.lifecycle_state == "excluded"

    def test_minutes_roll3_gk_not_applicable_over_excluded(self) -> None:
        """FORM-006 GK is not_applicable; AVAIL-001 GK is excluded.
        Excluded is more informative (was studied but rejected) — prefer excluded."""
        from signals.evaluation.governance import get_signal_governance

        gov = get_signal_governance("minutes_roll3", "GK")
        assert gov.lifecycle_state == "excluded"


# ---------------------------------------------------------------------------
# _assert_governance_compliance runtime assertions
# ---------------------------------------------------------------------------


def _make_confirmed(signal: str, position: str) -> object:
    """Return a minimal ConfirmedSignal-like object."""
    from intelligence.scoring.contracts import ConfirmedSignal

    return ConfirmedSignal(
        signal=signal,
        position=position,
        rho_pooled=0.20,
        direction=1,
        promotion_class="core_signal",
    )


def _make_manifest(confirmed: list) -> object:
    from intelligence.scoring.contracts import SignalManifest

    return SignalManifest(confirmed=confirmed, caveated=[], positions_covered={})


class TestAssertGovernanceCompliance:
    def test_valid_candidate_passes(self) -> None:
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("xgi_roll3", "DEF")])
        _assert_governance_compliance(manifest)  # should not raise

    def test_excluded_signal_raises(self) -> None:
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("fdr_avg", "DEF")])
        with pytest.raises(ValueError, match="GOVERNANCE VIOLATION"):
            _assert_governance_compliance(manifest)

    def test_evaluation_circularity_signal_raises(self) -> None:
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("points_roll3", "DEF")])
        with pytest.raises(ValueError, match="GOVERNANCE VIOLATION"):
            _assert_governance_compliance(manifest)

    def test_blocked_downstream_raises(self) -> None:
        """purchase_price GK is blocked — should hard-fail."""
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("purchase_price", "GK")])
        with pytest.raises(ValueError, match="GOVERNANCE VIOLATION"):
            _assert_governance_compliance(manifest)

    def test_missing_governance_metadata_passes(self) -> None:
        """Signals not in evaluation_metadata.yaml are governance gaps, not violations.
        Pre-lens signals (goals_scored, assists, etc.) are silently skipped here."""
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("unknown_signal_xyz", "DEF")])
        _assert_governance_compliance(manifest)  # should not raise

    def test_approved_signal_passes(self) -> None:
        """purchase_price DEF is approved by SYNTH-01 (G-SYNTH1-06) — should pass compliance."""
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([_make_confirmed("purchase_price", "DEF")])
        _assert_governance_compliance(manifest)  # should not raise

    def test_empty_manifest_passes(self) -> None:
        from intelligence.scoring.signals import _assert_governance_compliance

        manifest = _make_manifest([])
        _assert_governance_compliance(manifest)  # should not raise


# ---------------------------------------------------------------------------
# YAML completeness: every per-position entry must have the Phase 2 fields
# ---------------------------------------------------------------------------


class TestYAMLCompleteness:
    def _load_yaml(self) -> list[dict]:
        import yaml
        from pathlib import Path

        path = Path("signals/evaluation/evaluation_metadata.yaml")
        with path.open() as fh:
            data = yaml.safe_load(fh)
        return data["evaluation_findings"]

    def test_all_positions_have_behavioral_reason(self) -> None:
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                assert "behavioral_reason" in pos_data, (
                    f"{entry['signal_id']} {pos} missing behavioral_reason"
                )
                assert pos_data["behavioral_reason"], (
                    f"{entry['signal_id']} {pos} behavioral_reason is empty"
                )

    def test_all_positions_have_source_gate_decisions(self) -> None:
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                assert "source_gate_decisions" in pos_data, (
                    f"{entry['signal_id']} {pos} missing source_gate_decisions"
                )
                decisions = pos_data["source_gate_decisions"]
                assert isinstance(decisions, list) and len(decisions) >= 1, (
                    f"{entry['signal_id']} {pos} source_gate_decisions must be non-empty list"
                )

    def test_all_positions_have_leakage_risk(self) -> None:
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                assert "leakage_risk" in pos_data, (
                    f"{entry['signal_id']} {pos} missing leakage_risk"
                )
                assert pos_data["leakage_risk"] in LEAKAGE_RISK_VALUES, (
                    f"{entry['signal_id']} {pos} leakage_risk={pos_data['leakage_risk']!r} "
                    f"not in {LEAKAGE_RISK_VALUES}"
                )

    def test_all_positions_have_downstream_status(self) -> None:
        from signals.lifecycle.schema import DOWNSTREAM_STATUS_VALUES

        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                assert "downstream_status" in pos_data, (
                    f"{entry['signal_id']} {pos} missing downstream_status"
                )
                assert pos_data["downstream_status"] in DOWNSTREAM_STATUS_VALUES, (
                    f"{entry['signal_id']} {pos} downstream_status={pos_data['downstream_status']!r} "
                    f"not in {DOWNSTREAM_STATUS_VALUES}"
                )

    def test_all_positions_have_lifecycle_state(self) -> None:
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                assert "lifecycle_state" in pos_data, (
                    f"{entry['signal_id']} {pos} missing lifecycle_state"
                )
                assert pos_data["lifecycle_state"] in LIFECYCLE_STATE_VALUES, (
                    f"{entry['signal_id']} {pos} lifecycle_state={pos_data['lifecycle_state']!r} "
                    f"not in {LIFECYCLE_STATE_VALUES}"
                )

    def test_evaluation_circularity_signals_are_excluded(self) -> None:
        """Any entry with leakage_risk=evaluation_circularity must be excluded."""
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                if pos_data["leakage_risk"] == "evaluation_circularity":
                    assert pos_data["lifecycle_state"] == "excluded", (
                        f"{entry['signal_id']} {pos}: evaluation_circularity but "
                        f"lifecycle_state={pos_data['lifecycle_state']!r}"
                    )

    def test_blocked_downstream_matches_excluded_lifecycle(self) -> None:
        """All 'blocked' downstream entries must have excluded or not_applicable lifecycle."""
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                if pos_data["downstream_status"] == "blocked":
                    assert pos_data["lifecycle_state"] in {"excluded", "not_applicable"}, (
                        f"{entry['signal_id']} {pos}: downstream_status=blocked but "
                        f"lifecycle_state={pos_data['lifecycle_state']!r}"
                    )

    def test_candidate_lifecycle_is_eligible_or_caveated(self) -> None:
        """All candidate lifecycle entries must have eligible or caveated downstream."""
        for entry in self._load_yaml():
            for pos, pos_data in entry["per_position"].items():
                if pos_data["lifecycle_state"] == "candidate":
                    assert pos_data["downstream_status"] in {"eligible", "caveated"}, (
                        f"{entry['signal_id']} {pos}: lifecycle_state=candidate but "
                        f"downstream_status={pos_data['downstream_status']!r}"
                    )


# ---------------------------------------------------------------------------
# Phase 4 — get_signal_governance() completeness: all YAML entries resolvable
# ---------------------------------------------------------------------------


class TestGetSignalGovernanceCompleteness:
    """get_signal_governance() must return a complete GovernanceMetadata for every
    signal-position pair present in evaluation_metadata.yaml (Phase 4 requirement)."""

    def _load_yaml(self) -> list[dict]:
        import yaml
        from pathlib import Path

        path = Path("signals/evaluation/evaluation_metadata.yaml")
        with path.open() as fh:
            data = yaml.safe_load(fh)
        return data["evaluation_findings"]

    def test_all_yaml_entries_resolvable(self) -> None:
        """Every signal-position pair in YAML is resolvable by get_signal_governance()."""
        from signals.evaluation.governance import get_signal_governance
        from signals.lifecycle.schema import GovernanceMetadata

        failures = []
        for entry in self._load_yaml():
            signal = entry["signal"]
            for pos in entry.get("per_position", {}):
                try:
                    gov = get_signal_governance(signal, pos)
                    assert isinstance(gov, GovernanceMetadata), (
                        f"{entry['signal_id']} ({signal}, {pos}): returned non-GovernanceMetadata"
                    )
                except Exception as exc:
                    failures.append(
                        f"{entry['signal_id']} ({signal}, {pos}): {type(exc).__name__}: {exc}"
                    )
        assert not failures, "get_signal_governance() failed for entries:\n" + "\n".join(failures)

    def test_returned_metadata_has_all_required_fields(self) -> None:
        """Every returned GovernanceMetadata has all required fields populated."""
        from signals.evaluation.governance import get_signal_governance

        failures = []
        for entry in self._load_yaml():
            signal = entry["signal"]
            for pos, pos_data in entry.get("per_position", {}).items():
                try:
                    gov = get_signal_governance(signal, pos)
                except Exception:
                    continue  # covered by test_all_yaml_entries_resolvable

                if not gov.signal:
                    failures.append(f"({signal}, {pos}): signal field empty")
                if not gov.position:
                    failures.append(f"({signal}, {pos}): position field empty")
                if not gov.lifecycle_state:
                    failures.append(f"({signal}, {pos}): lifecycle_state empty")
                if not gov.downstream_status:
                    failures.append(f"({signal}, {pos}): downstream_status empty")
                if not gov.leakage_risk:
                    failures.append(f"({signal}, {pos}): leakage_risk empty")
                if not gov.behavioral_reason:
                    failures.append(f"({signal}, {pos}): behavioral_reason empty")
                if not gov.source_gate_decisions:
                    failures.append(f"({signal}, {pos}): source_gate_decisions empty")

        assert not failures, "GovernanceMetadata fields missing:\n" + "\n".join(failures)

    def test_candidate_entries_have_rho_pooled(self) -> None:
        """Every candidate lifecycle entry has rho_pooled not None in returned metadata."""
        from signals.evaluation.governance import get_signal_governance
        from signals.lifecycle.schema import GovernanceMetadataError

        failures = []
        for entry in self._load_yaml():
            signal = entry["signal"]
            for pos, pos_data in entry.get("per_position", {}).items():
                if pos_data.get("lifecycle_state") != "candidate":
                    continue
                try:
                    gov = get_signal_governance(signal, pos)
                except GovernanceMetadataError:
                    continue
                if gov.rho_pooled is None:
                    failures.append(
                        f"({signal}, {pos}): lifecycle_state=candidate but rho_pooled is None"
                    )
        assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# Phase 4 — Specific violation error types
# ---------------------------------------------------------------------------


class TestViolationErrorTypes:
    """_assert_governance_compliance() must raise LifecycleViolationError for excluded/blocked
    signals and LeakageViolationError for direct leakage signals (Phase 4 requirement).

    Since no current evaluation_metadata.yaml entry has leakage_risk=direct,
    the LeakageViolationError test uses unittest.mock to inject a synthetic record.
    """

    def _make_confirmed(self, signal: str, position: str) -> object:
        from intelligence.scoring.contracts import ConfirmedSignal
        return ConfirmedSignal(
            signal=signal, position=position, rho_pooled=0.20,
            direction=1, promotion_class="core_signal",
        )

    def _make_manifest(self, confirmed: list) -> object:
        from intelligence.scoring.contracts import SignalManifest
        return SignalManifest(confirmed=confirmed, caveated=[], positions_covered={})

    def test_excluded_signal_raises_lifecycle_violation_error(self) -> None:
        """lifecycle_state=excluded raises LifecycleViolationError (not just ValueError)."""
        from intelligence.scoring.signals import _assert_governance_compliance
        from signals.lifecycle.lifecycle import LifecycleViolationError

        manifest = self._make_manifest([self._make_confirmed("fdr_avg", "DEF")])
        with pytest.raises(LifecycleViolationError, match="GOVERNANCE VIOLATION"):
            _assert_governance_compliance(manifest)

    def test_blocked_downstream_raises_lifecycle_violation_error(self) -> None:
        """downstream_status=blocked raises LifecycleViolationError (not just ValueError)."""
        from intelligence.scoring.signals import _assert_governance_compliance
        from signals.lifecycle.lifecycle import LifecycleViolationError

        manifest = self._make_manifest([self._make_confirmed("purchase_price", "GK")])
        with pytest.raises(LifecycleViolationError, match="GOVERNANCE VIOLATION"):
            _assert_governance_compliance(manifest)

    def test_direct_leakage_raises_leakage_violation_error(self) -> None:
        """leakage_risk=direct raises LeakageViolationError (Phase 4 requirement).

        No current evaluation_metadata.yaml entry carries leakage_risk=direct, so
        this test patches get_signal_governance to return a synthetic direct-leakage record.
        """
        from unittest.mock import patch

        from intelligence.scoring.signals import _assert_governance_compliance
        from signals.lifecycle.lifecycle import LeakageViolationError
        from signals.lifecycle.schema import GovernanceMetadata

        synthetic_gov = GovernanceMetadata(
            signal="bonus_roll3",
            position="DEF",
            signal_id="TEST-DIRECT-LEAKAGE",
            lens="TEST",
            lifecycle_state="excluded",
            downstream_status="blocked",
            leakage_risk="direct",
            behavioral_reason="bonus is a direct target component",
            source_gate_decisions=("G-EDA7-06",),
            rho_pooled=0.54,
            ci_lower=None,
            ci_upper=None,
        )
        manifest = self._make_manifest([self._make_confirmed("bonus_roll3", "DEF")])
        with patch(
            "signals.evaluation.governance.get_signal_governance",
            return_value=synthetic_gov,
        ):
            with pytest.raises(LeakageViolationError, match="GOVERNANCE VIOLATION"):
                _assert_governance_compliance(manifest)

    def test_lifecycle_violation_error_is_value_error(self) -> None:
        """LifecycleViolationError is a subclass of ValueError (backward compatibility)."""
        from signals.lifecycle.lifecycle import LifecycleViolationError
        assert issubclass(LifecycleViolationError, ValueError)

    def test_leakage_violation_error_is_value_error(self) -> None:
        """LeakageViolationError is a subclass of ValueError (backward compatibility)."""
        from signals.lifecycle.lifecycle import LeakageViolationError
        assert issubclass(LeakageViolationError, ValueError)
