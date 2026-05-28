"""State layer — player gameweek analytical state variables."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dal.validation.grain import validate_grain_uniqueness

_ROLL_COLS = [
    "minutes",
    "xgi",
    "xgc",
    "clean_sheets",
    "goals_conceded",
]

# Columns that CURATED must provide for STATE to function correctly.
# Used by the entry contract guard — any caller (test or production) that omits
# these columns will get a clear error before any computation runs.
_REQUIRED_INPUT_COLS: frozenset[str] = frozenset(
    ["player_id", "gw", "is_bgw", "is_dgw"] + _ROLL_COLS
)

# Approved derived rolling column set — Phase 3 Representation Inventory Lock.
# Any addition to this set requires a governance decision recorded in
# docs/governance/state-representation-inventory.md and this frozenset updated.
_GOVERNED_ROLLING_COLS: frozenset[str] = frozenset({
    "xgi_roll3",            # LENS-FORM FORM-001 (DEF, MID)
    "xgi_roll5",            # LENS-FORM FORM-002 (DEF, MID)
    "xgc_roll3",            # LENS-FORM; team defensive context (DEF/GK scope)
    "xgc_roll5",            # LENS-FORM; team defensive context (DEF/GK scope)
    "clean_sheets_roll3",   # G-EDA8-05; team defensive context (DEF/GK scope)
    "clean_sheets_roll5",   # G-EDA8-05; team defensive context (DEF/GK scope)
    "goals_conceded_roll3", # G-EDA5; team defensive context (DEF/GK scope)
    "goals_conceded_roll5", # G-EDA5; team defensive context (DEF/GK scope)
    "minutes_roll3",        # LENS-AVAIL AVAIL-001 (MID)
    "minutes_roll5",        # LENS-AVAIL AVAIL-002 (MID)
    "minutes_roll8",        # LENS-AVAIL AVAIL-003 (DEF, MID)
    "minutes_trend",        # PROVISIONAL-EDITORIAL; availability domain only (STATE-T-01)
    "fixture_context",      # LENS-FIXTURE-GW; DGW/BGW classification
})

# Columns that are restricted to the availability domain only.
# Must not be consumed by form, value, or captain scoring modules.
_AVAILABILITY_DOMAIN_ONLY: frozenset[str] = frozenset({"minutes_trend"})

# Governance metadata for every derived column.
# scope: attribution unit per signal-ontology.yaml
# causality: lagged (prior GWs only) | contemporaneous (current GW)
# behavioral_reason: one-sentence rationale from STATE_CONTRACT.md and behavior profiles
# source_gate_decisions: gate IDs that produced this ruling
_COLUMN_META: dict[str, dict] = {
    # --- Process family ---
    "xgi_roll3": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "APPROVED at DEF (rho=0.123, 3/3 blocks) and MID (rho=0.144, 3/3 blocks); "
            "CONDITIONAL at FWD — CI excludes zero but fails decision relevance "
            "(haul concentration suppresses Q5-Q1 gap)"
        ),
        "source_gate_decisions": ["LENS-FORM FORM-001"],
    },
    "xgi_roll5": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "APPROVED at DEF (rho=0.113, 3/3 blocks) and MID (rho=0.157, clears naive baseline); "
            "CONDITIONAL at FWD — same haul concentration caveat as roll3"
        ),
        "source_gate_decisions": ["LENS-FORM FORM-002"],
    },
    "xgc_roll3": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": (
            "Candidate at DEF/GK scope as team defensive context signal; "
            "pooled redundancy with goals_conceded + clean_sheets (G-EDA8-05) does not rule out "
            "positional utility where clean sheets are structurally informative"
        ),
        "source_gate_decisions": ["G-EDA8-05"],
    },
    "xgc_roll5": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": (
            "Same basis as xgc_roll3; retained as candidate for DEF/GK team defensive context"
        ),
        "source_gate_decisions": ["G-EDA8-05"],
    },
    # --- Event family ---
    "clean_sheets_roll3": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": (
            "Semantically admissible (count type); CONDITIONAL pending lens study validation; "
            "xgc redundancy resolved (G-EDA8-05) confirms clean_sheets as surviving defensive signal"
        ),
        "source_gate_decisions": ["G-EDA8-05"],
    },
    "clean_sheets_roll5": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": "Same status as clean_sheets_roll3; CONDITIONAL pending lens study",
        "source_gate_decisions": ["G-EDA8-05"],
    },
    "goals_conceded_roll3": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": (
            "Semantically admissible; CONDITIONAL pending lens study validation; "
            "moderate_shift at MID (G-EDA5) means seasonal drift risk applies"
        ),
        "source_gate_decisions": ["G-EDA5"],
    },
    "goals_conceded_roll5": {
        "scope": "Team",
        "causality": "lagged",
        "behavioral_reason": "Same status as goals_conceded_roll3; MID moderate_shift risk applies",
        "source_gate_decisions": ["G-EDA5"],
    },
    # --- Participation family ---
    "minutes_roll3": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "APPROVED at MID (rho=0.179, 3/3 GW blocks); uninformative at DEF, FWD, GK; "
            "availability signal only — blocked as form proxy (G-EDA2-02)"
        ),
        "source_gate_decisions": ["LENS-AVAIL AVAIL-001"],
    },
    "minutes_roll5": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "APPROVED at MID (rho=0.168, 3/3 GW blocks); unstable at FWD (1/3 blocks); "
            "availability signal only"
        ),
        "source_gate_decisions": ["LENS-AVAIL AVAIL-002"],
    },
    "minutes_roll8": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "APPROVED at DEF (rho=0.130, 3/3 blocks) and MID (rho=0.169, 3/3 blocks); "
            "strongest availability window; uninformative at FWD and GK"
        ),
        "source_gate_decisions": ["LENS-AVAIL AVAIL-003"],
    },
    "minutes_trend": {
        "scope": "Individual",
        "causality": "lagged",
        "behavioral_reason": (
            "Directional availability trend (rising/stable/falling); "
            "CONDITIONAL — availability domain only (see _AVAILABILITY_DOMAIN_ONLY); "
            "30-minute threshold is PROVISIONAL-EDITORIAL without formal behavioral study (STATE-T-01)"
        ),
        "source_gate_decisions": ["G-EDA2-02"],
    },
    # --- Context / fixture label ---
    "fixture_context": {
        "scope": "Match",
        "causality": "contemporaneous",
        "behavioral_reason": (
            "Pre-match structural label (BGW/SGW/DGW) derived from is_bgw and is_dgw spine flags; "
            "contemporaneous; not a predictive feature; used to segment analyses by fixture type"
        ),
        "source_gate_decisions": ["Ontology"],
    },
}


def _validate_spine_entry_contract(spine: pd.DataFrame) -> None:
    """Assert CURATED → STATE boundary preconditions before any computation.

    Three invariants that STATE relies on but previously assumed without checking:
    1. Required columns present — avoids opaque KeyError deep in rolling transform.
    2. Grain uniqueness — a duplicate (player_id, gw) pair corrupts every rolling window
       for that player; the exit grain check fires too late to prevent that corruption.
    3. BGW performance columns are NULL — zero-substituted BGW values are semantically
       wrong and silently inflate rolling averages (mean([20, 0, 30]) ≠ mean([20, 30])).
    """
    missing = _REQUIRED_INPUT_COLS - set(spine.columns)
    if missing:
        raise ValueError(
            f"build_player_gameweek_state: required input columns missing: {sorted(missing)}"
        )

    dupes = spine.duplicated(subset=["player_id", "gw"])
    if dupes.any():
        n = int(dupes.sum())
        raise ValueError(
            f"build_player_gameweek_state: {n} duplicate (player_id, gw) rows in input — "
            "grain must be unique before STATE computation"
        )

    bgw = spine[spine["is_bgw"] == True]
    if not bgw.empty:
        for col in _ROLL_COLS:
            if col not in spine.columns:
                continue
            bad = bgw[bgw[col].notna()]
            if not bad.empty:
                raise ValueError(
                    f"build_player_gameweek_state: BGW rows have non-NULL '{col}' "
                    f"({len(bad)} rows) — zero-substituted BGW values corrupt rolling averages"
                )


def _compute_minutes_trend(minutes_series: pd.Series) -> pd.Series:
    # PROVISIONAL-EDITORIAL threshold — STATE-T-01: 30-minute divergence boundary has no
    # empirical calibration; availability domain only (see _AVAILABILITY_DOMAIN_ONLY).
    # shift(1): lag-1 convention — GW N trend uses only GW 1..N-1 data, never GW N itself
    last3 = minutes_series.shift(1).rolling(3, min_periods=3).mean()
    prior3 = minutes_series.shift(3).rolling(3, min_periods=3).mean()
    diff = last3 - prior3
    trend = pd.Series(index=minutes_series.index, dtype="object")
    trend[diff > 30] = "rising"
    trend[diff < -30] = "falling"
    trend[diff.abs() <= 30] = "stable"
    trend[last3.isna() | prior3.isna()] = None
    return trend


def build_player_gameweek_state(spine: pd.DataFrame) -> pd.DataFrame:
    """Derive analytical state variables from the player GW spine.

    Grain: (player_id, gw) unique on exit — same as input spine.
    """
    _validate_spine_entry_contract(spine)

    # Step 1 — sort
    df = spine.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # Step 2 — rolling windows (lag-1: prior GWs only, not including current)
    # NULLs (BGW, pre-transfer) are skipped; rolling computes with available non-NULL values
    # xa excluded: absorbed by xgi (G-EDA6-02). roll8 produced for minutes only (LENS-AVAIL AVAIL-003).
    # Rejected columns (total_points, xg, goals_scored, assists, saves, penalties_saved,
    # bonus, bps) removed per Phase 3 Representation Inventory Lock.
    for col in _ROLL_COLS:
        df[f"{col}_roll3"] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        )
        df[f"{col}_roll5"] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        )
        if col == "minutes":
            df["minutes_roll8"] = (
                df.groupby("player_id")[col]
                .transform(lambda x: x.shift(1).rolling(8, min_periods=1).mean())
            )

    # Step 3 — fixture_context: three-way label (BGW rows were previously mapped to "SGW")
    df["fixture_context"] = np.select(
        [df["is_bgw"], df["is_dgw"]],
        ["BGW", "DGW"],
        default="SGW",
    )

    # Step 4 — minutes_trend (availability domain only — see _AVAILABILITY_DOMAIN_ONLY)
    df["minutes_trend"] = (
        df.groupby("player_id")["minutes"]
        .transform(_compute_minutes_trend)
    )

    # Step 5 — governance assertion: derived columns must exactly equal _GOVERNED_ROLLING_COLS
    _produced = set(df.columns) - set(spine.columns)
    if _produced != _GOVERNED_ROLLING_COLS:
        _extra = _produced - _GOVERNED_ROLLING_COLS
        _missing = _GOVERNED_ROLLING_COLS - _produced
        raise RuntimeError(
            f"build_player_gameweek_state: STATE column set diverged from governed set.\n"
            f"Extra (unapproved): {sorted(_extra)}\n"
            f"Missing (approved but absent): {sorted(_missing)}"
        )

    # Step 6 — assert grain
    validate_grain_uniqueness(df, "player_gameweek_state")

    return df
