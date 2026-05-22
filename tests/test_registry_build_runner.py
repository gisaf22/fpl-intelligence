import json
from pathlib import Path

import pandas as pd
import pytest

from signals.lifecycle import load_registry, validate_registry_contract
from signals.registry.runner import main, run_registry_build
from intelligence.reporting.runner import run_week


SOURCE_REGISTRY_PATH = Path("studies/eda/findings/eda_03_joint_registry.csv")


def _prepared_relationship_data() -> pd.DataFrame:
    rows = []
    for position_index, position in enumerate(["GK", "DEF", "MID", "FWD"]):
        for player_id in range(20):
            for gw in range(5):
                value = player_id + gw + position_index
                rows.append(
                    {
                        "player_id": f"{position}-{player_id}",
                        "position": position,
                        "gw": gw + 1,
                        "gw_block": "early"
                        if gw < 2
                        else "mid"
                        if gw < 4
                        else "late",
                        "bps": value,
                        "total_points": value * 0.5 + position_index,
                    }
                )
    return pd.DataFrame(rows)


def test_registry_build_writes_valid_registry_and_metadata(tmp_path):
    result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        output_dir=tmp_path / "gw36",
    )

    assert result.gw == 36
    assert result.data_cutoff_gw == 36
    assert result.n_rows == 116
    assert result.registry_path.exists()
    assert result.registry_path.name == "registry.csv"
    assert result.metadata_path.exists()

    generated = load_registry(result.registry_path)
    validate_registry_contract(generated)
    assert len(generated) == 116

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["gw"] == 36
    assert metadata["data_cutoff_gw"] == 36
    assert metadata["build_mode"] == "packaged"
    assert metadata["source_registry_path"] == str(SOURCE_REGISTRY_PATH)
    assert metadata["source_dataset_path"] == str(SOURCE_REGISTRY_PATH)
    assert metadata["registry_version"]
    assert metadata["schema_version"]
    assert metadata["build_timestamp"]
    assert metadata["row_count"] == 116
    assert metadata["signal_count"] == generated["signal"].nunique()
    assert metadata["position_count"] == 4


def test_registry_build_validates_before_writing_outputs(tmp_path):
    invalid_registry = tmp_path / "invalid_registry.csv"
    output_dir = tmp_path / "gw36"

    registry = pd.read_csv(SOURCE_REGISTRY_PATH).drop(columns=["signal_layer"])
    registry.to_csv(invalid_registry, index=False)

    with pytest.raises(Exception, match="missing required columns"):
        run_registry_build(
            gw=36,
            source_registry_path=invalid_registry,
            output_dir=output_dir,
        )

    assert not output_dir.exists()


def test_registry_build_rejects_invalid_gameweek_values(tmp_path):
    with pytest.raises(ValueError, match="gw must be positive"):
        run_registry_build(gw=0, output_dir=tmp_path)

    with pytest.raises(ValueError, match="data_cutoff_gw cannot be greater"):
        run_registry_build(gw=35, data_cutoff_gw=36, output_dir=tmp_path)


def test_registry_build_cli_writes_artifacts(tmp_path, capsys):
    output_dir = tmp_path / "gw36"

    exit_code = main(
        [
            "--gw",
            "36",
            "--source-registry-path",
            str(SOURCE_REGISTRY_PATH),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GW36 registry build complete" in captured.out
    assert (output_dir / "registry.csv").exists()
    assert (output_dir / "build_metadata.json").exists()


def test_registry_build_computed_mode_writes_valid_registry_and_comparison(tmp_path):
    prepared_data_path = tmp_path / "prepared.csv"
    _prepared_relationship_data().to_csv(prepared_data_path, index=False)

    result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        output_dir=tmp_path / "gw36",
        build_mode="computed",
        prepared_data_path=prepared_data_path,
        signals=["bps"],
        n_bootstrap=0,
    )

    generated = load_registry(result.registry_path)
    validate_registry_contract(generated)
    assert result.build_mode == "computed"
    assert result.source_dataset_path == prepared_data_path
    assert result.comparison_path is not None
    assert result.comparison_path.exists()
    assert len(generated) == 4
    assert set(generated["signal"]) == {"bps"}

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["build_mode"] == "computed"
    assert metadata["source_dataset_path"] == str(prepared_data_path)
    assert metadata["source_registry_path"] == str(SOURCE_REGISTRY_PATH)
    assert metadata["comparison_summary"]["candidate_rows"] == 4


def test_registry_build_computed_mode_requires_prepared_data_path(tmp_path):
    with pytest.raises(ValueError, match="require prepared_data_path"):
        run_registry_build(
            gw=36,
            output_dir=tmp_path / "gw36",
            build_mode="computed",
            signals=["bps"],
        )


def test_weekly_runner_consumes_generated_registry(tmp_path):
    build_result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        output_dir=tmp_path / "registry" / "gw36",
    )

    weekly_result = run_week(
        gw=36,
        registry_path=build_result.registry_path,
        output_dir=tmp_path / "weekly" / "gw36",
    )

    assert weekly_result.n_rows == 116
    assert weekly_result.weekly_report_path.exists()
    assert weekly_result.registry_snapshot_path.exists()
