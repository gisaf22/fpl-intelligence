"""Lifecycle enforcement tests for the signal registry governance layer.

Validates that:
- Exploratory path detection is correct and deterministic
- Operational consumers (scorer, report runner) reject exploratory registries
- Research consumers (loader) remain flexible
- The lifecycle gate fires with an informative error
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from signals.governance.lifecycle import (
    LifecycleViolationError,
    assert_operational_safe,
    is_exploratory_path,
)
from signals.governance.registry_loader import load_registry

pytestmark = pytest.mark.unit

# The authoritative EDA output — exploratory state by definition
RESEARCH_REGISTRY = Path("research/findings/records/eda_03_joint_registry.csv")

# ---------------------------------------------------------------------------
# Exploratory path detection
# ---------------------------------------------------------------------------


class TestExploratoryPathDetection:
    def test_eda_findings_path_is_exploratory(self):
        assert is_exploratory_path(RESEARCH_REGISTRY)

    def test_findings_subdirectory_is_exploratory(self):
        assert is_exploratory_path(Path("research/findings/records/some_registry.csv"))

    def test_findings_root_is_exploratory(self):
        assert is_exploratory_path(Path("research/findings"))

    def test_outputs_registry_path_is_not_exploratory(self):
        assert not is_exploratory_path(Path("outputs/registry/gw36/registry.csv"))

    def test_signals_lenses_path_is_not_exploratory(self):
        # Lens study directories are investigational, not exploratory
        assert not is_exploratory_path(Path("signals/lenses/form/findings.csv"))

    def test_signals_registry_path_is_not_exploratory(self):
        assert not is_exploratory_path(Path("signals/registry/SIGNAL_REGISTRY.md"))

    def test_tmp_path_is_not_exploratory(self, tmp_path):
        assert not is_exploratory_path(tmp_path / "registry.csv")

    def test_unrelated_path_is_not_exploratory(self):
        assert not is_exploratory_path(Path("core/governance/schema.py"))


# ---------------------------------------------------------------------------
# assert_operational_safe gate
# ---------------------------------------------------------------------------


class TestAssertOperationalSafe:
    def test_rejects_eda_findings_path(self):
        with pytest.raises(LifecycleViolationError):
            assert_operational_safe(RESEARCH_REGISTRY)

    def test_rejects_any_findings_subdirectory(self):
        with pytest.raises(LifecycleViolationError):
            assert_operational_safe(Path("research/findings/records/test.csv"))

    def test_accepts_outputs_registry_path(self):
        # Must not raise — path is not exploratory
        assert_operational_safe(Path("outputs/registry/gw36/registry.csv"))

    def test_accepts_tmp_path(self, tmp_path):
        assert_operational_safe(tmp_path / "registry.csv")

    def test_error_message_identifies_the_path(self):
        with pytest.raises(LifecycleViolationError, match="research/findings"):
            assert_operational_safe(RESEARCH_REGISTRY)

    def test_error_message_mentions_exploratory(self):
        with pytest.raises(LifecycleViolationError, match="exploratory"):
            assert_operational_safe(RESEARCH_REGISTRY)

    def test_error_is_subclass_of_value_error(self):
        with pytest.raises(ValueError):
            assert_operational_safe(RESEARCH_REGISTRY)


# ---------------------------------------------------------------------------
# Scorer lifecycle enforcement
# ---------------------------------------------------------------------------


class TestScorerLifecycleEnforcement:
    def test_load_manifest_from_path_rejects_exploratory_registry(self):
        """Scorer must not consume EDA findings directly."""
        from intelligence.scoring.signal_selector import load_manifest_from_path

        with pytest.raises(LifecycleViolationError, match="exploratory"):
            load_manifest_from_path(RESEARCH_REGISTRY)

    def test_load_manifest_from_path_accepts_non_exploratory_path(self, tmp_path):
        """Path gate does not reject non-exploratory registries.

        Governance compliance runs after the path gate and may raise for signal-level
        violations (e.g. purchase_price GK/MID are review_signal in the EDA registry
        but excluded in evaluation_metadata.yaml). That is correct governance behavior
        — the test verifies only that any error is NOT about the path being exploratory.
        """
        from intelligence.scoring.signal_selector import load_manifest_from_path

        registry_path = tmp_path / "registry.csv"
        shutil.copy(RESEARCH_REGISTRY, registry_path)

        try:
            manifest = load_manifest_from_path(registry_path)
            assert manifest is not None
            assert isinstance(manifest.confirmed, list)
        except LifecycleViolationError as exc:
            assert "exploratory" not in str(exc).lower(), (
                f"Path gate should not fire for non-exploratory path, got: {exc}"
            )


# ---------------------------------------------------------------------------
# Report runner lifecycle enforcement
# ---------------------------------------------------------------------------


class TestReportRunnerLifecycleEnforcement:
    def test_run_week_rejects_exploratory_registry(self, tmp_path):
        """Report runner must not consume EDA findings directly."""
        from intelligence.reporting.weekly_report_runner import run_week

        with pytest.raises(LifecycleViolationError, match="exploratory"):
            run_week(gw=36, registry_path=RESEARCH_REGISTRY, output_dir=tmp_path / "gw36")

    def test_run_week_rejects_exploratory_before_output_is_created(self, tmp_path):
        """Lifecycle gate fires before any output directory is created."""
        from intelligence.reporting.weekly_report_runner import run_week

        output_dir = tmp_path / "gw36"
        with pytest.raises(LifecycleViolationError):
            run_week(gw=36, registry_path=RESEARCH_REGISTRY, output_dir=output_dir)

        assert not output_dir.exists()

    def test_run_week_accepts_non_exploratory_registry(self, tmp_path):
        """Report runner proceeds when registry path is not exploratory."""
        from intelligence.reporting.weekly_report_runner import run_week

        registry_path = tmp_path / "registry.csv"
        shutil.copy(RESEARCH_REGISTRY, registry_path)

        result = run_week(gw=36, registry_path=registry_path, output_dir=tmp_path / "gw36")
        assert result.n_rows == 104
        assert result.registry_snapshot_path.exists()

    def test_gw_validation_fires_before_lifecycle_check(self, tmp_path):
        """gw <= 0 raises ValueError, not LifecycleViolationError."""
        from intelligence.reporting.weekly_report_runner import run_week

        with pytest.raises(ValueError, match="gw must be positive"):
            run_week(gw=0, registry_path=RESEARCH_REGISTRY, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Research consumer flexibility
# ---------------------------------------------------------------------------


class TestResearchConsumerFlexibility:
    def test_load_registry_accepts_exploratory_path(self):
        """Research-mode loader carries no lifecycle restriction."""
        registry = load_registry(RESEARCH_REGISTRY)
        assert len(registry) > 0

    def test_load_registry_accepts_any_non_exploratory_path(self, tmp_path):
        registry_path = tmp_path / "registry.csv"
        shutil.copy(RESEARCH_REGISTRY, registry_path)
        registry = load_registry(registry_path)
        assert len(registry) == len(load_registry(RESEARCH_REGISTRY))

    def test_load_registry_default_is_research_registry(self):
        """The no-arg default should load the research registry, not an operational one."""
        from domain.registry.schema import RESEARCH_REGISTRY_PATH

        registry = load_registry()
        research = load_registry(RESEARCH_REGISTRY_PATH)
        assert len(registry) == len(research)


# ---------------------------------------------------------------------------
# Lifecycle enforcement is deterministic
# ---------------------------------------------------------------------------


class TestLifecycleEnforcementDeterminism:
    def test_same_path_always_classified_the_same(self):
        for _ in range(5):
            assert is_exploratory_path(RESEARCH_REGISTRY)
            assert not is_exploratory_path(Path("outputs/registry/gw36/registry.csv"))

    def test_gate_always_fires_for_eda_path(self):
        for _ in range(5):
            with pytest.raises(LifecycleViolationError):
                assert_operational_safe(RESEARCH_REGISTRY)
