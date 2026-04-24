from __future__ import annotations

import inspect
import unittest.mock
from datetime import datetime, timezone
from statistics import mean, pstdev

import pytest

from fpl_intelligence.config import OVR_TOP_N
from fpl_intelligence.context import GameweekContext
from fpl_intelligence.datasets import PlayerFeatures
from fpl_intelligence.models.briefing import GwType, SignalStatus
from fpl_intelligence.models.pipeline import (
    FeaturesDataset,
    FilteredPool,
    GwContext,
    MetricsDataset,
    WeightedSignalOutputs,
)
from fpl_intelligence.pipeline.steps import (
    assemble_briefing,
    apply_context_weighting,
    compute_features_batch,
    compute_signals_base,
    robust_zscore,
)
from validation import validate_pipeline_output

_GW = 1
_DEADLINE = datetime(2025, 8, 1, tzinfo=timezone.utc)


def _context(**kwargs) -> GwContext:
    defaults = dict(
        gw=_GW,
        gw_type=GwType.normal,
        double_teams=[],
        blank_teams=[],
        deadline_time=_DEADLINE,
    )
    defaults.update(kwargs)
    return GwContext(**defaults)


def _metrics(records: list[dict]) -> MetricsDataset:
    return MetricsDataset(gw=_GW, records=records)


def _features(records: list[dict]) -> FeaturesDataset:
    return FeaturesDataset(gw=_GW, records=records)


def _pool(nailed: list[int], rotation: list[int] = (), doubt: list[int] = ()) -> FilteredPool:
    return FilteredPool(gw=_GW, nailed=list(nailed), rotation=list(rotation), doubt=list(doubt))


def _gw_contexts(features: FeaturesDataset, ctx: GwContext) -> dict[int, GameweekContext]:
    """Build gw_contexts from features records using double/blank teams from ctx."""
    dgw = set(ctx.double_teams)
    bgw = set(ctx.blank_teams)
    result = {}
    for r in features.records:
        is_dgw = r.team_id in dgw
        is_bgw = r.team_id in bgw
        fc = 2 if is_dgw else (0 if is_bgw else 1)
        result[r.entity_id] = GameweekContext(
            gw=ctx.gw,
            team_id=r.team_id,
            is_dgw=is_dgw,
            is_bgw=is_bgw,
            fixture_count=fc,
            opponent_team_ids=[],
            home_flags=[],
        )
    return result


def _signal_record(entity_id: int, team_id: int, value: float) -> dict:
    """Minimal FeaturesDataset record for signal-layer tests."""
    return {
        "entity_id": entity_id,
        "entity_name": f"Player{entity_id}",
        "team_id": team_id,
        "position": "MID",
        "mispricing_score": value,
        "start_rate": 1.0,
        "returns_z": value,
        "ownership_z": 0.0,
        "points_last_n": 10.0,
        "starts_last_n": 6.0,
        "selected_count_gw": 100.0,
        "is_eligible": True,
    }


# =============================================================================
# TEST 1 — robust_zscore outlier resistance
# =============================================================================

def test_robust_zscore_outlier_resistance():
    # 300 is exactly 10x the largest non-outlier value (30)
    values = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 300.0]
    non_outlier_indices = slice(0, 6)

    robust = robust_zscore(values)
    non_outlier_robust = robust[non_outlier_indices]

    mu = mean(values)
    sigma = pstdev(values)
    mean_z = [(v - mu) / sigma for v in values]
    non_outlier_mean = mean_z[non_outlier_indices]

    robust_spread = pstdev(non_outlier_robust)
    mean_spread = pstdev(non_outlier_mean)

    assert robust_spread > 0.5, (
        f"robust_zscore non-outlier spread should be > 0.5; got {robust_spread:.4f}. "
        "Outlier should not compress the spread of normal values."
    )
    assert mean_spread < 0.2, (
        f"Mean-based z-score non-outlier spread should be < 0.2 (outlier compression); "
        f"got {mean_spread:.4f}."
    )


def test_robust_zscore_called_only_from_returns_and_ownership():
    import fpl_intelligence.pipeline.steps as steps_mod

    features_source = inspect.getsource(steps_mod.compute_features_batch)
    call_count = features_source.count("robust_zscore(")
    assert call_count == 2, (
        f"robust_zscore must be called exactly twice in compute_features_batch "
        f"(returns_z and ownership_z); found {call_count} call(s)."
    )

    for fn_name in ("compute_signals_base", "apply_context_weighting", "assemble_briefing"):
        fn_source = inspect.getsource(getattr(steps_mod, fn_name))
        assert "robust_zscore" not in fn_source, (
            f"robust_zscore must not be called from {fn_name}."
        )


