"""Unit tests for research/families/evidence_record.py.

write_evidence() is the function that produces the committed governance input.
These tests verify: position label mapping, YAML structure, evidence_run metadata,
decision_class_for mapping, and multi-signal / multi-position output.
"""

import yaml

from research.families.evidence_record import build_evidence_row, decision_class_for, write_evidence

# ---------------------------------------------------------------------------
# decision_class_for
# ---------------------------------------------------------------------------

class TestDecisionClassFor:

    def test_informative_maps_to_informative(self):
        assert decision_class_for("informative") == "informative"

    def test_uninformative_maps_to_uninformative(self):
        assert decision_class_for("uninformative") == "uninformative"

    def test_unstable_maps_to_uninformative(self):
        # "unstable" study verdict -> "uninformative" governance decision class
        assert decision_class_for("unstable") == "uninformative"

    def test_unknown_status_returns_uninformative(self):
        assert decision_class_for("conditional") == "uninformative"
        assert decision_class_for("") == "uninformative"


# ---------------------------------------------------------------------------
# write_evidence — helpers
# ---------------------------------------------------------------------------

def _row(signal: str, position: str, decision_class: str = "informative") -> dict:
    return {
        "signal": signal,
        "position": position,
        "rho_pooled": 0.15,
        "rho_ci_lower": 0.05,
        "rho_ci_upper": 0.25,
        "block_stability_count": 2,
        "decision_class": decision_class,
    }


def _run_meta(ts: str = "20260607_120000") -> dict:
    return {"source": f"LENS-FORM-{ts}", "produced": ts, "db_path": "/tmp/test.db"}


# ---------------------------------------------------------------------------
# write_evidence tests
# ---------------------------------------------------------------------------

