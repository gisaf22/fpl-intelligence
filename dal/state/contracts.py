"""State layer causality contracts — declares causality, warmup, and reliability for each column.

Every derived column in the state layer must be declared here before use in any lens study.
Downstream consumers use this to understand:
  - causality: whether the value is safe to use as a pre-GW feature
  - warmup_gws: the first GW where this column is non-null
  - min_obs_for_reliability: the observation count at which the rolling average is statistically
    established (does NOT change min_periods — purely metadata for downstream filtering)
  - null_if_no_obs: whether the column is null when no observations exist
"""

from dal.state.player_gameweek_state import _ROLL_COLS

_ROLL_COL_SHORT = {col: ("points" if col == "total_points" else col) for col in _ROLL_COLS}

STATE_COL_CONTRACTS: dict[str, dict] = {}

# All rolling window columns — lag-1 convention (SC-1 fix): safe as pre-GW features
for _col in _ROLL_COLS:
    _short = "points" if _col == "total_points" else _col
    STATE_COL_CONTRACTS[f"{_short}_roll3"] = {
        "causality": "lagged",
        "warmup_gws": 1,
        "min_obs_for_reliability": 3,
        "null_if_no_obs": True,
    }
    STATE_COL_CONTRACTS[f"{_short}_roll5"] = {
        "causality": "lagged",
        "warmup_gws": 1,
        "min_obs_for_reliability": 5,
        "null_if_no_obs": True,
    }

# minutes_roll8 — approved at DEF and MID (LENS-AVAIL AVAIL-003); only roll8 window produced
STATE_COL_CONTRACTS["minutes_roll8"] = {
    "causality": "lagged",
    "warmup_gws": 1,
    "min_obs_for_reliability": 8,
    "null_if_no_obs": True,
}

# minutes_trend — requires 3 prior + 3 prior-prior GWs; warmup larger than roll3
STATE_COL_CONTRACTS["minutes_trend"] = {
    "causality": "lagged",      # SC-1 fix: uses shift(1) — safe as pre-GW feature
    "warmup_gws": 4,            # requires 3 prior + 3 prior-prior (shift(3)) non-null GWs
    "min_obs_for_reliability": 6,
    "null_if_no_obs": True,
}

# fixture_context — contemporaneous: reflects current GW fixture structure, not performance
STATE_COL_CONTRACTS["fixture_context"] = {
    "causality": "contemporaneous",
    "values": ["BGW", "SGW", "DGW"],
    "null_if_no_obs": False,
}
