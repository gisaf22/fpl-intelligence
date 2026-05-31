"""Tests for the operational intelligence output layer.

Validates deterministic output, governance enforcement, ranking behavior,
filtering contracts, and explainability column presence.

Uses minimal synthetic DataFrames — no test DB dependency — to keep tests
focused on output contracts rather than DAL integration.
"""

from __future__ import annotations

import pandas as pd
import pytest

from intelligence.intelligence_contracts import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)
from intelligence.availability import flag_availability_risk
from intelligence.captain import rank_captain_candidates
from intelligence.fixtures import rank_fixture_opportunities
from intelligence.transfers import rank_transfer_targets
from intelligence.value import rank_value_players


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _base_row(
    player_id: int,
    gw: int,
    position_label: str = "MID",
    minutes_roll3: float = 90.0,
    minutes_roll5: float = 85.0,
    minutes_roll8: float = 88.0,
    points_roll3: float = 6.0,
    points_roll5: float = 5.5,
    xgi_roll3: float = 0.5,
    xgi_roll5: float | None = None,
    fdr_avg: float = 3.0,
    purchase_price: float = 7.5,
    goals_scored: float = 0.5,
    minutes_trend: str = "stable",
    is_dgw: bool = False,
    fixture_context: str = "SGW",
) -> dict:
    """Produce a single row with all required intelligence columns."""
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"Player_{player_id}",
        "position_label": position_label,
        "position_code": 3,
        "team_id": player_id * 10,
        "purchase_price": purchase_price,
        "fdr_avg": fdr_avg,
        "fdr_min": fdr_avg - 0.5,
        "is_bgw": False,
        "is_dgw": is_dgw,
        "goals_scored": goals_scored,
        "points_roll3": points_roll3,
        "points_roll5": points_roll5,
        "minutes_roll3": minutes_roll3,
        "minutes_roll5": minutes_roll5,
        "minutes_roll8": minutes_roll8,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": (xgi_roll3 - 0.1) if xgi_roll5 is None else xgi_roll5,
        "xgc_roll3": 0.2,
        "xgc_roll5": 0.25,
        "goals_conceded_roll3": 0.3,
        "goals_conceded_roll5": 0.4,
        "minutes_trend": minutes_trend,
        "fixture_context": fixture_context,
    }


def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture
def two_player_features():
    """Two players at GW 5: player 1 has better form, player 2 is cheaper."""
    return _make_features(
        _base_row(1, 5, points_roll3=8.0, xgi_roll3=0.9, fdr_avg=2.0,
                  purchase_price=9.0),
        _base_row(2, 5, points_roll3=5.0, xgi_roll3=0.4, fdr_avg=3.5,
                  purchase_price=5.5),
    )


@pytest.fixture
def multi_gw_features():
    """Four players across two GWs with mixed positions."""
    return _make_features(
        _base_row(1, 4, position_label="FWD", points_roll3=7.0),
        _base_row(2, 4, position_label="MID", points_roll3=6.0),
        _base_row(1, 5, position_label="FWD", points_roll3=8.0),
        _base_row(2, 5, position_label="MID", points_roll3=5.0),
    )


# ---------------------------------------------------------------------------
# _base utilities
# ---------------------------------------------------------------------------

class TestNormalizeWithinPosition:
    def test_values_in_0_1_range(self, two_player_features):
        result = normalize_within_position(two_player_features, "points_roll3")
        assert result.between(0.0, 1.0).all()

    def test_higher_value_gets_higher_score(self, two_player_features):
        result = normalize_within_position(two_player_features, "points_roll3")
        # player 1 (row 0) has higher points_roll3 → higher normalized score
        assert result.iloc[0] > result.iloc[1]

    def test_all_equal_returns_half(self):
        df = _make_features(
            _base_row(1, 1, points_roll3=5.0),
            _base_row(2, 1, points_roll3=5.0),
        )
        result = normalize_within_position(df, "points_roll3")
        assert (result == 0.5).all()

    def test_nan_filled_with_neutral(self):
        df = _make_features(
            _base_row(1, 1, points_roll3=6.0),
            _base_row(2, 1, points_roll3=float("nan")),
        )
        df["points_roll3"] = df["points_roll3"].astype(float)
        result = normalize_within_position(df, "points_roll3")
        assert not result.isna().any()


