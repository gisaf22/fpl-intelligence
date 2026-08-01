"""Runtime consumer alignment tests for the intelligence layer.

Verifies that:
1. Lifecycle enforcement raises LifecycleViolationError for excluded signals / exploratory paths.
2. availability.py wires minutes_roll8 for DEF/MID long-horizon flags (AVAIL-003).

The weight-registry / hardcoded-weight / score_provenance consumer contracts that used to live here were
removed with the serve signal composites: captain, value, transfers, and fixtures now all rank by the
model forecast (assemble_forecast columns), not a weight composite, so there is no weight_registry or
provenance surface left to align against. See docs/serve-model-integration.md.
"""

from __future__ import annotations

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    is_warmup_gw: bool = False,
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
        "is_warmup_gw": is_warmup_gw,
        "fixture_context": fixture_context,
    }


def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# 1. Lifecycle enforcement: excluded signals raise LifecycleViolationError
# ---------------------------------------------------------------------------


class TestLifecycleEnforcement:
    """Verify _assert_governance_compliance rejects excluded lifecycle signals."""

    def _make_manifest_with_signal(self, signal: str, position: str, rho: float = 0.30):
        """Build a synthetic SignalManifest containing a single confirmed signal."""
        from serve.scoring.contracts import ConfirmedSignal, SignalManifest

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
        from domain.registry.governance_lookup import get_signal_governance
        from domain.registry.governance_types import GovernanceMetadataError

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
        from serve.scoring.signal_selector import _assert_governance_compliance

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
# 2. minutes_roll8 wired for DEF/MID long-horizon availability flag
# ---------------------------------------------------------------------------


class TestMinutesRoll8Wired:
    """availability.py must use minutes_roll8 for DEF/MID long_horizon_flag (AVAIL-003)."""

    def test_long_horizon_flag_in_output(self) -> None:
        from serve.availability import flag_availability_risk

        features = _make_features(
            _base_features_row(
                player_id=1, gw=5, position_label="DEF", minutes_roll3=90.0, minutes_roll5=85.0, minutes_roll8=88.0
            ),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert "long_horizon_flag" in result.columns
        assert "minutes_roll8" in result.columns

    def test_def_low_roll8_gets_long_horizon_flag(self) -> None:
        from serve.availability import flag_availability_risk

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
        from serve.availability import flag_availability_risk

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
        from serve.availability import flag_availability_risk

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