# =============================================================================
# TEST 2 — ownership_z position grouping
# =============================================================================

def test_ownership_z_is_position_grouped():
    # GK group selected: [50, 100, 150] → median=100, so entity_id=2 (selected=100) gets z=0.0
    # MID group selected: [100, 110, 120] → median=110, so entity_id=4 (selected=100) gets z<0
    # Both players have selected_count_gw=100 but different ownership_z due to grouping.
    records = [
        {"entity_id": 1, "entity_name": "GK_A", "team_id": 1, "position": "GK",
         "points_last_n": 10.0, "starts_last_n": 6.0, "selected_count_gw": 50.0},
        {"entity_id": 2, "entity_name": "GK_B", "team_id": 1, "position": "GK",
         "points_last_n": 12.0, "starts_last_n": 6.0, "selected_count_gw": 100.0},
        {"entity_id": 3, "entity_name": "GK_C", "team_id": 1, "position": "GK",
         "points_last_n": 14.0, "starts_last_n": 6.0, "selected_count_gw": 150.0},
        {"entity_id": 4, "entity_name": "MID_A", "team_id": 2, "position": "MID",
         "points_last_n": 10.0, "starts_last_n": 6.0, "selected_count_gw": 100.0},
        {"entity_id": 5, "entity_name": "MID_B", "team_id": 2, "position": "MID",
         "points_last_n": 12.0, "starts_last_n": 6.0, "selected_count_gw": 110.0},
        {"entity_id": 6, "entity_name": "MID_C", "team_id": 2, "position": "MID",
         "points_last_n": 14.0, "starts_last_n": 6.0, "selected_count_gw": 120.0},
    ]

    ctx = _context()
    gwc = {
        r["entity_id"]: GameweekContext(
            gw=ctx.gw, team_id=r["team_id"],
            is_dgw=False, is_bgw=False,
            fixture_count=1, opponent_team_ids=[], home_flags=[],
        )
        for r in records
    }
    features = compute_features_batch(_metrics(records), ctx, gwc)
    by_id = {r.entity_id: r for r in features.records}

    gk_at_100 = by_id[2]   # GK median → z≈0
    mid_at_100 = by_id[4]  # MID low-end → z<0

    assert gk_at_100.ownership_z != mid_at_100.ownership_z, (
        f"GK and MID with identical selected_count_gw=100 must have different ownership_z "
        f"due to position grouping. "
        f"GK z={gk_at_100.ownership_z:.4f}, MID z={mid_at_100.ownership_z:.4f}"
    )

    # GK is at its group median so |z| should be smaller than MID which is below its median
    assert abs(gk_at_100.ownership_z) < abs(mid_at_100.ownership_z), (
        "GK at group median should have smaller |ownership_z| than MID at group low end."
    )


# =============================================================================
# TEST 3 — Top-N slice after weighting
# =============================================================================

def test_top_n_slice_after_weighting():
    DGW_TEAM = 99
    TOP_N = 2

    # 3 undervalued players; DGW player is rank 3 pre-weighting (value=0.7).
    # After DGW_DIVERGENCE_WEIGHT=1.5: 0.7 * 1.5 = 1.05, which beats rank 1 (1.0).
    records = [
        _signal_record(entity_id=1, team_id=1, value=1.0),
        _signal_record(entity_id=2, team_id=2, value=0.8),
        _signal_record(entity_id=3, team_id=DGW_TEAM, value=0.7),
    ]

    ctx = _context(double_teams=[DGW_TEAM])
    features = _features(records)
    pool = _pool(nailed=[1, 2, 3])
    gwc = _gw_contexts(features, ctx)

    with unittest.mock.patch("fpl_intelligence.pipeline.steps.OVR_TOP_N", TOP_N):
        base = compute_signals_base(features.records, pool, ctx, gwc)
        pre_undervalued = base.signals["ownership_vs_returns"]["undervalued"]

        # Pre-weighting list must not yet be truncated
        assert len(pre_undervalued) > TOP_N, (
            f"Pre-weighting undervalued list should exceed OVR_TOP_N={TOP_N}; "
            f"got {len(pre_undervalued)}. Truncation must happen after context weighting."
        )

        weighted = apply_context_weighting(base, ctx, gwc)
        post_undervalued = weighted.signals["ownership_vs_returns"]["undervalued"]

        assert len(post_undervalued) == TOP_N, (
            f"Post-weighting undervalued list must be capped at OVR_TOP_N={TOP_N}; "
            f"got {len(post_undervalued)}."
        )

        post_ids = [i["entity_id"] for i in post_undervalued]
        assert 3 in post_ids, (
            f"DGW player (id=3, pre-weighting rank 3) should enter top-{TOP_N} after "
            f"DGW boost. Post-weighting ids: {post_ids}"
        )

        # Determinism: identical input produces identical output order
        weighted2 = apply_context_weighting(base, ctx, gwc)
        post2_ids = [i["entity_id"] for i in weighted2.signals["ownership_vs_returns"]["undervalued"]]
        assert post_ids == post2_ids, (
            f"Identical inputs must produce identical output order. "
            f"Run 1: {post_ids}, Run 2: {post2_ids}"
        )