class TestWriteEvidence:

    def test_output_path_is_evidence_yaml(self, tmp_path):
        rows = [_row("xgi_roll3", "DEF")]
        result = write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        assert result == tmp_path / "evidence.yaml"
        assert result.exists()

    def test_top_level_structure(self, tmp_path):
        rows = [_row("xgi_roll3", "DEF")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert payload["lens"] == "form"
        assert payload["target"] == "total_points"
        assert "evidence_run" in payload
        assert "signals" in payload

    def test_evidence_run_metadata_present(self, tmp_path):
        meta = _run_meta("20260607_150000")
        rows = [_row("xgi_roll3", "DEF")]
        write_evidence(tmp_path, "form", "total_points", rows, meta)
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert payload["evidence_run"]["source"] == "LENS-FORM-20260607_150000"
        assert payload["evidence_run"]["db_path"] == "/tmp/test.db"

    def test_gkp_position_mapped_to_gk(self, tmp_path):
        rows = [_row("points_roll3", "GKP")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        # GKP -> GK mapping applied
        assert "GK" in payload["signals"]["points_roll3"]
        assert "GKP" not in payload["signals"]["points_roll3"]

    def test_gk_position_passthrough(self, tmp_path):
        rows = [_row("points_roll3", "GK")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert "GK" in payload["signals"]["points_roll3"]

    def test_unknown_position_passes_through_unchanged(self, tmp_path):
        rows = [_row("xgi_roll3", "CUSTOM")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert "CUSTOM" in payload["signals"]["xgi_roll3"]

    def test_signal_entry_has_required_fields(self, tmp_path):
        rows = [_row("xgi_roll3", "DEF")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        entry = payload["signals"]["xgi_roll3"]["DEF"]
        assert "rho_pooled" in entry
        assert "rho_ci_lower" in entry
        assert "rho_ci_upper" in entry
        assert "block_stability_count" in entry
        assert "decision_class" in entry

    def test_decision_class_written_correctly(self, tmp_path):
        rows = [_row("xgi_roll3", "DEF", "informative"),
                _row("xgi_roll3", "MID", "uninformative")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert payload["signals"]["xgi_roll3"]["DEF"]["decision_class"] == "informative"
        assert payload["signals"]["xgi_roll3"]["MID"]["decision_class"] == "uninformative"

    def test_multi_signal_multi_position(self, tmp_path):
        rows = [
            _row("xgi_roll3", "DEF", "informative"),
            _row("xgi_roll3", "MID", "informative"),
            _row("xgi_roll5", "DEF", "uninformative"),
            _row("points_roll3", "GKP", "uninformative"),
        ]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        signals = payload["signals"]
        assert "xgi_roll3" in signals
        assert "xgi_roll5" in signals
        assert "points_roll3" in signals
        assert "DEF" in signals["xgi_roll3"]
        assert "MID" in signals["xgi_roll3"]
        assert "GK" in signals["points_roll3"]  # GKP -> GK

    def test_rho_values_preserved(self, tmp_path):
        row = {
            "signal": "xgi_roll3", "position": "DEF",
            "rho_pooled": 0.1234, "rho_ci_lower": 0.0859, "rho_ci_upper": 0.1598,
            "block_stability_count": 3, "decision_class": "informative",
        }
        write_evidence(tmp_path, "form", "total_points", [row], _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        entry = payload["signals"]["xgi_roll3"]["DEF"]
        assert abs(entry["rho_pooled"] - 0.1234) < 1e-6
        assert abs(entry["rho_ci_lower"] - 0.0859) < 1e-6
        assert entry["block_stability_count"] == 3

    def test_none_rho_preserved(self, tmp_path):
        row = {
            "signal": "xgi_roll3", "position": "FWD",
            "rho_pooled": None, "rho_ci_lower": None, "rho_ci_upper": None,
            "block_stability_count": None, "decision_class": "uninformative",
        }
        write_evidence(tmp_path, "form", "total_points", [row], _run_meta())
        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        entry = payload["signals"]["xgi_roll3"]["FWD"]
        assert entry["rho_pooled"] is None
        assert entry["block_stability_count"] is None

    def test_file_is_valid_yaml(self, tmp_path):
        rows = [_row("xgi_roll3", "DEF")]
        write_evidence(tmp_path, "form", "total_points", rows, _run_meta())
        content = (tmp_path / "evidence.yaml").read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)

    def test_overwrites_existing_file(self, tmp_path):
        rows1 = [_row("xgi_roll3", "DEF", "informative")]
        write_evidence(tmp_path, "form", "total_points", rows1, _run_meta("20260607_100000"))

        rows2 = [_row("xgi_roll3", "DEF", "uninformative")]
        write_evidence(tmp_path, "form", "total_points", rows2, _run_meta("20260607_110000"))

        payload = yaml.safe_load((tmp_path / "evidence.yaml").read_text())
        assert payload["signals"]["xgi_roll3"]["DEF"]["decision_class"] == "uninformative"


# ---------------------------------------------------------------------------
# build_evidence_row
# ---------------------------------------------------------------------------

def _cls(lens_status: str, signal: str = "xgi_roll3", position: str = "DEF") -> dict:
    return {"signal_id": "FORM-001", "signal": signal, "position": position,
            "lens_status": lens_status, "rationale": "test"}


def _block(excludes_zero: bool) -> dict:
    return {"rho": 0.12, "ci_lower": 0.03, "ci_upper": 0.21, "n": 100,
            "ci_excludes_zero": excludes_zero}


class TestBuildEvidenceRow:

    def test_full_corr_fields_projected(self):
        full_corr = {"rho": 0.15, "ci_lower": 0.05, "ci_upper": 0.25, "n": 200,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, [], _cls("informative"))
        assert row["signal"] == "xgi_roll3"
        assert row["position"] == "DEF"
        assert row["rho_pooled"] == 0.15
        assert row["rho_ci_lower"] == 0.05
        assert row["rho_ci_upper"] == 0.25

    def test_block_stability_count_aggregated(self):
        blocks = [_block(True), _block(True), _block(False)]
        full_corr = {"rho": 0.15, "ci_lower": 0.05, "ci_upper": 0.25, "n": 200,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, blocks, _cls("informative"))
        assert row["block_stability_count"] == 2

    def test_block_stability_count_none_blocks_ignored(self):
        blocks = [_block(True), None, _block(False)]
        full_corr = {"rho": 0.15, "ci_lower": 0.05, "ci_upper": 0.25, "n": 200,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, blocks, _cls("informative"))
        assert row["block_stability_count"] == 1

    def test_no_full_corr_fields_are_none(self):
        row = build_evidence_row("xgi_roll3", "FWD", None, [], _cls("uninformative"))
        assert row["rho_pooled"] is None
        assert row["rho_ci_lower"] is None
        assert row["rho_ci_upper"] is None
        assert row["block_stability_count"] is None

    def test_informative_status_maps_to_informative_class(self):
        full_corr = {"rho": 0.15, "ci_lower": 0.05, "ci_upper": 0.25, "n": 200,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, [], _cls("informative"))
        assert row["decision_class"] == "informative"

    def test_uninformative_status_maps_to_uninformative_class(self):
        row = build_evidence_row("xgi_roll3", "DEF", None, [], _cls("uninformative"))
        assert row["decision_class"] == "uninformative"

    def test_unstable_status_maps_to_uninformative_class(self):
        full_corr = {"rho": 0.15, "ci_lower": 0.05, "ci_upper": 0.25, "n": 200,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, [_block(True)],
                                 _cls("unstable"))
        assert row["decision_class"] == "uninformative"

    def test_output_has_all_required_fields(self):
        row = build_evidence_row("xgi_roll3", "DEF", None, [], _cls("uninformative"))
        required = {"signal", "position", "rho_pooled", "rho_ci_lower", "rho_ci_upper",
                    "block_stability_count", "decision_class"}
        assert required == set(row.keys())

    def test_empty_block_list_gives_zero_stability_count(self):
        full_corr = {"rho": 0.10, "ci_lower": 0.01, "ci_upper": 0.19, "n": 150,
                     "ci_excludes_zero": True}
        row = build_evidence_row("xgi_roll3", "DEF", full_corr, [], _cls("unstable"))
        assert row["block_stability_count"] == 0
