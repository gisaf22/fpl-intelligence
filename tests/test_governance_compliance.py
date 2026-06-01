"""Governance compliance behavioral tests for the intelligence layer.

These tests guard against regression of documented SYNTH-01 scope decisions
and confirmed governance violations. Each test names the gate decision it
enforces.

SYNTH-01 decisions guarded:
- G-SYNTH1-07: xgi_roll3 EXCLUDED-REDUNDANT at MID (captain.py, value.py, transfers.py)
- FORM-001/002: xgi_roll3/xgi_roll5 excluded at FWD (all modules)
- AVAIL-003: minutes_roll8 positional guard (DEF/MID only in availability.py)
- FIXTURE-001: fdr_avg must not contribute to fixture_opportunity_score

Novel unevaluated metrics flagged:
- PENDING-EVAL-01: consistency_score in value.py
- PENDING-EVAL-02: team_goals_roll5 in fixtures.py
- PENDING-EVAL-03: form_momentum_score in transfers.py
"""

from __future__ import annotations

import pandas as pd
import pytest

from intelligence.availability import flag_availability_risk
from intelligence.captain import rank_captain_candidates
from intelligence.fixtures import rank_fixture_opportunities
from intelligence.transfers import rank_transfer_targets
from intelligence.value import rank_value_players

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _row(
    player_id: int,
    gw: int,
    position_label: str = "MID",
    xgi_roll3: float = 0.6,
    xgi_roll5: float = 0.5,
    minutes_roll3: float = 85.0,
    minutes_roll5: float = 82.0,
    minutes_roll8: float = 80.0,
    minutes_trend: str = "stable",
    fixture_context: str = "SGW",
    fdr_avg: float = 3.0,
    purchase_price: float = 7.5,
    goals_scored: float = 1.0,
    team_id: int = 10,
) -> dict:
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"P{player_id}",
        "position_label": position_label,
        "position_code": {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}[position_label],
        "team_id": team_id,
        "purchase_price": purchase_price,
        "fdr_avg": fdr_avg,
        "is_bgw": False,
        "goals_scored": goals_scored,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": xgi_roll5,
        "xgc_roll3": 0.2,
        "xgc_roll5": 0.2,
        "clean_sheets_roll3": 0.15,
        "clean_sheets_roll5": 0.15,
        "goals_conceded_roll3": 0.8,
        "goals_conceded_roll5": 0.8,
        "minutes_roll3": minutes_roll3,
        "minutes_roll5": minutes_roll5,
        "minutes_roll8": minutes_roll8,
        "minutes_trend": minutes_trend,
        "fixture_context": fixture_context,
    }


def _features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# SYNTH-01 G-SYNTH1-07: xgi_roll3 zeroed at MID in captain.py
# ---------------------------------------------------------------------------

