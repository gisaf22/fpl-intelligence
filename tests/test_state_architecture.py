"""STATE architecture tests — governance enforcement.

Verifies that the STATE output column set matches the approved representation set:
1. Rejected column exclusions — xa_roll* and non-minutes roll8 variants are absent.
2. Column count invariant — STATE produces exactly 13 derived columns (Phase 3 lock).
3. FEATURE_REGISTRY coverage — every derived column has a registry entry and vice versa.
4. FEATURE_REGISTRY structure — every entry carries required governance fields.
5. Explicitly rejected columns — all 16 REJECTED-BEHAVIORAL columns are absent.
6. minutes_trend retained — domain-restricted but present.
"""

import pandas as pd
import pytest

from dal.feat.feat_player_gameweek import (
    _ROLL_COLS,
    build_player_gameweek_state,
)
from dal.feat.feat_schema import FEATURE_REGISTRY


# ---------------------------------------------------------------------------
# Shared synthetic spine
# ---------------------------------------------------------------------------

def _make_spine() -> pd.DataFrame:
    rows = []
    for pid in [1, 2, 3]:
        for gw in range(1, 11):
            rows.append({
                "player_id": pid,
                "gw": gw,
                "is_bgw": False,
                "is_dgw": False,
                "fixture_count": 1,
                "total_points": 5,
                "minutes": 60,
                "xg": 0.1,
                "xa": 0.1,
                "xgi": 0.2,
                "xgc": 0.3,
                "goals_scored": 0,
                "assists": 0,
                "clean_sheets": 0,
                "goals_conceded": 1,
                "saves": 0,
                "penalties_saved": 0,
                "bonus": 1,
                "bps": 10,
            })
    df = pd.DataFrame(rows)
    for col in ["total_points", "minutes", "goals_scored", "assists", "clean_sheets",
                "goals_conceded", "saves", "penalties_saved", "bonus", "bps"]:
        df[col] = df[col].astype("Int64")
    for col in ["xg", "xa", "xgi", "xgc"]:
        df[col] = df[col].astype("Float64")
    return df


# ---------------------------------------------------------------------------
# Test 1 — xa_roll* absent (G-EDA6-02: xa absorbed by xgi)
# ---------------------------------------------------------------------------

def test_xa_roll_variants_absent():
    """xa_roll3 and xa_roll5 must not appear in STATE output.

    xa is excluded from _ROLL_COLS (G-EDA6-02 — absorbed by xgi).
    Confirms no regression adds xa back to the roll loop.
    """
    state = build_player_gameweek_state(_make_spine())
    cols = set(state.columns)
    assert "xa_roll3" not in cols, "xa_roll3 present — xa must not produce rolled representations"
    assert "xa_roll5" not in cols, "xa_roll5 present — xa must not produce rolled representations"


# ---------------------------------------------------------------------------
# Test 2 — non-minutes roll8 absent (LENS-AVAIL AVAIL-003: minutes_roll8 only)
# ---------------------------------------------------------------------------

def test_non_minutes_roll8_absent():
    """roll8 variants must not appear for any signal except minutes.

    Only minutes_roll8 is justified (LENS-AVAIL AVAIL-003).
    All other roll8 windows are unjustified or explicitly rejected.
    """
    state = build_player_gameweek_state(_make_spine())
    cols = set(state.columns)

    forbidden_roll8 = [
        f"{'points' if c == 'total_points' else c}_roll8"
        for c in _ROLL_COLS
        if c != "minutes"
    ]
    # xa and xg are not in _ROLL_COLS but were historically candidates — confirm explicitly
    forbidden_roll8 += ["xa_roll8", "xg_roll8"]

    present = [col for col in forbidden_roll8 if col in cols]
    assert not present, f"Forbidden roll8 columns present in STATE output: {present}"


# ---------------------------------------------------------------------------
# Test 3 — derived column count = 13 (Phase 3 Representation Inventory Lock)
# ---------------------------------------------------------------------------

def test_derived_column_count_is_13():
    """STATE must produce exactly 13 derived columns.

    5 approved signals × 2 windows (roll3, roll5) = 10
    + minutes_roll8 + minutes_trend + fixture_context = 13

    Phase 3 lock: 16 REJECTED-BEHAVIORAL columns removed.
    Evidence: docs/archive/state-representation-inventory.md
    """
    spine = _make_spine()
    state = build_player_gameweek_state(spine)
    derived = set(state.columns) - set(spine.columns)
    assert len(derived) == 13, (
        f"Expected 13 derived columns, got {len(derived)}.\n"
        f"Derived columns: {sorted(derived)}"
    )


