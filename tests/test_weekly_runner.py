from pathlib import Path

import pandas as pd
import pytest

from weekly.runner import main, run_week


REGISTRY_PATH = Path("research/eda/findings/eda_03_joint_registry.csv")


def test_run_week_writes_registry_snapshot(tmp_path):
    result = run_week(
        gw=36,
        registry_path=REGISTRY_PATH,
        output_dir=tmp_path / "gw36",
    )

    assert result.gw == 36
    assert result.n_rows == 116
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
    assert len(snapshot) == 116
    assert len(signal_summary) == 116
    assert "downstream_status" in snapshot.columns


def test_run_week_validates_before_writing_outputs(tmp_path):
    invalid_registry = tmp_path / "invalid_registry.csv"
    output_dir = tmp_path / "gw36"

    registry = pd.read_csv(REGISTRY_PATH)
    registry = registry.drop(columns=["signal_layer"])
    registry.to_csv(invalid_registry, index=False)

    with pytest.raises(Exception, match="missing required columns"):
        run_week(gw=36, registry_path=invalid_registry, output_dir=output_dir)

    assert not output_dir.exists()


def test_run_week_rejects_non_positive_gameweek(tmp_path):
    with pytest.raises(ValueError, match="gw must be positive"):
        run_week(gw=0, registry_path=REGISTRY_PATH, output_dir=tmp_path)


def test_runner_cli_writes_snapshot(tmp_path, capsys):
    output_dir = tmp_path / "gw36"

    exit_code = main(
        [
            "--gw",
            "36",
            "--registry-path",
            str(REGISTRY_PATH),
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