class TestWeightedComposite:
    def test_equal_weights_averages_components(self):
        df = pd.DataFrame({"a": [1.0], "b": [0.0]})
        result = weighted_composite(df, ["a", "b"], {"a": 0.5, "b": 0.5})
        assert abs(result.iloc[0] - 0.5) < 1e-9

    def test_unequal_weights_applied_correctly(self):
        df = pd.DataFrame({"a": [1.0], "b": [0.0]})
        result = weighted_composite(df, ["a", "b"], {"a": 0.8, "b": 0.2})
        # 1.0 * 0.8 / 1.0 + 0.0 * 0.2 / 1.0 = 0.8
        assert abs(result.iloc[0] - 0.8) < 1e-9


class TestValidateIntelligenceInputs:
    def test_valid_input_passes(self, two_player_features):
        validate_intelligence_inputs(two_player_features, "test")

    def test_missing_column_raises(self, two_player_features):
        df = two_player_features.drop(columns=["xgi_roll5"])
        with pytest.raises(IntelligenceInputError, match="missing required columns"):
            validate_intelligence_inputs(df, "test")

    def test_multiple_missing_columns_listed(self, two_player_features):
        df = two_player_features.drop(columns=["xgi_roll5", "minutes_roll5"])
        with pytest.raises(IntelligenceInputError) as exc_info:
            validate_intelligence_inputs(df, "test")
        msg = str(exc_info.value)
        assert "xgi_roll5" in msg or "minutes_roll5" in msg


# ---------------------------------------------------------------------------
# Captain candidates
# ---------------------------------------------------------------------------

