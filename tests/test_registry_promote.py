import json
from pathlib import Path

import pandas as pd
import pytest

from domain.registry.lifecycle import LifecycleViolationError
from model.governance.promote import main, promote_registry
from signals.governance import load_registry, validate_registry_contract

pytestmark = pytest.mark.unit

FINDING_PATH = Path("research/findings/records/eda_03_joint_registry.csv")


def test_promote_publishes_validated_finding(tmp_path):
    output_dir = tmp_path / "registry" / "gw36"

    result = promote_registry(finding_path=FINDING_PATH, gw=36, output_dir=output_dir)

    assert result.gw == 36
    assert result.n_rows == 104
    assert result.registry_path.exists()
    assert result.registry_path.name == "registry.csv"
    assert result.metadata_path.exists()

    promoted = load_registry(result.registry_path)
    validate_registry_contract(promoted)
    assert len(promoted) == 104

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["gw"] == 36
    assert metadata["finding_path"] == str(FINDING_PATH)
    assert metadata["row_count"] == 104
    assert metadata["validated"] is True


def test_promote_validates_before_writing_outputs(tmp_path):
    invalid_finding = tmp_path / "invalid_finding.csv"
    output_dir = tmp_path / "registry" / "gw36"

    pd.read_csv(FINDING_PATH).drop(columns=["signal_layer"]).to_csv(invalid_finding, index=False)

    with pytest.raises(Exception, match="missing required columns"):
        promote_registry(finding_path=invalid_finding, gw=36, output_dir=output_dir)

    assert not output_dir.exists()


def test_promote_rejects_exploratory_target(tmp_path):
    # Governance must never publish back into an exploratory research/findings/ path.
    with pytest.raises(LifecycleViolationError):
        promote_registry(
            finding_path=FINDING_PATH,
            gw=36,
            output_dir=Path("research/findings/registry_builds/gw36"),
        )


def test_promote_rejects_invalid_gameweek(tmp_path):
    with pytest.raises(ValueError, match="gw must be positive"):
        promote_registry(finding_path=FINDING_PATH, gw=0, output_dir=tmp_path / "gw0")


def test_promote_cli_publishes_registry(tmp_path, capsys):
    output_dir = tmp_path / "registry" / "gw36"

    exit_code = main(
        [
            "--gw",
            "36",
            "--finding-path",
            str(FINDING_PATH),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GW36 registry promoted" in captured.out
    assert (output_dir / "registry.csv").exists()
    assert (output_dir / "promotion_metadata.json").exists()