def test_equal_post_weighting_values_preserve_input_order():
    TOP_N = 3

    # Players id=1 and id=2 have identical values; neither is DGW so values stay equal.
    # features.records order is [id=1, id=2, id=3], so id=1 must precede id=2 after sort.
    records = [
        _signal_record(entity_id=1, team_id=1, value=1.0),
        _signal_record(entity_id=2, team_id=2, value=1.0),
        _signal_record(entity_id=3, team_id=3, value=0.5),
    ]

    ctx = _context()
    features = _features(records)
    pool = _pool(nailed=[1, 2, 3])
    gwc = _gw_contexts(features, ctx)

    with unittest.mock.patch("fpl_intelligence.pipeline.steps.OVR_TOP_N", TOP_N):
        base = compute_signals_base(features.records, pool, ctx, gwc)
        weighted = apply_context_weighting(base, ctx, gwc)

        post_ids = [i["entity_id"] for i in weighted.signals["ownership_vs_returns"]["undervalued"]]
        idx_1 = post_ids.index(1)
        idx_2 = post_ids.index(2)
        assert idx_1 < idx_2, (
            f"For equal post-weighting values, original input order must be preserved. "
            f"Expected id=1 before id=2 in {post_ids}."
        )


# =============================================================================
# TEST 4 — direction from final value
# =============================================================================

def test_no_direction_key_in_raw_signal_items():
    records = [
        _signal_record(entity_id=1, team_id=1, value=0.5),
        _signal_record(entity_id=2, team_id=2, value=-0.5),
    ]

    ctx = _context()
    features = _features(records)
    pool = _pool(nailed=[1, 2])
    gwc = _gw_contexts(features, ctx)

    base = compute_signals_base(features.records, pool, ctx, gwc)
    ovr = base.signals["ownership_vs_returns"]

    for item in ovr["undervalued"] + ovr["overvalued"]:
        assert "direction" not in item, (
            f"Raw signal item for entity_id={item['entity_id']} must not carry a "
            f"'direction' key before briefing assembly."
        )


def test_direction_derived_from_final_value_in_briefing():
    # Construct WeightedSignalOutputs directly with a player whose final value is
    # positive. direction must be "undervalued" regardless of which list it came from,
    # because direction is derived from the final value in assemble_briefing.
    ctx = _context()

    def _weighted(players_undervalued: list, players_overvalued: list) -> WeightedSignalOutputs:
        return WeightedSignalOutputs(
            gw=_GW,
            signals={
                "minutes_filter": {
                    "nailed_count": 1,
                    "rotation_count": 0,
                    "doubt_count": 0,
                    "status": SignalStatus.complete,
                },
                "ownership_vs_returns": {
                    "status": SignalStatus.complete,
                    "undervalued": players_undervalued,
                    "overvalued": players_overvalued,
                },
            },
        )

    pos_player = {
        "entity_id": 99,
        "entity_name": "Positive",
        "team_id": 1,
        "position": "MID",
        "value": 0.75,
        "components": PlayerFeatures(
            entity_id=99, entity_name="Positive", team_id=1, position="MID",
            points_last_n=10.0, starts_last_n=6.0, selected_count_gw=100.0,
            start_rate=1.0, returns_z=0.5, ownership_z=-0.25, mispricing_score=0.75,
            is_eligible=True,
        ),
        "context_flags": {
            "is_double_team": False,
            "is_blank_team": False,
            "context_weight_applied": False,
        },
    }
    neg_player = {**pos_player, "entity_id": 100, "entity_name": "Negative", "value": -0.3}

    briefing_pos = assemble_briefing(ctx, _weighted([pos_player], []))
    item_pos = briefing_pos.signals.ownership_vs_returns.undervalued[0]
    assert item_pos.direction == "undervalued", (
        f"Player with value={item_pos.value} > 0 must have direction='undervalued'; "
        f"got '{item_pos.direction}'."
    )

    briefing_neg = assemble_briefing(ctx, _weighted([], [neg_player]))
    item_neg = briefing_neg.signals.ownership_vs_returns.overvalued[0]
    assert item_neg.direction == "overvalued", (
        f"Player with value={item_neg.value} <= 0 must have direction='overvalued'; "
        f"got '{item_neg.direction}'."
    )


