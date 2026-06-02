import shutil
from pathlib import Path

import pandas as pd
import pytest

from intelligence.reporting.weekly_report_runner import main, run_week
from signals.governance.lifecycle import LifecycleViolationError

pytestmark = pytest.mark.unit

RESEARCH_REGISTRY = Path("studies/eda/findings/eda_03_joint_registry.csv")


def test_run_week_writes_registry_snapshot(tmp_path):
    # Operational consumers require a non-exploratory registry path.
    # Copy the research registry to a tmp location to simulate a promoted artifact.
    registry_path = tmp_path / "registry.csv"
    shutil.copy(RESEARCH_REGISTRY, registry_path)

    result = run_week(
        gw=36,
        registry_path=registry_path,
        output_dir=tmp_path / "gw36",
    )

    assert result.gw == 36
    assert result.n_rows == 104
    assert result.registry_snapshot_path.exists()
    assert result.registry_snapshot_path.name == "registry_snapshot.csv"
    assert result.snapshot_changes_path.exists()
    assert result.signal_summary_path.exists()
    assert result.summary_by_position_path.exists()
    assert result.summary_by_layer_path.exists()
    assert result.stable_performance_signals_path.exists()
    assert result.insight_cards_path.exists()
    assert result.weekly_report_path.exists()

    snapshot = pd.read_csv(result.registry_snapshot_path)
    signal_summary = pd.read_csv(result.signal_summary_path)
    assert len(snapshot) == 104
    assert len(signal_summary) == 104
    assert "downstream_status" in snapshot.columns


def test_run_week_rejects_exploratory_registry(tmp_path):
    """run_week must reject registries from studies/eda/ (exploratory state)."""
    with pytest.raises(LifecycleViolationError, match="exploratory"):
        run_week(gw=36, registry_path=RESEARCH_REGISTRY, output_dir=tmp_path / "gw36")


def test_run_week_validates_before_writing_outputs(tmp_path):
    # An invalid registry at a non-exploratory path: lifecycle gate passes,
    # schema validation catches the missing column.
    invalid_registry = tmp_path / "invalid_registry.csv"
    output_dir = tmp_path / "gw36"

    registry = pd.read_csv(RESEARCH_REGISTRY)
    registry = registry.drop(columns=["signal_layer"])
    registry.to_csv(invalid_registry, index=False)

    with pytest.raises(Exception, match="missing required columns"):
        run_week(gw=36, registry_path=invalid_registry, output_dir=output_dir)

    assert not output_dir.exists()


def test_run_week_rejects_non_positive_gameweek(tmp_path):
    # gw validation fires before lifecycle check.
    with pytest.raises(ValueError, match="gw must be positive"):
        run_week(gw=0, registry_path=tmp_path / "registry.csv", output_dir=tmp_path)


def test_runner_cli_writes_snapshot(tmp_path, capsys):
    registry_path = tmp_path / "registry.csv"
    shutil.copy(RESEARCH_REGISTRY, registry_path)
    output_dir = tmp_path / "gw36"

    exit_code = main(
        [
            "--gw",
            "36",
            "--registry-path",
            str(registry_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GW36 weekly snapshot complete" in captured.out
    assert (output_dir / "registry_snapshot.csv").exists()
    assert (output_dir / "snapshot_changes.csv").exists()
    assert (output_dir / "signal_summary.csv").exists()
    assert (output_dir / "insight_cards.csv").exists()
    assert (output_dir / "weekly_report.md").exists()
