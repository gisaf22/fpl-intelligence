"""Minutes and availability risk flagging.

Identifies players with unreliable or deteriorating minute patterns. This is
an operational warning layer — it does not predict injuries or suspensions.
It surfaces observable patterns in recent playing time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence._base import (
    IntelligenceInputError,
    validate_intelligence_inputs,
)

# Risk thresholds — explicit and static.
# These reflect playing-time patterns, not injury likelihood.
_HIGH_RISK_MINUTES_ROLL3 = 30.0    # Rarely starting or subbing on
_MEDIUM_RISK_MINUTES_ROLL3 = 60.0  # Rotation risk / used as sub

# Divergence threshold: roll3 significantly below roll5 signals a recent drop.
_DIVERGENCE_THRESHOLD = 20.0  # minutes

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "minutes_roll3",
    "minutes_roll5",
    "minutes_trend",
    "minutes_divergence",
    "low_minutes_flag",
    "falling_trend_flag",
    "divergence_flag",
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
    LOW:    none of the above

    All players at target_gw are included, not just risky ones, so consumers
    can filter for LOW-risk players when building squads.
    """
    validate_intelligence_inputs(features, "flag_availability_risk")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(
            f"flag_availability_risk: no data for gw={target_gw}"
        )

    roll3 = gw_df["minutes_roll3"].fillna(0)
    roll5 = gw_df["minutes_roll5"].fillna(0)
    trend = gw_df["minutes_trend"].fillna("")

    # Component risk signals — each is a binary flag.
    gw_df["minutes_divergence"] = (roll5 - roll3).clip(lower=0)
    gw_df["low_minutes_flag"] = (roll3 < _MEDIUM_RISK_MINUTES_ROLL3).astype(int)
    gw_df["falling_trend_flag"] = (trend == "falling").astype(int)
    gw_df["divergence_flag"] = (
        gw_df["minutes_divergence"] > _DIVERGENCE_THRESHOLD
    ).astype(int)

    # Risk level: evaluated in priority order (HIGH → MEDIUM → LOW).
    conditions = [
        roll3 < _HIGH_RISK_MINUTES_ROLL3,
        (roll3 < _MEDIUM_RISK_MINUTES_ROLL3)
        | (trend == "falling")
        | (gw_df["minutes_divergence"] > _DIVERGENCE_THRESHOLD),
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
                parts.append(
                    f"recent drop ({row['minutes_roll3']:.0f} vs "
                    f"{row['minutes_roll5']:.0f} 5-GW avg)"
                )
            return "; ".join(parts) if parts else "borderline minutes"
        return "stable minutes"

    gw_df["risk_reason"] = gw_df.apply(_explain, axis=1)

    return gw_df[_OUTPUT_COLS].reset_index(drop=True)
