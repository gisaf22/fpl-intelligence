"""Governance compliance behavioral tests for the intelligence layer.

These tests guard against regression of documented SYNTH-01 scope decisions
and confirmed governance violations. Each test names the gate decision it
enforces.

captain.py, value.py, transfers.py, and fixtures.py are RETIRED from these guards — all rank by the
model forecast, not a serve composite, so their per-position validity (and fixture context) is enforced
upstream by the term gates, not a serve scope-guard. Only availability.py remains guarded here.

Decisions guarded:
- AVAIL-003: minutes_roll8 positional guard (DEF/MID only in availability.py)
"""

from __future__ import annotations

import pandas as pd
import pytest

from serve.availability import flag_availability_risk

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
    is_warmup_gw: bool = False,
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
        "is_warmup_gw": is_warmup_gw,
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
# captain.py, value.py, transfers.py: RETIRED from these guards — none consume xgi (all rank by the
# model forecast). Per-position validity is enforced upstream by the term gates, not a serve
# scope-guard. Only fixtures.py and availability.py remain guarded below.
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
        assert fwd_row["long_horizon_flag"] == 0, "AVAIL-003: FWD must not receive long_horizon_flag (G2-FAIL at FWD)"

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


# FIXTURE-001 (fdr_avg not scored) / PENDING-EVAL-02 (team_goals_roll5): RETIRED — the fixtures composite
# is gone (transfers subsumes it via the model forecast). fdr's fixture context lives inside e_points
# (the fdr term), not a serve scope-guard, so there is no fixture_opportunity_score left to keep invariant.
