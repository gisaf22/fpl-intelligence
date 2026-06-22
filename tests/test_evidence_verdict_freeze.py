"""Verdict-freeze tests for all committed lens evidence.yaml artifacts.

These tests freeze the (signal, position) → decision_class mapping for each
lens. If a study is re-run and evidence.yaml changes, these tests will fail,
alerting developers that the governance generator must be re-run before commit
(GPG-02 from Architecture Decision Log).

These are semantic snapshot tests — they verify decision_class verdicts, not
YAML formatting. A formatting change that preserves all verdicts will not fail.

Design: tests read the committed evidence.yaml from the repository and assert
that all required signals, positions, and decision_class values are present.
If evidence.yaml is regenerated with different verdicts, the test catches it.

No database or study execution is required.
"""

from pathlib import Path

import pytest
import yaml

FAMILIES_DIR = Path(__file__).resolve().parents[1] / "research" / "families"
VALID_DECISION_CLASSES = {"informative", "uninformative"}
VALID_TOP_LEVEL_KEYS = {"lens", "target", "evidence_run", "signals"}
REQUIRED_ENTRY_FIELDS = {
    "rho_pooled",
    "rho_ci_lower",
    "rho_ci_upper",
    "block_stability_count",
    "decision_class",
}


def _load_evidence(lens_dir: str) -> dict:
    path = FAMILIES_DIR / lens_dir / "validate" / "evidence.yaml"
    assert path.exists(), f"evidence.yaml missing: {path}"
    return yaml.safe_load(path.read_text())


def _assert_schema(payload: dict, expected_lens: str, expected_target: str) -> None:
    assert payload.get("lens") == expected_lens
    assert payload.get("target") == expected_target
    assert set(payload.keys()) >= VALID_TOP_LEVEL_KEYS
    assert isinstance(payload["evidence_run"], dict)
    assert "source" in payload["evidence_run"]
    assert "produced" in payload["evidence_run"]
    assert "db_path" in payload["evidence_run"]
    assert isinstance(payload["signals"], dict)
    assert len(payload["signals"]) > 0


def _assert_all_entries_have_required_fields(payload: dict) -> None:
    for signal, positions in payload["signals"].items():
        for pos, entry in positions.items():
            missing = REQUIRED_ENTRY_FIELDS - set(entry.keys())
            assert not missing, f"{signal}/{pos} missing fields: {missing}"


def _assert_decision_class_vocab(payload: dict) -> None:
    for signal, positions in payload["signals"].items():
        for pos, entry in positions.items():
            dc = entry["decision_class"]
            assert dc in VALID_DECISION_CLASSES, f"{signal}/{pos}: unexpected decision_class '{dc}'"


# ---------------------------------------------------------------------------
# FORM lens
# ---------------------------------------------------------------------------

FORM_EXPECTED_VERDICTS: dict[tuple[str, str], str] = {
    # Study-emitted decision_class (machine half). Note: annotations.yaml may override
    # some uninformative entries to informative in evaluation_metadata.yaml.
    ("xgi_roll3", "DEF"): "informative",
    ("xgi_roll3", "MID"): "informative",
    ("xgi_roll3", "FWD"): "uninformative",
    ("xgi_roll5", "DEF"): "uninformative",
    ("xgi_roll5", "MID"): "informative",
    ("xgi_roll5", "FWD"): "uninformative",
    ("goals_scored_roll3", "DEF"): "uninformative",
    ("goals_scored_roll3", "MID"): "uninformative",
    ("goals_scored_roll3", "FWD"): "uninformative",
    ("points_roll3", "GK"): "uninformative",
    ("points_roll3", "DEF"): "uninformative",
    ("points_roll3", "MID"): "uninformative",
    ("points_roll3", "FWD"): "uninformative",
    ("points_roll5", "GK"): "uninformative",
    ("points_roll5", "DEF"): "uninformative",
    ("points_roll5", "MID"): "uninformative",
    ("points_roll5", "FWD"): "uninformative",
    ("minutes_roll3", "DEF"): "uninformative",
    ("minutes_roll3", "MID"): "uninformative",
    ("minutes_roll3", "FWD"): "uninformative",
}


class TestFormEvidenceFreeze:
    def setup_method(self):
        self.payload = _load_evidence("form")

    def test_schema_valid(self):
        _assert_schema(self.payload, "form", "total_points")

    def test_all_entries_have_required_fields(self):
        _assert_all_entries_have_required_fields(self.payload)

    def test_decision_class_vocab(self):
        _assert_decision_class_vocab(self.payload)

    def test_expected_signals_present(self):
        signals = set(self.payload["signals"].keys())
        expected_signals = {s for s, _ in FORM_EXPECTED_VERDICTS}
        assert expected_signals <= signals

    @pytest.mark.parametrize(
        "signal,position,expected_class", [(s, p, dc) for (s, p), dc in FORM_EXPECTED_VERDICTS.items()]
    )
    def test_verdict_frozen(self, signal, position, expected_class):
        actual = self.payload["signals"][signal][position]["decision_class"]
        assert actual == expected_class, (
            f"VERDICT CHANGED: {signal}/{position} was '{expected_class}', "
            f"now '{actual}'. Re-run study and governance generator before committing."
        )