# =============================================================================
# TEST 5 — SignalStatus consistency
# =============================================================================

def test_signal_statuses_are_enum_not_string():
    records = [_signal_record(entity_id=1, team_id=1, value=0.5)]

    ctx = _context()
    features = _features(records)
    pool = _pool(nailed=[1])
    gwc = _gw_contexts(features, ctx)

    base = compute_signals_base(features.records, pool, ctx, gwc)
    weighted = apply_context_weighting(base, ctx, gwc)
    briefing = assemble_briefing(ctx, weighted)

    mf_status = briefing.signals.minutes_filter.status
    ovr_status = briefing.signals.ownership_vs_returns.status

    assert isinstance(mf_status, SignalStatus), (
        f"minutes_filter.status must be a SignalStatus instance; got {type(mf_status)}."
    )
    assert isinstance(ovr_status, SignalStatus), (
        f"ownership_vs_returns.status must be a SignalStatus instance; got {type(ovr_status)}."
    )

    assert mf_status is SignalStatus.complete, (
        f"minutes_filter.status must be SignalStatus.complete; got {mf_status!r}."
    )
    assert ovr_status is SignalStatus.complete, (
        f"ownership_vs_returns.status must be SignalStatus.complete; got {ovr_status!r}."
    )


def test_raw_string_complete_would_fail_status_checks():
    # SignalStatus is a str-enum so "complete" == SignalStatus.complete by value,
    # but isinstance and identity distinguish a raw string from the enum member.
    raw = "complete"
    enum_val = SignalStatus.complete

    assert raw == enum_val, "Sanity: str-enum equality holds by value."
    assert raw is not enum_val, "Identity must differ between raw str and enum member."
    assert not isinstance(raw, SignalStatus), (
        "A raw string 'complete' must not pass isinstance(x, SignalStatus)."
    )
    assert isinstance(enum_val, SignalStatus)


# =============================================================================
# TEST 6 — Signal invariants: degenerate outputs are detected
# =============================================================================

def _make_ovr_player(entity_id: int, value: float) -> dict:
    return {
        "entity_id": entity_id,
        "entity_name": f"Player{entity_id}",
        "team_id": 1,
        "position": "MID",
        "value": value,
        "components": PlayerFeatures(
            entity_id=entity_id,
            entity_name=f"Player{entity_id}",
            team_id=1,
            position="MID",
            points_last_n=10.0,
            starts_last_n=6.0,
            selected_count_gw=100.0,
            start_rate=1.0,
            returns_z=value,
            ownership_z=0.0,
            mispricing_score=value,
            is_eligible=True,
        ),
        "context_flags": {
            "is_double_team": False,
            "is_blank_team": False,
            "context_weight_applied": False,
        },
    }


def _make_weighted_ovr(undervalued: list, overvalued: list) -> WeightedSignalOutputs:
    return WeightedSignalOutputs(
        gw=_GW,
        signals={
            "minutes_filter": {
                "nailed_count": 1,
                "rotation_count": 0,
                "doubt_count": 0,
                "status": SignalStatus.complete,
            },
            "ownership_vs_returns": {
                "status": SignalStatus.complete,
                "undervalued": undervalued,
                "overvalued": overvalued,
            },
        },
    )


def test_all_positive_values_fails_overvalued_invariant():
    # All signal items have value > 0, so overvalued list is empty.
    # validate_pipeline_output must flag this as a degenerate signal.
    players = [_make_ovr_player(i, float(i)) for i in range(1, 4)]
    ctx = _context()
    briefing = assemble_briefing(ctx, _make_weighted_ovr(undervalued=players, overvalued=[]))

    result = validate_pipeline_output(_features([]), briefing, _GW, {})

    assert not result.passed
    assert any("No overvalued players" in e for e in result.errors), (
        f"Expected 'No overvalued players' error; got errors: {result.errors}"
    )


def test_all_negative_values_fails_undervalued_invariant():
    # All signal items have value <= 0, so undervalued list is empty.
    # validate_pipeline_output must flag this as a degenerate signal.
    players = [_make_ovr_player(i, -float(i)) for i in range(1, 4)]
    ctx = _context()
    briefing = assemble_briefing(ctx, _make_weighted_ovr(undervalued=[], overvalued=players))

    result = validate_pipeline_output(_features([]), briefing, _GW, {})

    assert not result.passed
    assert any("No undervalued players" in e for e in result.errors), (
        f"Expected 'No undervalued players' error; got errors: {result.errors}"
    )