# ---------------------------------------------------------------------------
# Test 4 — FEATURE_REGISTRY covers every derived column
# ---------------------------------------------------------------------------

def test_feature_registry_covers_all_derived():
    """FEATURE_REGISTRY must have an entry for every column STATE produces."""
    spine = _make_spine()
    state = build_player_gameweek_state(spine)
    derived = set(state.columns) - set(spine.columns)

    missing = derived - set(FEATURE_REGISTRY)
    assert not missing, f"Derived columns without FEATURE_REGISTRY entries: {sorted(missing)}"


# ---------------------------------------------------------------------------
# Test 5 — FEATURE_REGISTRY has no orphan entries
# ---------------------------------------------------------------------------

def test_feature_registry_no_orphan_entries():
    """FEATURE_REGISTRY must not contain entries for columns STATE does not produce."""
    spine = _make_spine()
    state = build_player_gameweek_state(spine)
    derived = set(state.columns) - set(spine.columns)

    orphan = set(FEATURE_REGISTRY) - derived
    assert not orphan, f"FEATURE_REGISTRY entries for columns not in STATE output: {sorted(orphan)}"


# ---------------------------------------------------------------------------
# Test 6 — FEATURE_REGISTRY required governance fields
# ---------------------------------------------------------------------------

def test_feature_registry_required_fields():
    """Every FEATURE_REGISTRY entry must carry non-empty gate, scope, causality, and positions."""
    violations = []
    for col, rec in FEATURE_REGISTRY.items():
        if not rec.gate:
            violations.append(f"  {col}: gate is empty")
        if not rec.scope:
            violations.append(f"  {col}: scope is empty")
        if not rec.causality:
            violations.append(f"  {col}: causality is empty")
        if not rec.positions:
            violations.append(f"  {col}: positions is empty")
    assert not violations, "Field violations in FEATURE_REGISTRY:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Test 7 — 16 REJECTED-BEHAVIORAL columns are individually absent
# ---------------------------------------------------------------------------

_REJECTED_BEHAVIORAL = [
    # Target leakage — component of total_points
    "bonus_roll3", "bonus_roll5",
    # Target leakage — input to bonus allocation
    "bps_roll3", "bps_roll5",
    # Rolling mean destroys burst structure (LENS-FORM FORM-003)
    "goals_scored_roll3", "goals_scored_roll5",
    # No variant clears naive baseline (G-EDA8-07/08/09)
    "assists_roll3", "assists_roll5",
    # Structural zero at outfield; uninformative at GKP (G-EDA8-01/02, G-EDA2-03)
    "saves_roll3", "saves_roll5",
    # 99.7% zero-rate; structural sparsity (G-EDA8-06)
    "penalties_saved_roll3", "penalties_saved_roll5",
    # Absorbed by xgi at FWD/MID; blocked at DEF/GK (G-EDA6-03)
    "xg_roll3", "xg_roll5",
    # Analytically circular (target rolling mean) — LENS-FORM FORM-004/005
    "points_roll3", "points_roll5",
]

def test_rejected_behavioral_columns_absent():
    """All 16 REJECTED-BEHAVIORAL columns must not appear in STATE output.

    Phase 3 Representation Inventory Lock: these columns are permanently removed
    from STATE production. Evidence in docs/archive/state-representation-inventory.md.
    """
    state = build_player_gameweek_state(_make_spine())
    cols = set(state.columns)

    present = [col for col in _REJECTED_BEHAVIORAL if col in cols]
    assert not present, (
        f"REJECTED-BEHAVIORAL columns present in STATE output: {present}\n"
        "These columns were removed by Phase 3 Representation Inventory Lock."
    )


@pytest.mark.parametrize("col", _REJECTED_BEHAVIORAL)
def test_each_rejected_column_individually_absent(col):
    """Each of the 16 REJECTED-BEHAVIORAL columns must be individually absent."""
    state = build_player_gameweek_state(_make_spine())
    assert col not in state.columns, (
        f"Rejected column '{col}' is present in STATE output — "
        "Phase 3 Representation Inventory Lock violation."
    )


# ---------------------------------------------------------------------------
# Test 8 — minutes_trend is present (retained, availability-domain-restricted)
# ---------------------------------------------------------------------------

def test_minutes_trend_present():
    """minutes_trend must be present in STATE output.

    Retained as PROVISIONAL-EDITORIAL with availability domain restriction.
    The 30-minute threshold is annotated STATE-T-01 in the threshold registry.
    """
    state = build_player_gameweek_state(_make_spine())
    assert "minutes_trend" in state.columns, (
        "minutes_trend is absent from STATE output — it was retained with domain restriction "
        "(availability domain only, see _AVAILABILITY_DOMAIN_ONLY)."
    )
