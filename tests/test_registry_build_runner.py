import json
from pathlib import Path

import pandas as pd
import pytest

from intelligence.reporting.weekly_report_runner import run_week
from model.governance.promote import promote_registry
from research.registry.build import main, run_registry_build
from signals.governance import load_registry, validate_registry_contract

pytestmark = pytest.mark.unit

SOURCE_REGISTRY_PATH = Path("research/findings/records/eda_03_joint_registry.csv")


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
                        "gw_block": "early" if gw < 2 else "mid" if gw < 4 else "late",
                        "bps": value,
                        "total_points": value * 0.5 + position_index,
                    }
                )
    return pd.DataFrame(rows)


def test_registry_build_writes_finding_and_metadata(tmp_path):
    result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        finding_dir=tmp_path / "gw36",
    )

    assert result.gw == 36
    assert result.data_cutoff_gw == 36
    assert result.n_rows == 104
    assert result.finding_path.exists()
    assert result.finding_path.name == "registry.csv"
    assert result.metadata_path.exists()

    # Build stops at the finding; it does not validate the contract. The finding
    # is nevertheless well-formed (the seed is valid) — promotion validates it.
    generated = load_registry(result.finding_path)
    assert len(generated) == 104

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["gw"] == 36
    assert metadata["data_cutoff_gw"] == 36
    assert metadata["build_mode"] == "packaged"
    assert metadata["source_registry_path"] == str(SOURCE_REGISTRY_PATH)
    assert metadata["source_dataset_path"] == str(SOURCE_REGISTRY_PATH)
    assert metadata["registry_version"]
    assert metadata["schema_version"]
    assert metadata["build_timestamp"]
    assert metadata["row_count"] == 104
    assert metadata["signal_count"] == generated["signal"].nunique()
    assert metadata["position_count"] == 4


def test_registry_build_does_not_validate_contract(tmp_path):
    # Build no longer enforces the contract — that is promotion's job. An invalid
    # source is written to the finding location without raising.
    invalid_registry = tmp_path / "invalid_registry.csv"
    pd.read_csv(SOURCE_REGISTRY_PATH).drop(columns=["signal_layer"]).to_csv(invalid_registry, index=False)

    result = run_registry_build(
        gw=36,
        source_registry_path=invalid_registry,
        finding_dir=tmp_path / "gw36",
    )

    assert result.finding_path.exists()
    assert "signal_layer" not in pd.read_csv(result.finding_path).columns


def test_registry_build_rejects_invalid_gameweek_values(tmp_path):
    with pytest.raises(ValueError, match="gw must be positive"):
        run_registry_build(gw=0, finding_dir=tmp_path)

    with pytest.raises(ValueError, match="data_cutoff_gw cannot be greater"):
        run_registry_build(gw=35, data_cutoff_gw=36, finding_dir=tmp_path)


def test_registry_build_cli_writes_finding_artifacts(tmp_path, capsys):
    finding_dir = tmp_path / "gw36"

    exit_code = main(
        [
            "--gw",
            "36",
            "--source-registry-path",
            str(SOURCE_REGISTRY_PATH),
            "--finding-dir",
            str(finding_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GW36 registry finding built" in captured.out
    assert (finding_dir / "registry.csv").exists()
    assert (finding_dir / "build_metadata.json").exists()


def test_registry_build_computed_mode_writes_finding_and_comparison(tmp_path):
    prepared_data_path = tmp_path / "prepared.csv"
    _prepared_relationship_data().to_csv(prepared_data_path, index=False)

    result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        finding_dir=tmp_path / "gw36",
        build_mode="computed",
        prepared_data_path=prepared_data_path,
        signals=["bps"],
        n_bootstrap=0,
    )

    generated = load_registry(result.finding_path)
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
            finding_dir=tmp_path / "gw36",
            build_mode="computed",
            signals=["bps"],
        )


def test_weekly_runner_consumes_promoted_registry(tmp_path):
    # Full flow: research builds the finding, governance promotes it, then the
    # operational weekly runner consumes the promoted (operational) registry.
    build_result = run_registry_build(
        gw=36,
        source_registry_path=SOURCE_REGISTRY_PATH,
        finding_dir=tmp_path / "finding" / "gw36",
    )

    promotion = promote_registry(
        finding_path=build_result.finding_path,
        gw=36,
        output_dir=tmp_path / "registry" / "gw36",
    )

    weekly_result = run_week(
        gw=36,
        registry_path=promotion.registry_path,
        output_dir=tmp_path / "weekly" / "gw36",
    )

    assert weekly_result.n_rows == 104
    assert weekly_result.weekly_report_path.exists()
    assert weekly_result.registry_snapshot_path.exists()
