"""Minutes and availability risk flagging.

Identifies players with unreliable or deteriorating minute patterns. This is
an operational warning layer — it does not predict injuries or suspensions.
It surfaces observable patterns in recent playing time.

All thresholds are editorial, not evaluation-derived — see threshold-registry.md:
- _MEDIUM_RISK_MINUTES_ROLL3 = 60: FPL appearance bonus boundary (60+ min = full bonus)
- _HIGH_RISK_MINUTES_ROLL3 = 30: less than half a match on average over 3 GWs
- _DIVERGENCE_THRESHOLD = 20: observable drop in recent vs medium-term minutes

minutes_roll8 governs long_horizon_flag at DEF/MID only (minutes_roll8@avail:played_next_gw; G2-FAIL at FWD,
non-monotonic at GK). minutes_roll3 and minutes_roll5 are AVAIL-excluded at DEF,
making minutes_roll8 the only governed DEF availability signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from serve.input_contracts import (
    IntelligenceInputError,
    validate_intelligence_inputs,
)

# Risk thresholds — explicit and static.
# These reflect playing-time patterns, not injury likelihood.
_HIGH_RISK_MINUTES_ROLL3 = 30.0  # threshold not evaluation-derived — see threshold-registry.md §AVAIL-T-01
_MEDIUM_RISK_MINUTES_ROLL3 = 60.0  # threshold not evaluation-derived — see threshold-registry.md §AVAIL-T-02

# Divergence threshold: roll3 significantly below roll5 signals a recent drop.
_DIVERGENCE_THRESHOLD = 20.0  # threshold not evaluation-derived — see threshold-registry.md §AVAIL-T-03

# minutes_roll8: DEF/MID only (minutes_roll8@avail:played_next_gw; DEF rho=0.219, MID rho=0.222; G2-FAIL at FWD)
_MINUTES_ROLL8_POSITIONS = frozenset({"DEF", "MID"})

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "minutes_roll3",
    "minutes_roll5",
    "minutes_roll8",
    "minutes_trend",
    "minutes_divergence",
    "low_minutes_flag",
    "falling_trend_flag",
    "divergence_flag",
    "long_horizon_flag",
    "risk_level",
    "risk_reason",
]


def flag_availability_risk(
    features: pd.DataFrame,
    target_gw: int,
) -> pd.DataFrame:
    """Flag players with minutes/availability risk at a target gameweek.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain.
    target_gw:
        Gameweek being assessed.

    Returns
    -------
    DataFrame with one row per player containing:
    - risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
    - risk_reason: human-readable explanation of the risk classification
    - Component flag columns for each risk signal

    Risk classification logic (explicit, static rules):
    HIGH:   minutes_roll3 < 30 (rarely playing)
    MEDIUM: minutes_roll3 < 60 OR minutes_trend == 'falling'
            OR minutes_divergence > 20 (recent drop relative to 5-GW baseline)
            OR long_horizon_flag == 1 (DEF/MID only: minutes_roll8 < 60;
               minutes_roll8@avail:played_next_gw governed signal)
    LOW:    none of the above

    All players at target_gw are included, not just risky ones, so consumers
    can filter for LOW-risk players when building squads.
    """
    validate_intelligence_inputs(features, "flag_availability_risk")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"flag_availability_risk: no data for gw={target_gw}")

    roll3 = gw_df["minutes_roll3"].fillna(0)
    roll5 = gw_df["minutes_roll5"].fillna(0)
    roll8 = gw_df["minutes_roll8"].fillna(0)
    trend = gw_df["minutes_trend"].fillna("")

    # Component risk signals — each is a binary flag.
    gw_df["minutes_divergence"] = (roll5 - roll3).clip(lower=0)
    gw_df["low_minutes_flag"] = (roll3 < _MEDIUM_RISK_MINUTES_ROLL3).astype(int)
    gw_df["falling_trend_flag"] = (trend == "falling").astype(int)
    gw_df["divergence_flag"] = (gw_df["minutes_divergence"] > _DIVERGENCE_THRESHOLD).astype(int)

    # Long-horizon availability signal for DEF/MID (minutes_roll8; minutes_roll8@avail:played_next_gw): flagged when
    # 8-GW baseline also shows low participation. minutes_roll3/roll5 are AVAIL-excluded at
    # DEF, making minutes_roll8 the only governed DEF availability signal.
    gw_df["long_horizon_flag"] = (
        (roll8 < _MEDIUM_RISK_MINUTES_ROLL3) & gw_df["position_label"].isin(_MINUTES_ROLL8_POSITIONS)
    ).astype(int)

    # Risk level: evaluated in priority order (HIGH → MEDIUM → LOW).
    conditions = [
        roll3 < _HIGH_RISK_MINUTES_ROLL3,
        (roll3 < _MEDIUM_RISK_MINUTES_ROLL3)
        | (trend == "falling")
        | (gw_df["minutes_divergence"] > _DIVERGENCE_THRESHOLD)
        | (gw_df["long_horizon_flag"] == 1),
    ]
    choices = ["HIGH", "MEDIUM"]
    gw_df["risk_level"] = np.select(conditions, choices, default="LOW")

    # Human-readable explanation for each risk level.
    def _explain(row: pd.Series) -> str:
        if row["risk_level"] == "HIGH":
            return f"Avg {row['minutes_roll3']:.0f} min last 3 GW — rarely playing"
        if row["risk_level"] == "MEDIUM":
            parts = []
            if row["low_minutes_flag"]:
                parts.append(f"avg {row['minutes_roll3']:.0f} min (rotation risk)")
            if row["falling_trend_flag"]:
                parts.append("falling minutes trend")
            if row["divergence_flag"]:
                parts.append(f"recent drop ({row['minutes_roll3']:.0f} vs {row['minutes_roll5']:.0f} 5-GW avg)")
            if row["long_horizon_flag"]:
                parts.append(f"8-GW avg {row['minutes_roll8']:.0f} min also low")
            return "; ".join(parts) if parts else "borderline minutes"
        return "stable minutes"

    gw_df["risk_reason"] = gw_df.apply(_explain, axis=1)

    return gw_df[_OUTPUT_COLS].reset_index(drop=True)