class TestRankCaptainCandidates:
    def test_returns_expected_columns(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5)
        for col in ["form_score", "involvement_score", "fixture_score",
                    "minutes_score", "captain_score", "captain_rank"]:
            assert col in result.columns, f"missing column: {col}"

    def test_is_deterministic(self, two_player_features):
        r1 = rank_captain_candidates(two_player_features, target_gw=5)
        r2 = rank_captain_candidates(two_player_features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

    def test_top_row_has_highest_score(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5)
        assert result["captain_score"].is_monotonic_decreasing

    def test_higher_form_player_ranks_first(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5)
        # player 1 has better form and involvement — should be top
        assert result.iloc[0]["player_id"] == 1

    def test_filters_low_minutes_players(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=90.0),
            _base_row(2, 5, minutes_roll3=20.0),  # below threshold
        )
        result = rank_captain_candidates(features, target_gw=5)
        assert 2 not in result["player_id"].values

    def test_no_data_for_gw_raises(self, two_player_features):
        with pytest.raises(IntelligenceInputError, match="no data for gw=99"):
            rank_captain_candidates(two_player_features, target_gw=99)

    def test_empty_after_minutes_filter_returns_empty(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=10.0),
            _base_row(2, 5, minutes_roll3=15.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        assert result.empty

    def test_n_limits_output_rows(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5, n=1)
        assert len(result) <= 1

    def test_missing_column_raises_governance_error(self, two_player_features):
        df = two_player_features.drop(columns=["xgi_roll3"])
        with pytest.raises(IntelligenceInputError):
            rank_captain_candidates(df, target_gw=5)

    def test_scores_in_0_1_range(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5)
        for col in ["form_score", "involvement_score", "fixture_score",
                    "minutes_score", "captain_score"]:
            assert result[col].between(0.0, 1.0).all(), f"{col} out of [0,1]"


# ---------------------------------------------------------------------------
# Transfer targets
# ---------------------------------------------------------------------------

class TestRankTransferTargets:
    def test_returns_expected_columns(self, two_player_features):
        result = rank_transfer_targets(two_player_features, target_gw=5)
        for col in ["recent_form_score", "form_momentum_score", "fixture_score",
                    "involvement_score", "minutes_stability_score",
                    "transfer_score", "transfer_rank"]:
            assert col in result.columns

    def test_is_deterministic(self, two_player_features):
        r1 = rank_transfer_targets(two_player_features, target_gw=5)
        r2 = rank_transfer_targets(two_player_features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

    def test_position_filter_works(self, multi_gw_features):
        result_fwd = rank_transfer_targets(
            multi_gw_features, target_gw=5, position="FWD"
        )
        assert (result_fwd["position_label"] == "FWD").all()

    def test_position_filter_unknown_position_returns_empty(
        self, two_player_features
    ):
        result = rank_transfer_targets(
            two_player_features, target_gw=5, position="GK"
        )
        assert result.empty

    def test_rising_form_player_preferred(self):
        # Player 1: xgi_roll3 > xgi_roll5 (rising xgi momentum)
        # Player 2: xgi_roll3 < xgi_roll5 (declining xgi momentum)
        features = _make_features(
            _base_row(1, 5, xgi_roll3=0.8, xgi_roll5=0.4),
            _base_row(2, 5, xgi_roll3=0.4, xgi_roll5=0.8),
        )
        result = rank_transfer_targets(features, target_gw=5)
        assert result.iloc[0]["player_id"] == 1

    def test_filters_low_minutes_roll5(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll5=90.0),
            _base_row(2, 5, minutes_roll5=10.0),  # below threshold
        )
        result = rank_transfer_targets(features, target_gw=5)
        assert 2 not in result["player_id"].values

    def test_purchase_price_in_output(self, two_player_features):
        result = rank_transfer_targets(two_player_features, target_gw=5)
        assert "purchase_price" in result.columns

    def test_missing_column_raises(self, two_player_features):
        df = two_player_features.drop(columns=["xgi_roll5"])
        with pytest.raises(IntelligenceInputError):
            rank_transfer_targets(df, target_gw=5)


# ---------------------------------------------------------------------------
# Value players
# ---------------------------------------------------------------------------

class TestRankValuePlayers:
    def test_returns_expected_columns(self, two_player_features):
        result = rank_value_players(two_player_features, target_gw=5)
        for col in ["xgi_per_cost", "efficiency_score", "form_score",
                    "consistency_score", "value_score", "value_rank"]:
            assert col in result.columns

    def test_is_deterministic(self, two_player_features):
        r1 = rank_value_players(two_player_features, target_gw=5)
        r2 = rank_value_players(two_player_features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

    def test_cheaper_player_may_rank_higher_on_value(self):
        # Player 1: same xgi, high price → low xgi/cost
        # Player 2: same xgi, low price → high xgi/cost
        features = _make_features(
            _base_row(1, 5, xgi_roll3=0.5, xgi_roll5=0.4, purchase_price=12.0),
            _base_row(2, 5, xgi_roll3=0.5, xgi_roll5=0.4, purchase_price=5.5),
        )
        result = rank_value_players(features, target_gw=5)
        # P2 xgi_per_cost = 0.4/5.5 ≈ 0.073; P1 = 0.4/12 ≈ 0.033 → P2 ranks higher
        assert result.iloc[0]["player_id"] == 2

    def test_xgi_per_cost_computed_correctly(self, two_player_features):
        result = rank_value_players(two_player_features, target_gw=5)
        for _, row in result.iterrows():
            expected_xpc = row["xgi_roll5"] / row["purchase_price"]
            assert abs(row["xgi_per_cost"] - expected_xpc) < 1e-6

    def test_max_price_filter_works(self):
        features = _make_features(
            _base_row(1, 5, purchase_price=12.0),
            _base_row(2, 5, purchase_price=6.0),
        )
        result = rank_value_players(features, target_gw=5, max_price=7.0)
        assert (result["purchase_price"] <= 7.0).all()
        assert 1 not in result["player_id"].values

    def test_low_price_players_excluded(self):
        features = _make_features(
            _base_row(1, 5, purchase_price=2.0),  # below _MIN_PRICE
            _base_row(2, 5, purchase_price=7.0),
        )
        result = rank_value_players(features, target_gw=5)
        assert 1 not in result["player_id"].values

    def test_missing_column_raises(self, two_player_features):
        df = two_player_features.drop(columns=["purchase_price"])
        with pytest.raises(IntelligenceInputError):
            rank_value_players(df, target_gw=5)


# ---------------------------------------------------------------------------
# Availability risk
# ---------------------------------------------------------------------------

class TestFlagAvailabilityRisk:
    def test_returns_expected_columns(self, two_player_features):
        result = flag_availability_risk(two_player_features, target_gw=5)
        for col in ["risk_level", "risk_reason", "low_minutes_flag",
                    "falling_trend_flag", "divergence_flag", "minutes_divergence"]:
            assert col in result.columns

    def test_all_players_included(self, two_player_features):
        result = flag_availability_risk(two_player_features, target_gw=5)
        assert len(result) == 2

    def test_high_risk_for_very_low_minutes(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=10.0),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert result.iloc[0]["risk_level"] == "HIGH"

    def test_medium_risk_for_falling_trend(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=75.0, minutes_trend="falling"),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert result.iloc[0]["risk_level"] == "MEDIUM"

    def test_medium_risk_for_low_minutes_roll3(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=45.0, minutes_trend="stable"),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert result.iloc[0]["risk_level"] == "MEDIUM"

    def test_medium_risk_for_divergence(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=65.0, minutes_roll5=90.0,
                      minutes_trend="stable"),
        )
        result = flag_availability_risk(features, target_gw=5)
        # divergence = 90 - 65 = 25 > 20 threshold
        assert result.iloc[0]["risk_level"] == "MEDIUM"
        assert result.iloc[0]["divergence_flag"] == 1

    def test_low_risk_for_stable_player(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll3=90.0, minutes_roll5=88.0,
                      minutes_trend="stable"),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert result.iloc[0]["risk_level"] == "LOW"

    def test_risk_reason_populated(self, two_player_features):
        result = flag_availability_risk(two_player_features, target_gw=5)
        assert result["risk_reason"].notna().all()
        assert (result["risk_reason"].str.len() > 0).all()

    def test_high_risk_overrides_medium(self):
        # Even with falling trend, very low minutes → HIGH not MEDIUM.
        features = _make_features(
            _base_row(1, 5, minutes_roll3=5.0, minutes_trend="falling"),
        )
        result = flag_availability_risk(features, target_gw=5)
        assert result.iloc[0]["risk_level"] == "HIGH"

    def test_no_data_for_gw_raises(self, two_player_features):
        with pytest.raises(IntelligenceInputError, match="no data for gw=99"):
            flag_availability_risk(two_player_features, target_gw=99)

    def test_missing_column_raises(self, two_player_features):
        df = two_player_features.drop(columns=["minutes_trend"])
        with pytest.raises(IntelligenceInputError):
            flag_availability_risk(df, target_gw=5)


# ---------------------------------------------------------------------------
# Fixture opportunities
# ---------------------------------------------------------------------------

class TestRankFixtureOpportunities:
    def test_returns_expected_columns(self, multi_gw_features):
        result = rank_fixture_opportunities(multi_gw_features, target_gw=5)
        # fdr_opportunity_score not in fixtures registry (fdr_avg G2-FAIL at all positions)
        for col in ["fdr_window_avg", "dgw_in_window", "team_goals_roll5",
                    "team_attack_score",
                    "dgw_bonus_score", "fixture_opportunity_score",
                    "fixture_opportunity_rank"]:
            assert col in result.columns
        # Confirm fdr_opportunity_score is no longer present
        assert "fdr_opportunity_score" not in result.columns

    def test_is_deterministic(self, multi_gw_features):
        r1 = rank_fixture_opportunities(multi_gw_features, target_gw=5)
        r2 = rank_fixture_opportunities(multi_gw_features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

    def test_dgw_fixture_scores_higher(self):
        # fixture_score uses binary DGW indicator from STATE fixture_context column
        features = _make_features(
            _base_row(1, 5, fixture_context="DGW"),   # double gameweek → higher score
            _base_row(2, 5, fixture_context="SGW"),   # single gameweek
        )
        result = rank_fixture_opportunities(features, target_gw=5)
        assert result.iloc[0]["player_id"] == 1

    def test_dgw_bonus_applied(self):
        # DGW detection reads STATE fixture_context, not spine is_dgw (governed column access)
        features = _make_features(
            _base_row(1, 5, fixture_context="DGW", fdr_avg=3.0),
            _base_row(2, 5, fixture_context="SGW", fdr_avg=3.0),
        )
        result = rank_fixture_opportunities(features, target_gw=5)
        dgw_row = result[result["player_id"] == 1].iloc[0]
        non_dgw_row = result[result["player_id"] == 2].iloc[0]
        assert dgw_row["dgw_bonus_score"] == 1.0
        assert non_dgw_row["dgw_bonus_score"] == 0.0
        # DGW player should score higher (all else equal)
        assert dgw_row["fixture_opportunity_score"] > non_dgw_row["fixture_opportunity_score"]

    def test_filters_low_minutes_players(self):
        features = _make_features(
            _base_row(1, 5, minutes_roll5=90.0),
            _base_row(2, 5, minutes_roll5=5.0),  # below threshold
        )
        result = rank_fixture_opportunities(features, target_gw=5)
        assert 2 not in result["player_id"].values

    def test_no_data_for_gw_raises(self, multi_gw_features):
        with pytest.raises(IntelligenceInputError, match="no data for gw=99"):
            rank_fixture_opportunities(multi_gw_features, target_gw=99)

    def test_n_limits_output_rows(self, multi_gw_features):
        result = rank_fixture_opportunities(multi_gw_features, target_gw=5, n=1)
        assert len(result) <= 1

    def test_missing_column_raises(self, multi_gw_features):
        df = multi_gw_features.drop(columns=["fdr_avg"])
        with pytest.raises(IntelligenceInputError):
            rank_fixture_opportunities(df, target_gw=5)


# ---------------------------------------------------------------------------
# Cross-module: governance and explainability
# ---------------------------------------------------------------------------

class TestIntelligenceGovernance:
    """Governance contracts across all intelligence outputs."""

    _ALL_FUNCTIONS = [
        ("rank_captain_candidates", rank_captain_candidates),
        ("rank_transfer_targets", rank_transfer_targets),
        ("rank_value_players", rank_value_players),
        ("flag_availability_risk", flag_availability_risk),
        ("rank_fixture_opportunities", rank_fixture_opportunities),
    ]

    @pytest.mark.parametrize("name,fn", _ALL_FUNCTIONS)
    def test_all_reject_missing_required_column(self, name, fn, two_player_features):
        df = two_player_features.drop(columns=["goals_conceded_roll3"])
        with pytest.raises(IntelligenceInputError):
            fn(df, target_gw=5)

    def test_intelligence_does_not_import_eda(self):
        """Intelligence modules must not depend on research EDA paths."""
        import intelligence.captain as cap_mod
        import intelligence.transfers as trans_mod
        import intelligence.value as val_mod
        import intelligence.availability as avail_mod
        import intelligence.fixtures as fix_mod

        for mod in [cap_mod, trans_mod, val_mod, avail_mod, fix_mod]:
            src = mod.__file__
            with open(src) as f:
                content = f.read()
            assert "studies/eda" not in content, (
                f"{mod.__name__} imports from studies/eda — "
                "research artifacts must not enter operational outputs"
            )
            assert "RESEARCH_REGISTRY_PATH" not in content, (
                f"{mod.__name__} references RESEARCH_REGISTRY_PATH"
            )

    def test_captain_explainability_columns_present(self, two_player_features):
        result = rank_captain_candidates(two_player_features, target_gw=5)
        for col in ["form_score", "involvement_score", "fixture_score", "minutes_score"]:
            assert col in result.columns

    def test_transfers_explainability_columns_present(self, two_player_features):
        result = rank_transfer_targets(two_player_features, target_gw=5)
        for col in ["recent_form_score", "form_momentum_score", "fixture_score"]:
            assert col in result.columns

    def test_value_explainability_columns_present(self, two_player_features):
        result = rank_value_players(two_player_features, target_gw=5)
        for col in ["xgi_per_cost", "efficiency_score", "consistency_score"]:
            assert col in result.columns

    def test_availability_explainability_columns_present(self, two_player_features):
        result = flag_availability_risk(two_player_features, target_gw=5)
        for col in ["low_minutes_flag", "falling_trend_flag", "divergence_flag", "risk_reason"]:
            assert col in result.columns

    def test_fixtures_explainability_columns_present(self, multi_gw_features):
        result = rank_fixture_opportunities(multi_gw_features, target_gw=5)
        for col in ["fdr_window_avg", "dgw_in_window", "team_goals_roll5"]:
            assert col in result.columns