# ---------------------------------------------------------------------------
# AVAIL lens
# ---------------------------------------------------------------------------

AVAIL_EXPECTED_VERDICTS: dict[tuple[str, str], str] = {
    ("minutes_roll3", "GK"): "uninformative",
    ("minutes_roll3", "DEF"): "uninformative",
    ("minutes_roll3", "MID"): "informative",
    ("minutes_roll3", "FWD"): "uninformative",
    ("minutes_roll5", "GK"): "uninformative",
    ("minutes_roll5", "DEF"): "uninformative",
    ("minutes_roll5", "MID"): "informative",
    ("minutes_roll5", "FWD"): "informative",
    ("minutes_roll8", "GK"): "uninformative",
    ("minutes_roll8", "DEF"): "uninformative",
    ("minutes_roll8", "MID"): "informative",
    ("minutes_roll8", "FWD"): "uninformative",
}


class TestAvailEvidenceFreeze:
    def setup_method(self):
        self.payload = _load_evidence("availability")

    def test_schema_valid(self):
        _assert_schema(self.payload, "avail", "played_next_gw")

    def test_all_entries_have_required_fields(self):
        _assert_all_entries_have_required_fields(self.payload)

    def test_decision_class_vocab(self):
        _assert_decision_class_vocab(self.payload)

    @pytest.mark.parametrize(
        "signal,position,expected_class", [(s, p, dc) for (s, p), dc in AVAIL_EXPECTED_VERDICTS.items()]
    )
    def test_verdict_frozen(self, signal, position, expected_class):
        actual = self.payload["signals"][signal][position]["decision_class"]
        assert actual == expected_class, (
            f"VERDICT CHANGED: {signal}/{position} was '{expected_class}', "
            f"now '{actual}'. Re-run study and governance generator before committing."
        )


# ---------------------------------------------------------------------------
# MARKET lens
# ---------------------------------------------------------------------------

MARKET_EXPECTED_VERDICTS: dict[tuple[str, str], str] = {
    ("transfers_in", "GK"): "uninformative",
    ("transfers_in", "DEF"): "informative",
    ("transfers_in", "MID"): "informative",
    ("transfers_in", "FWD"): "uninformative",
    ("ownership_count", "GK"): "uninformative",
    ("ownership_count", "DEF"): "informative",
    ("ownership_count", "MID"): "informative",
    ("ownership_count", "FWD"): "uninformative",
    ("purchase_price", "GK"): "uninformative",
    ("purchase_price", "DEF"): "informative",
    ("purchase_price", "MID"): "uninformative",
    ("purchase_price", "FWD"): "uninformative",
}


class TestMarketEvidenceFreeze:
    def setup_method(self):
        self.payload = _load_evidence("market")

    def test_schema_valid(self):
        _assert_schema(self.payload, "market", "total_points")

    def test_all_entries_have_required_fields(self):
        _assert_all_entries_have_required_fields(self.payload)

    def test_decision_class_vocab(self):
        _assert_decision_class_vocab(self.payload)

    @pytest.mark.parametrize(
        "signal,position,expected_class", [(s, p, dc) for (s, p), dc in MARKET_EXPECTED_VERDICTS.items()]
    )
    def test_verdict_frozen(self, signal, position, expected_class):
        actual = self.payload["signals"][signal][position]["decision_class"]
        assert actual == expected_class, (
            f"VERDICT CHANGED: {signal}/{position} was '{expected_class}', "
            f"now '{actual}'. Re-run study and governance generator before committing."
        )


# ---------------------------------------------------------------------------
# FIXTURE lens
# ---------------------------------------------------------------------------

FIXTURE_EXPECTED_VERDICTS: dict[tuple[str, str], str] = {
    ("fdr_avg", "GK"): "uninformative",
    ("fdr_avg", "DEF"): "uninformative",
    ("fdr_avg", "MID"): "uninformative",
    ("fdr_avg", "FWD"): "uninformative",
    ("was_home", "GK"): "uninformative",
    ("was_home", "DEF"): "uninformative",
    ("was_home", "MID"): "uninformative",
    ("was_home", "FWD"): "uninformative",
    ("fixture_count", "DEF"): "uninformative",
    ("fixture_count", "MID"): "uninformative",
}


class TestFixtureEvidenceFreeze:
    def setup_method(self):
        self.payload = _load_evidence("fixture")

    def test_schema_valid(self):
        _assert_schema(self.payload, "fixture_gw", "total_points")

    def test_all_entries_have_required_fields(self):
        _assert_all_entries_have_required_fields(self.payload)

    def test_decision_class_vocab(self):
        _assert_decision_class_vocab(self.payload)

    @pytest.mark.parametrize(
        "signal,position,expected_class", [(s, p, dc) for (s, p), dc in FIXTURE_EXPECTED_VERDICTS.items()]
    )
    def test_verdict_frozen(self, signal, position, expected_class):
        actual = self.payload["signals"][signal][position]["decision_class"]
        assert actual == expected_class, (
            f"VERDICT CHANGED: {signal}/{position} was '{expected_class}', "
            f"now '{actual}'. Re-run study and governance generator before committing."
        )
