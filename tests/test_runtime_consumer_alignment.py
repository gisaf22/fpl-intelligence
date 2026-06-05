"""Runtime consumer alignment tests for the intelligence layer.

Verifies that:
1. No intelligence module contains hardcoded weight values — all weights are
   loaded from intelligence/weight_registry.yaml.
2. The weight registry loader hard-fails on missing entries.
3. signals.py lifecycle enforcement raises LifecycleViolationError for excluded signals.
4. score_provenance() returns a complete audit trail for a synthetic test case.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _intelligence_module_paths() -> list[Path]:
    """Return paths to the four operational intelligence modules."""
    root = Path("intelligence")
    return [
        root / "captain.py",
        root / "value.py",
        root / "fixtures.py",
        root / "transfers.py",
    ]


def _module_source(path: Path) -> str:
    return path.read_text()


def _base_features_row(
    player_id: int = 1,
    gw: int = 5,
    position_label: str = "MID",
    team_id: int = 10,
    purchase_price: float = 7.0,
    xgi_roll3: float = 0.5,
    xgi_roll5: float = 0.4,
    xgc_roll3: float = 0.3,
    xgc_roll5: float = 0.3,
    clean_sheets_roll3: float = 0.2,
    clean_sheets_roll5: float = 0.2,
    goals_conceded_roll3: float = 1.0,
    goals_conceded_roll5: float = 1.0,
    minutes_roll3: float = 90.0,
    minutes_roll5: float = 85.0,
    minutes_roll8: float = 88.0,
    minutes_trend: str = "stable",
    goals_scored: float = 1.5,
    fdr_avg: float = 3.0,
    is_bgw: int = 0,
    fixture_context: str = "SGW",
) -> dict:
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"Player {player_id}",
        "position_label": position_label,
        "position_code": 3,
        "team_id": team_id,
        "purchase_price": purchase_price,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": xgi_roll5,
        "xgc_roll3": xgc_roll3,
        "xgc_roll5": xgc_roll5,
        "clean_sheets_roll3": clean_sheets_roll3,
        "clean_sheets_roll5": clean_sheets_roll5,
        "goals_conceded_roll3": goals_conceded_roll3,
        "goals_conceded_roll5": goals_conceded_roll5,
        "minutes_roll3": minutes_roll3,
        "minutes_roll5": minutes_roll5,
        "minutes_roll8": minutes_roll8,
        "minutes_trend": minutes_trend,
        "goals_scored": goals_scored,
        "fdr_avg": fdr_avg,
        "is_bgw": is_bgw,
        "fixture_context": fixture_context,
    }


def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# 1. No hardcoded weight dicts in intelligence modules
# ---------------------------------------------------------------------------


class TestNoHardcodedWeights:
    """Verify intelligence modules do not contain literal float weight dicts.

    A hardcoded weight dict looks like:
        _WEIGHTS = {"form_score": 0.35, "fixture_score": 0.20, ...}

    The weight registry enforces that all such dicts are replaced by get_module_weights()
    registry calls. This test parses each module's AST and asserts no
    top-level assignment to _WEIGHTS (or similar) uses a plain Dict literal
    with float values.
    """

    @pytest.mark.parametrize("path", _intelligence_module_paths(), ids=lambda p: p.name)
    def test_no_hardcoded_weight_dict(self, path: Path) -> None:
        source = _module_source(path)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Look for assignments like _WEIGHTS = {...} where values are floats
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Name) and "_WEIGHTS" in target.id):
                    continue
                # The RHS must not be a plain Dict literal with float values.
                # A registry call looks like a Call node, not a Dict.
                if isinstance(node.value, ast.Dict):
                    float_vals = [
                        v for v in node.value.values if isinstance(v, ast.Constant) and isinstance(v.value, float)
                    ]
                    assert float_vals == [], (
                        f"{path}: _WEIGHTS is assigned a literal dict with float values "
                        f"({len(float_vals)} entries). Replace with get_module_weights() "
                        "from intelligence.weight_registry."
                    )

    @pytest.mark.parametrize("path", _intelligence_module_paths(), ids=lambda p: p.name)
    def test_uses_get_module_weights(self, path: Path) -> None:
        """Each module must call get_module_weights() to load its weights."""
        source = _module_source(path)
        assert "get_module_weights" in source, (
            f"{path}: does not import or call get_module_weights(). "
            "All module weights must be loaded from the governance registry."
        )


# ---------------------------------------------------------------------------
# 2. Weight registry loader contracts
# ---------------------------------------------------------------------------


class TestWeightRegistryLoader:
    """Verify weight_registry.py loads correctly and hard-fails on bad input."""

    def test_known_modules_load(self) -> None:
        from intelligence.weight_registry import get_module_weights

        for module in ("captain", "value", "fixtures", "transfers"):
            weights = get_module_weights(module)
            assert isinstance(weights, dict), f"{module}: expected dict"
            assert len(weights) > 0, f"{module}: empty weights dict"
            for k, v in weights.items():
                assert isinstance(v, float), f"{module}.{k}: weight must be float, got {type(v)}"

    def test_all_weights_positive(self) -> None:
        from intelligence.weight_registry import get_module_weights

        for module in ("captain", "value", "fixtures", "transfers"):
            weights = get_module_weights(module)
            for k, v in weights.items():
                assert v > 0, f"{module}.{k}: weight must be positive, got {v}"

    def test_missing_module_raises(self) -> None:
        from intelligence.weight_registry import WeightRegistryError, get_module_weights

        with pytest.raises(WeightRegistryError):
            get_module_weights("nonexistent_module_xyz")

    def test_get_weight_metadata_returns_dict(self) -> None:
        from intelligence.weight_registry import get_weight_metadata

        meta = get_weight_metadata("captain", "form_score")
        assert isinstance(meta, dict)
        assert "value" in meta

    def test_get_weight_metadata_missing_raises(self) -> None:
        from intelligence.weight_registry import WeightRegistryError, get_weight_metadata

        with pytest.raises(WeightRegistryError):
            get_weight_metadata("captain", "nonexistent_key_xyz")

    def test_fdr_opportunity_score_not_in_fixtures(self) -> None:
        """fdr_opportunity_score must not appear in fixtures registry."""
        from intelligence.weight_registry import get_module_weights

        weights = get_module_weights("fixtures")
        assert "fdr_opportunity_score" not in weights, (
            "fixtures registry must not contain fdr_opportunity_score — "
            "fdr_avg excluded at all positions (FIXTURE-001 G2-FAIL: non-monotonic quintile ordering)."
        )

    def test_fixtures_has_two_components(self) -> None:
        """fixtures module scoring uses exactly team_attack_score and dgw_bonus_score."""
        from intelligence.weight_registry import get_module_weights

        weights = get_module_weights("fixtures")
        assert set(weights.keys()) == {"team_attack_score", "dgw_bonus_score"}, (
            f"fixtures weights: expected {{team_attack_score, dgw_bonus_score}}, got {set(weights.keys())}"
        )


# ---------------------------------------------------------------------------
# 3. Lifecycle enforcement: excluded signals raise LifecycleViolationError
# ---------------------------------------------------------------------------


class TestLifecycleEnforcement:
    """Verify _assert_governance_compliance rejects excluded lifecycle signals."""

    def _make_manifest_with_signal(self, signal: str, position: str, rho: float = 0.30):
        """Build a synthetic SignalManifest containing a single confirmed signal."""
        from intelligence.scoring.contracts import ConfirmedSignal, SignalManifest

        confirmed = [
            ConfirmedSignal(
                signal=signal,
                position=position,
                rho_pooled=rho,
                direction=1,
                promotion_class="core_signal",
            )
        ]
        return SignalManifest(
            confirmed=confirmed,
            caveated=[],
            positions_covered={position: [signal]},
        )

    def test_excluded_signal_raises_lifecycle_violation(self) -> None:
        """A signal with lifecycle_state=excluded must not pass governance compliance."""
        from domain.registry.schema import GovernanceMetadataError
        from signals.governance.governance import get_signal_governance

        # Find an excluded signal from the evaluation metadata to use as the test case.
        # xgi_roll3 excluded at FWD (FORM-001 G2-FAIL: non-monotonic quintile ordering).
        try:
            gov = get_signal_governance("xgi_roll3", "FWD")
        except GovernanceMetadataError:
            pytest.skip("xgi_roll3@FWD not in evaluation_metadata — skipping")

        if gov.lifecycle_state != "excluded":
            pytest.skip(
                f"xgi_roll3@FWD has lifecycle_state={gov.lifecycle_state!r}, "
                "not excluded — test requires an excluded signal"
            )

        from domain.registry.lifecycle import LifecycleViolationError
        from intelligence.scoring.signal_selector import _assert_governance_compliance

        manifest = self._make_manifest_with_signal("xgi_roll3", "FWD")
        with pytest.raises(LifecycleViolationError):
            _assert_governance_compliance(manifest)

    def test_exploratory_path_raises_lifecycle_violation(self) -> None:
        from domain.registry.lifecycle import LifecycleViolationError, assert_operational_safe

        with pytest.raises(LifecycleViolationError):
            assert_operational_safe("research/findings/some_registry.csv")

    def test_operational_path_passes(self) -> None:
        from domain.registry.lifecycle import assert_operational_safe

        # Should not raise for a non-exploratory path
        assert_operational_safe("outputs/registry/joint_registry.csv")


# ---------------------------------------------------------------------------
# 4. score_provenance() completeness
# ---------------------------------------------------------------------------


class TestScoreProvenance:
    """Verify score_provenance() returns a complete, well-structured audit trail."""

    @pytest.fixture
    def synthetic_features(self) -> pd.DataFrame:
        return _make_features(
            _base_features_row(player_id=1, gw=5, position_label="MID"),
            _base_features_row(player_id=2, gw=5, position_label="FWD"),
            _base_features_row(player_id=3, gw=5, position_label="DEF"),
        )

    @pytest.mark.parametrize("module", ["captain", "value", "fixtures", "transfers"])
    def test_provenance_top_level_keys(self, module: str, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance

        result = score_provenance(synthetic_features, player_id=1, gw=5, module=module)

        assert result["player_id"] == 1
        assert result["gw"] == 5
        assert result["module"] == module
        assert "position" in result
        assert "registry_source" in result
        assert "signals" in result
        assert isinstance(result["signals"], dict)

    @pytest.mark.parametrize("module", ["captain", "value", "fixtures", "transfers"])
    def test_provenance_signal_structure(self, module: str, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance
        from intelligence.weight_registry import get_module_weights

        result = score_provenance(synthetic_features, player_id=1, gw=5, module=module)
        weights = get_module_weights(module)

        # Every weight component must appear in the provenance signals dict.
        for component in weights:
            assert component in result["signals"], (
                f"module={module}: component {component!r} missing from provenance signals"
            )
            entry = result["signals"][component]
            assert "weight" in entry, f"{module}.{component}: missing 'weight'"
            assert "signals" in entry, f"{module}.{component}: missing 'signals'"
            assert "state_values" in entry, f"{module}.{component}: missing 'state_values'"
            assert "registry_source" in entry, f"{module}.{component}: missing 'registry_source'"
            assert "signal_id" in entry, f"{module}.{component}: missing 'signal_id'"
            assert "provenance" in entry, f"{module}.{component}: missing 'provenance'"
            assert "caveats" in entry, f"{module}.{component}: missing 'caveats'"
            assert isinstance(entry["caveats"], list), f"{module}.{component}: 'caveats' must be a list"

    @pytest.mark.parametrize("module", ["captain", "value", "fixtures", "transfers"])
    def test_provenance_weights_match_registry(self, module: str, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance
        from intelligence.weight_registry import get_module_weights

        result = score_provenance(synthetic_features, player_id=1, gw=5, module=module)
        registry_weights = get_module_weights(module)

        for component, expected_weight in registry_weights.items():
            actual_weight = result["signals"][component]["weight"]
            assert actual_weight == pytest.approx(expected_weight), (
                f"{module}.{component}: provenance weight {actual_weight} != registry weight {expected_weight}"
            )

    def test_provenance_unknown_module_raises(self, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance

        with pytest.raises(ValueError, match="not in provenance map"):
            score_provenance(synthetic_features, player_id=1, gw=5, module="unknown_xyz")

    def test_provenance_missing_player_raises(self, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance

        with pytest.raises(ValueError, match="no data for player_id=999"):
            score_provenance(synthetic_features, player_id=999, gw=5, module="captain")

    def test_provenance_registry_source_references_yaml(self, synthetic_features: pd.DataFrame) -> None:
        from intelligence.provenance import score_provenance

        result = score_provenance(synthetic_features, player_id=1, gw=5, module="captain")
        assert "weight_registry.yaml" in result["registry_source"]
        for component, entry in result["signals"].items():
            assert "weight_registry.yaml" in entry["registry_source"], (
                f"captain.{component}: registry_source should reference weight_registry.yaml"
            )

    def test_provenance_fwd_position_present(self, synthetic_features: pd.DataFrame) -> None:
        """FWD players must return valid provenance — FWD guard affects scores, not lookup."""
        from intelligence.provenance import score_provenance

        result = score_provenance(synthetic_features, player_id=2, gw=5, module="transfers")
        assert result["position"] == "FWD"
        assert "signals" in result
        assert len(result["signals"]) > 0


# ---------------------------------------------------------------------------
# 5. fdr_avg excluded from scoring (informational output only)
# ---------------------------------------------------------------------------


class TestFdrRemovedFromScoring:
    """fdr_avg must not contribute to any scored output.

    LENS-FIXTURE-GW found non-monotonic quintile ordering at all positions;
    fdr_avg is retained as an informational output column only.
    """

    def _features_with_varying_fdr(self) -> pd.DataFrame:
        """Two players: identical except one has a much better (lower) FDR."""
        rows = [
            _base_features_row(
                player_id=1,
                gw=5,
                team_id=1,
                fdr_avg=1.0,  # very easy fixture
                fixture_context="SGW",
                minutes_roll5=85.0,
            ),
            _base_features_row(
                player_id=2,
                gw=5,
                team_id=2,
                fdr_avg=5.0,  # very hard fixture
                fixture_context="SGW",
                minutes_roll5=85.0,
            ),
        ]
        # Add prior-gw rows for team attack strength computation
        prior = [
            _base_features_row(player_id=1, gw=4, team_id=1, goals_scored=2.0),
            _base_features_row(player_id=2, gw=4, team_id=2, goals_scored=2.0),
        ]
        return _make_features(*rows, *prior)

    def test_fixtures_score_unaffected_by_fdr_alone(self) -> None:
        """Players with identical fixture_context but different fdr_avg get equal scores."""
        from intelligence.fixtures import rank_fixture_opportunities

        features = self._features_with_varying_fdr()
        result = rank_fixture_opportunities(features, target_gw=5)

        assert len(result) == 2
        scores = result.set_index("player_id")["fixture_opportunity_score"]
        # Both players have SGW context and same team attack data — scores should be equal.
        assert scores[1] == pytest.approx(scores[2]), (
            "fixture_opportunity_score must not differ by fdr_avg alone. "
            f"Player 1 (fdr=1.0): {scores[1]:.4f}, Player 2 (fdr=5.0): {scores[2]:.4f}"
        )

    def test_captain_score_unaffected_by_fdr_alone(self) -> None:
        """Captain scores must not vary when only fdr_avg differs."""
        from intelligence.captain import rank_captain_candidates as rank_captains

        rows = [
            _base_features_row(
                player_id=1,
                gw=5,
                position_label="MID",
                fdr_avg=1.0,
                fixture_context="SGW",
                xgi_roll5=0.5,
                xgi_roll3=0.5,
                minutes_roll3=90.0,
            ),
            _base_features_row(
                player_id=2,
                gw=5,
                position_label="MID",
                fdr_avg=5.0,
                fixture_context="SGW",
                xgi_roll5=0.5,
                xgi_roll3=0.5,
                minutes_roll3=90.0,
            ),
        ]
        features = _make_features(*rows)
        result = rank_captains(features, target_gw=5)

        scores = result.set_index("player_id")["captain_score"]
        assert scores[1] == pytest.approx(scores[2]), (
            "captain_score must not differ by fdr_avg alone. "
            f"Player 1 (fdr=1.0): {scores[1]:.4f}, Player 2 (fdr=5.0): {scores[2]:.4f}"
        )


# ---------------------------------------------------------------------------
# 6. FWD scope guard: xgi_roll3/xgi_roll5 excluded at FWD
# ---------------------------------------------------------------------------


class TestFwdScopeGuard:
    """xgi_roll3/xgi_roll5 excluded at FWD (FORM-001/002 G2-FAIL); scores neutralised to 0.5."""

    def _fwd_features_varying_xgi(self) -> pd.DataFrame:
        """Two FWD players with very different xgi — scores should be equal (0.5)."""
        return _make_features(
            _base_features_row(
                player_id=10,
                gw=5,
                position_label="FWD",
                xgi_roll3=2.0,
                xgi_roll5=2.0,
            ),
            _base_features_row(
                player_id=11,
                gw=5,
                position_label="FWD",
                xgi_roll3=0.01,
                xgi_roll5=0.01,
            ),
        )

    def test_transfers_fwd_xgi_neutralised(self) -> None:
        from intelligence.transfers import rank_transfer_targets

        features = self._fwd_features_varying_xgi()
        result = rank_transfer_targets(features, target_gw=5)
        fwd = result[result["position_label"] == "FWD"]

        if len(fwd) < 2:
            pytest.skip("Not enough FWD players in result to compare")

        scores = fwd.set_index("player_id")["recent_form_score"]
        assert scores[10] == pytest.approx(scores[11], abs=1e-6), (
            "FWD recent_form_score must be neutralised (0.5) regardless of xgi_roll3. "
            f"Player 10 (xgi=2.0): {scores[10]:.4f}, Player 11 (xgi=0.01): {scores[11]:.4f}"
        )

    def test_captain_fwd_xgi_neutralised(self) -> None:
        from intelligence.captain import rank_captain_candidates

        features = self._fwd_features_varying_xgi()
        result = rank_captain_candidates(features, target_gw=5)
        fwd = result[result["position_label"] == "FWD"]

        if len(fwd) < 2:
            pytest.skip("Not enough FWD players in result to compare")

        scores = fwd.set_index("player_id")["captain_score"]
        assert scores[10] == pytest.approx(scores[11], abs=1e-6), (
            "FWD captain_score must be neutralised when xgi differs. "
            f"Player 10 (xgi=2.0): {scores[10]:.4f}, Player 11 (xgi=0.01): {scores[11]:.4f}"
        )


# ---------------------------------------------------------------------------
# 7. minutes_roll8 wired for DEF/MID long-horizon availability flag
# ---------------------------------------------------------------------------


class TestMinutesRoll8Wired:
    """availability.py must use minutes_roll8 for DEF/MID long_horizon_flag (AVAIL-003)."""

    def test_long_horizon_flag_in_output(self) -> None:
        from intelligence.availability import flag_availability_risk

        features = _make_features(
            _base_features_row(
                player_id=1, gw=5, position_label="DEF", minutes_roll3=90.0, minutes_roll5=85.0, minutes_roll8=88.0
            ),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert "long_horizon_flag" in result.columns
        assert "minutes_roll8" in result.columns

    def test_def_low_roll8_gets_long_horizon_flag(self) -> None:
        from intelligence.availability import flag_availability_risk

        features = _make_features(
            _base_features_row(
                player_id=1,
                gw=5,
                position_label="DEF",
                minutes_roll3=90.0,
                minutes_roll5=85.0,
                minutes_roll8=30.0,  # low 8-GW average
            ),
        )
        result = flag_availability_risk(features, target_gw=5)
        row = result.iloc[0]
        assert row["long_horizon_flag"] == 1, (
            "DEF player with minutes_roll8=30.0 (< 60 threshold) should have long_horizon_flag=1"
        )

    def test_gk_not_flagged_by_roll8(self) -> None:
        """GK players are excluded from minutes_roll8 governance (AVAIL-003 non-monotonic at GK)."""
        from intelligence.availability import flag_availability_risk

        features = _make_features(
            _base_features_row(
                player_id=2,
                gw=5,
                position_label="GK",
                minutes_roll3=90.0,
                minutes_roll5=85.0,
                minutes_roll8=30.0,  # would trigger if GK was governed
            ),
        )
        result = flag_availability_risk(features, target_gw=5)
        row = result.iloc[0]
        assert row["long_horizon_flag"] == 0, (
            "GK players must not receive long_horizon_flag — "
            "AVAIL-003 non-monotonic at GK, excluded from roll8 governance."
        )

    def test_fwd_not_flagged_by_roll8(self) -> None:
        """FWD players are excluded from minutes_roll8 governance (AVAIL-003 G2-FAIL at FWD)."""
        from intelligence.availability import flag_availability_risk

        features = _make_features(
            _base_features_row(
                player_id=3,
                gw=5,
                position_label="FWD",
                minutes_roll3=90.0,
                minutes_roll5=85.0,
                minutes_roll8=30.0,
            ),
        )
        result = flag_availability_risk(features, target_gw=5)
        row = result.iloc[0]
        assert row["long_horizon_flag"] == 0, (
            "FWD players must not receive long_horizon_flag — AVAIL-003 G2-FAIL at FWD, excluded from roll8 governance."
        )