class TestCaptainMidXgiGuard:
    """G-SYNTH1-07: xgi_roll3 EXCLUDED-REDUNDANT at MID in captain.py.

    involvement_score for MID must be neutral 0.5 regardless of xgi_roll3
    value, because all MID players are zeroed before normalize_within_position.
    """

    def test_mid_involvement_score_is_neutral_regardless_of_xgi(self):
        """Two MID players with very different xgi_roll3 must have the same
        involvement_score (both zeroed → all-equal group → 0.5 from normalization)."""
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll3=0.9, minutes_roll3=85.0),
            _row(2, 5, position_label="MID", xgi_roll3=0.1, minutes_roll3=85.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"]
        assert len(mid_rows) == 2

        scores = mid_rows["involvement_score"].unique()
        assert len(scores) == 1, (
            f"G-SYNTH1-07: MID players with different xgi_roll3 must have identical "
            f"involvement_score (all zeroed → 0.5). Got {mid_rows['involvement_score'].tolist()}"
        )
        assert abs(scores[0] - 0.5) < 1e-9, (
            f"G-SYNTH1-07: MID involvement_score must be 0.5, got {scores[0]}"
        )

    def test_mid_form_score_not_neutralized(self):
        """form_score uses xgi_roll5 which is NOT excluded at MID.
        Verify differentiation at MID via form_score (xgi_roll5)."""
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll5=0.9, xgi_roll3=0.5, minutes_roll3=85.0),
            _row(2, 5, position_label="MID", xgi_roll5=0.1, xgi_roll3=0.5, minutes_roll3=85.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"].set_index("player_id")

        assert mid_rows.loc[1, "form_score"] > mid_rows.loc[2, "form_score"], (
            "MID form_score (xgi_roll5) must differentiate players"
        )


# ---------------------------------------------------------------------------
# SYNTH-01 G-SYNTH1-07: xgi_roll3 zeroed at MID in value.py
# ---------------------------------------------------------------------------

class TestValueMidXgiGuard:
    """G-SYNTH1-07: xgi_roll3 EXCLUDED-REDUNDANT at MID in value.py.

    form_score and consistency_score must be neutral 0.5 for all MID players
    regardless of xgi_roll3 value. efficiency_score (driven by xgi_roll5, which
    is approved at MID) must still differentiate MID players.
    """

    def test_mid_form_score_is_neutral_regardless_of_xgi(self):
        """Two MID players with different xgi_roll3 must have equal form_score (0.5)."""
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll3=0.9, xgi_roll5=0.5,
                 minutes_roll5=85.0, purchase_price=7.5),
            _row(2, 5, position_label="MID", xgi_roll3=0.1, xgi_roll5=0.5,
                 minutes_roll5=85.0, purchase_price=7.5),
        )
        result = rank_value_players(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"]
        assert len(mid_rows) == 2

        scores = mid_rows["form_score"].unique()
        assert len(scores) == 1, (
            f"G-SYNTH1-07: MID form_score must be equal for all MID players. "
            f"Got {mid_rows['form_score'].tolist()}"
        )
        assert abs(scores[0] - 0.5) < 1e-9, (
            f"G-SYNTH1-07: MID form_score must be 0.5, got {scores[0]}"
        )

    def test_mid_consistency_score_is_neutral_regardless_of_xgi(self):
        """MID consistency_score must be 0.5 regardless of xgi_roll3 value.

        Consistency compares xgi_roll3 vs xgi_roll5. Since xgi_roll3 is zeroed
        at MID, the comparison is neutralised to prevent perverse ranking.
        """
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll3=0.9, xgi_roll5=0.8,
                 minutes_roll5=85.0, purchase_price=7.5),
            _row(2, 5, position_label="MID", xgi_roll3=0.1, xgi_roll5=0.8,
                 minutes_roll5=85.0, purchase_price=7.5),
        )
        result = rank_value_players(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"]

        scores = mid_rows["consistency_score"].unique()
        assert len(scores) == 1, (
            f"G-SYNTH1-07: MID consistency_score must be equal (neutralised). "
            f"Got {mid_rows['consistency_score'].tolist()}"
        )
        assert abs(scores[0] - 0.5) < 1e-9, (
            f"G-SYNTH1-07: MID consistency_score must be 0.5, got {scores[0]}"
        )

    def test_mid_efficiency_score_not_neutralized(self):
        """efficiency_score uses xgi_roll5 which is approved at MID (not excluded).
        MID players must be differentiated by efficiency_score."""
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll5=0.9, xgi_roll3=0.5,
                 minutes_roll5=85.0, purchase_price=7.5),
            _row(2, 5, position_label="MID", xgi_roll5=0.1, xgi_roll3=0.5,
                 minutes_roll5=85.0, purchase_price=7.5),
        )
        result = rank_value_players(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"].set_index("player_id")

        assert mid_rows.loc[1, "efficiency_score"] > mid_rows.loc[2, "efficiency_score"], (
            "G-SYNTH1-07: MID efficiency_score (xgi_roll5) must differentiate players"
        )


# ---------------------------------------------------------------------------
# SYNTH-01 G-SYNTH1-07: xgi_roll3 zeroed at MID in transfers.py
# ---------------------------------------------------------------------------

class TestTransfersMidXgiGuard:
    """G-SYNTH1-07: xgi_roll3 EXCLUDED-REDUNDANT at MID in transfers.py.

    recent_form_score, involvement_score, and form_momentum_score must be neutral
    0.5 for all MID players regardless of xgi_roll3 value. fixture_score and
    minutes_stability_score must still differentiate MID players.
    """

    def test_mid_form_and_involvement_scores_neutral(self):
        """recent_form_score and involvement_score must be 0.5 for all MID players."""
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll3=0.9, xgi_roll5=0.5,
                 minutes_roll5=85.0),
            _row(2, 5, position_label="MID", xgi_roll3=0.1, xgi_roll5=0.5,
                 minutes_roll5=85.0),
        )
        result = rank_transfer_targets(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"]
        assert len(mid_rows) == 2

        for score_col in ("recent_form_score", "involvement_score"):
            scores = mid_rows[score_col].unique()
            assert len(scores) == 1, (
                f"G-SYNTH1-07: MID {score_col} must be equal for all MID. "
                f"Got {mid_rows[score_col].tolist()}"
            )
            assert abs(scores[0] - 0.5) < 1e-9, (
                f"G-SYNTH1-07: MID {score_col} must be 0.5, got {scores[0]}"
            )

    def test_mid_momentum_score_neutral(self):
        """form_momentum_score must be 0.5 for all MID players.

        Momentum = xgi_roll3 - xgi_roll5. Since xgi_roll3 is zeroed at MID,
        the comparison is neutralised to prevent always-negative momentum.
        """
        features = _features(
            _row(1, 5, position_label="MID", xgi_roll3=0.9, xgi_roll5=0.5,
                 minutes_roll5=85.0),
            _row(2, 5, position_label="MID", xgi_roll3=0.1, xgi_roll5=0.5,
                 minutes_roll5=85.0),
        )
        result = rank_transfer_targets(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"]

        scores = mid_rows["form_momentum_score"].unique()
        assert len(scores) == 1, (
            f"G-SYNTH1-07: MID form_momentum_score must be equal (neutralised). "
            f"Got {mid_rows['form_momentum_score'].tolist()}"
        )
        assert abs(scores[0] - 0.5) < 1e-9, (
            f"G-SYNTH1-07: MID form_momentum_score must be 0.5, got {scores[0]}"
        )

    def test_mid_fixture_score_not_neutralized(self):
        """fixture_score uses fixture_context which is not xgi-based.
        MID players must still be differentiated by fixture_score."""
        features = _features(
            _row(1, 5, position_label="MID", fixture_context="DGW", minutes_roll5=85.0),
            _row(2, 5, position_label="MID", fixture_context="SGW", minutes_roll5=85.0),
        )
        result = rank_transfer_targets(features, target_gw=5)
        mid_rows = result[result["position_label"] == "MID"].set_index("player_id")

        assert mid_rows.loc[1, "fixture_score"] > mid_rows.loc[2, "fixture_score"], (
            "G-SYNTH1-07: MID fixture_score must differentiate DGW vs SGW players"
        )


# ---------------------------------------------------------------------------
# FORM-001/002: FWD zeroing guard in captain.py, value.py, transfers.py
# ---------------------------------------------------------------------------

class TestFwdZeroingGuard:
    """FORM-001/002 G2-FAIL: xgi signals excluded at FWD across all three modules.

    Zeroing produces neutral 0.5 for all FWD players — they are not ranked by
    xgi, but they remain in the output. This is different from positional exclusion.
    """

    def test_captain_fwd_form_score_neutral(self):
        """FWD form_score (xgi_roll5) must be 0.5 regardless of xgi_roll5."""
        features = _features(
            _row(1, 5, position_label="FWD", xgi_roll5=0.9, minutes_roll3=85.0),
            _row(2, 5, position_label="FWD", xgi_roll5=0.1, minutes_roll3=85.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        fwd_rows = result[result["position_label"] == "FWD"]
        assert len(fwd_rows) == 2

        for _, row in fwd_rows.iterrows():
            assert abs(row["form_score"] - 0.5) < 1e-9, (
                f"FORM-002: FWD form_score must be 0.5, got {row['form_score']} "
                f"for player {row['player_id']}"
            )

    def test_captain_fwd_involvement_score_neutral(self):
        """FWD involvement_score (xgi_roll3) must be 0.5 regardless of xgi_roll3."""
        features = _features(
            _row(1, 5, position_label="FWD", xgi_roll3=0.9, minutes_roll3=85.0),
            _row(2, 5, position_label="FWD", xgi_roll3=0.1, minutes_roll3=85.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        fwd_rows = result[result["position_label"] == "FWD"]

        for _, row in fwd_rows.iterrows():
            assert abs(row["involvement_score"] - 0.5) < 1e-9, (
                f"FORM-001: FWD involvement_score must be 0.5, got {row['involvement_score']}"
            )

    def test_transfers_fwd_form_scores_neutral(self):
        """FWD recent_form_score and involvement_score must be 0.5 in transfers.py."""
        features = _features(
            _row(1, 5, position_label="FWD", xgi_roll3=0.9, xgi_roll5=0.8, minutes_roll5=85.0),
            _row(2, 5, position_label="FWD", xgi_roll3=0.1, xgi_roll5=0.1, minutes_roll5=85.0),
        )
        result = rank_transfer_targets(features, target_gw=5)
        fwd_rows = result[result["position_label"] == "FWD"]
        assert len(fwd_rows) == 2

        for _, row in fwd_rows.iterrows():
            assert abs(row["recent_form_score"] - 0.5) < 1e-9, (
                f"FORM-001: FWD recent_form_score must be 0.5, got {row['recent_form_score']}"
            )
            assert abs(row["involvement_score"] - 0.5) < 1e-9, (
                f"FORM-001: FWD involvement_score must be 0.5, got {row['involvement_score']}"
            )

    def test_value_fwd_efficiency_score_neutral(self):
        """FWD efficiency_score and form_score must be 0.5 in value.py."""
        features = _features(
            _row(1, 5, position_label="FWD", xgi_roll3=0.9, xgi_roll5=0.8,
                 minutes_roll5=85.0, purchase_price=8.0),
            _row(2, 5, position_label="FWD", xgi_roll3=0.1, xgi_roll5=0.1,
                 minutes_roll5=85.0, purchase_price=8.0),
        )
        result = rank_value_players(features, target_gw=5)
        fwd_rows = result[result["position_label"] == "FWD"]
        assert len(fwd_rows) == 2

        for _, row in fwd_rows.iterrows():
            assert abs(row["efficiency_score"] - 0.5) < 1e-9, (
                f"FORM-002: FWD efficiency_score must be 0.5, got {row['efficiency_score']}"
            )
            assert abs(row["form_score"] - 0.5) < 1e-9, (
                f"FORM-001: FWD form_score must be 0.5, got {row['form_score']}"
            )


# ---------------------------------------------------------------------------
# AVAIL-003: minutes_roll8 positional guard in availability.py
# ---------------------------------------------------------------------------

class TestMinutesRoll8PositionalGuard:
    """AVAIL-003: minutes_roll8 wired only for DEF and MID in availability.py.

    long_horizon_flag must be 0 for GK and FWD even when minutes_roll8 < 60.
    """

    def test_gk_no_long_horizon_flag_even_with_low_roll8(self):
        features = _features(
            _row(1, 5, position_label="GK", minutes_roll8=20.0, minutes_roll3=85.0),
        )
        result = flag_availability_risk(features, target_gw=5)
        gk_row = result[result["position_label"] == "GK"].iloc[0]
        assert gk_row["long_horizon_flag"] == 0, (
            "AVAIL-003: GK must not receive long_horizon_flag regardless of minutes_roll8"
        )

    def test_fwd_no_long_horizon_flag_even_with_low_roll8(self):
        features = _features(
            _row(1, 5, position_label="FWD", minutes_roll8=20.0, minutes_roll3=85.0),
        )
        result = flag_availability_risk(features, target_gw=5)
        fwd_row = result[result["position_label"] == "FWD"].iloc[0]
        assert fwd_row["long_horizon_flag"] == 0, (
            "AVAIL-003: FWD must not receive long_horizon_flag (G2-FAIL at FWD)"
        )

    def test_def_gets_long_horizon_flag_when_roll8_low(self):
        features = _features(
            _row(1, 5, position_label="DEF", minutes_roll8=20.0, minutes_roll3=85.0),
        )
        result = flag_availability_risk(features, target_gw=5)
        def_row = result[result["position_label"] == "DEF"].iloc[0]
        assert def_row["long_horizon_flag"] == 1, (
            "AVAIL-003: DEF with minutes_roll8 < 60 must receive long_horizon_flag=1"
        )

    def test_mid_gets_long_horizon_flag_when_roll8_low(self):
        features = _features(
            _row(1, 5, position_label="MID", minutes_roll8=20.0, minutes_roll3=85.0),
        )
        result = flag_availability_risk(features, target_gw=5)
        mid_row = result[result["position_label"] == "MID"].iloc[0]
        assert mid_row["long_horizon_flag"] == 1, (
            "AVAIL-003: MID with minutes_roll8 < 60 must receive long_horizon_flag=1"
        )


# ---------------------------------------------------------------------------
# FIXTURE-001: fdr_avg must not affect fixture_opportunity_score
# ---------------------------------------------------------------------------

class TestFdrAvgNotScored:
    """FIXTURE-001 G2-FAIL: fdr_avg excluded at all positions.

    fixture_opportunity_score must be invariant to changes in fdr_avg.
    """

    def test_fixture_score_invariant_to_fdr_avg(self):
        """Two players identical except for fdr_avg must have equal
        fixture_opportunity_score (FIXTURE-001: fdr_avg not scored)."""
        features = _features(
            _row(1, 5, fdr_avg=2.0, fixture_context="SGW", goals_scored=1.0,
                 minutes_roll5=80.0, team_id=10),
            _row(2, 5, fdr_avg=5.0, fixture_context="SGW", goals_scored=1.0,
                 minutes_roll5=80.0, team_id=10),
        )
        result = rank_fixture_opportunities(features, target_gw=5, horizon=1)
        assert len(result) == 2

        p1 = result[result["player_id"] == 1]["fixture_opportunity_score"].iloc[0]
        p2 = result[result["player_id"] == 2]["fixture_opportunity_score"].iloc[0]
        assert abs(p1 - p2) < 1e-9, (
            f"FIXTURE-001: fixture_opportunity_score must be invariant to fdr_avg. "
            f"Got p1={p1:.4f}, p2={p2:.4f} despite identical non-fdr inputs"
        )


# ---------------------------------------------------------------------------
# fixture_context: DGW detection wired in captain.py and transfers.py
# ---------------------------------------------------------------------------

class TestFixtureContextWired:
    """fixture_context candidate consumed by captain.py and transfers.py.

    fixture_score must differ between DGW and SGW players.
    """

    def test_captain_fixture_score_higher_for_dgw(self):
        """DGW player must score higher on fixture_score than SGW player
        when all other inputs are equal."""
        features = _features(
            _row(1, 5, fixture_context="DGW", minutes_roll3=85.0),
            _row(2, 5, fixture_context="SGW", minutes_roll3=85.0),
        )
        result = rank_captain_candidates(features, target_gw=5)
        p1 = result[result["player_id"] == 1]["fixture_score"].iloc[0]
        p2 = result[result["player_id"] == 2]["fixture_score"].iloc[0]
        assert p1 > p2, (
            f"captain.py: DGW player must have higher fixture_score than SGW. "
            f"Got DGW={p1:.3f}, SGW={p2:.3f}"
        )

    def test_transfers_fixture_score_higher_for_dgw(self):
        """DGW player must score higher on fixture_score than SGW player
        in transfers.py ranking."""
        features = _features(
            _row(1, 5, fixture_context="DGW", minutes_roll5=82.0),
            _row(2, 5, fixture_context="SGW", minutes_roll5=82.0),
        )
        result = rank_transfer_targets(features, target_gw=5)
        p1 = result[result["player_id"] == 1]["fixture_score"].iloc[0]
        p2 = result[result["player_id"] == 2]["fixture_score"].iloc[0]
        assert p1 > p2, (
            f"transfers.py: DGW player must have higher fixture_score than SGW. "
            f"Got DGW={p1:.3f}, SGW={p2:.3f}"
        )
