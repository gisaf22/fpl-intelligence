"""Hardcoded unit tests for the eval module. No db. No files."""
from __future__ import annotations

import pytest

from fpl_intelligence.eval.metrics import (
    compute_calibration_bins,
    compute_churn_at_k,
    compute_precision_at_k,
    compute_spearman,
    compute_temporal_stability,
)
from fpl_intelligence.eval.ranking import (
    ActualRecord,
    SignalRecord,
    build_actual_ranking,
    build_signal_ranking,
    construct_evaluation_set,
    deduplicate_signals,
    filter_and_rerank_signals,
    get_top_k,
)
from fpl_intelligence.eval.schema import (
    BinStats,
    EvaluationReport,
    EvaluationWindow,
    AggregateMetrics,
    GwEvalResult,
)


# ─── Ranking tests ────────────────────────────────────────────────────────────

def test_signal_ranking_order():
    signals = [
        SignalRecord(entity_id=1, value=1.5, team_id=None, position=None),
        SignalRecord(entity_id=2, value=3.0, team_id=None, position=None),
        SignalRecord(entity_id=3, value=0.5, team_id=None, position=None),
    ]
    ranking = dict(build_signal_ranking(signals))
    assert ranking[2] == 1


def test_signal_ranking_tiebreak():
    signals = [
        SignalRecord(entity_id=10, value=1.0, team_id=None, position=None),
        SignalRecord(entity_id=5, value=1.0, team_id=None, position=None),
    ]
    ranking = dict(build_signal_ranking(signals))
    assert ranking[5] == 1
    assert ranking[10] == 2


def test_actual_ranking_order():
    actuals = [
        ActualRecord(entity_id=1, total_points=8, minutes_played=90),
        ActualRecord(entity_id=2, total_points=12, minutes_played=90),
        ActualRecord(entity_id=3, total_points=6, minutes_played=90),
    ]
    ranking = dict(build_actual_ranking(actuals))
    assert ranking[2] == 1


def test_actual_ranking_tiebreak_minutes():
    actuals = [
        ActualRecord(entity_id=1, total_points=6, minutes_played=60),
        ActualRecord(entity_id=2, total_points=6, minutes_played=90),
    ]
    ranking = dict(build_actual_ranking(actuals))
    assert ranking[2] == 1


def test_evaluation_set_intersection():
    result = construct_evaluation_set({1, 2, 3, 4}, {3, 4, 5, 6})
    assert result == {3, 4}


def test_top_k_population_cap():
    ranking = [(1, 1), (2, 2), (3, 3)]
    result = get_top_k(ranking, k=5)
    assert len(result) == 3
    assert set(result) == {1, 2, 3}


def test_deduplicate_keeps_max():
    signals = [
        SignalRecord(entity_id=1, value=2.0, team_id=None, position=None),
        SignalRecord(entity_id=1, value=5.0, team_id=None, position=None),
    ]
    result = deduplicate_signals(signals)
    assert len(result) == 1
    assert result[0].value == 5.0


def test_filter_and_rerank_signals_excludes_absent():
    signals = [
        SignalRecord(entity_id=1, value=4.0, team_id=None, position=None),
        SignalRecord(entity_id=2, value=3.0, team_id=None, position=None),
        SignalRecord(entity_id=3, value=2.0, team_id=None, position=None),
        SignalRecord(entity_id=4, value=1.0, team_id=None, position=None),
    ]
    ranking = filter_and_rerank_signals(signals, evaluation_set={1, 3})
    assert len(ranking) == 2
    ranks = {eid: r for eid, r in ranking}
    assert set(ranks.values()) == {1, 2}


# ─── Metrics tests ────────────────────────────────────────────────────────────

def test_spearman_perfect_agreement():
    signal = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    actual = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    assert compute_spearman(signal, actual) == 1.0


def test_spearman_perfect_disagreement():
    signal = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    actual = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]
    assert compute_spearman(signal, actual) == -1.0


def test_spearman_insufficient_data():
    signal = [(1, 1)]
    actual = [(1, 1)]
    assert compute_spearman(signal, actual) is None


def test_spearman_identical_ranks():
    # All signal ranks identical → return 0.0 not NaN
    signal = [(1, 1), (2, 1), (3, 1)]
    actual = [(1, 1), (2, 2), (3, 3)]
    result = compute_spearman(signal, actual)
    assert result == 0.0


def test_precision_perfect():
    signal = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    actual = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    assert compute_precision_at_k(signal, actual, k=5) == 1.0


def test_precision_zero():
    signal = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    actual = [(6, 1), (7, 2), (8, 3), (9, 4), (10, 5)]
    assert compute_precision_at_k(signal, actual, k=5) == 0.0


def test_precision_population_cap_end_to_end():
    # Only 3 players total, k=5 — effective k capped at 3
    signal = [(1, 1), (2, 2), (3, 3)]
    actual = [(1, 1), (2, 2), (3, 3)]
    # effective_k = min(5, 3) = 3; all 3 match → precision = 1.0
    result = compute_precision_at_k(signal, actual, k=5)
    assert result == 1.0


def test_churn_identical():
    assert compute_churn_at_k([1, 2, 3], [1, 2, 3]) == 0.0


def test_churn_complete():
    assert compute_churn_at_k([1, 2, 3], [4, 5, 6]) == 1.0


def test_churn_partial():
    top_k_t = [1, 2, 3, 4]
    top_k_t1 = [3, 4, 5, 6]
    # intersection = {3, 4}, union = {1,2,3,4,5,6}
    # Jaccard = 2/6; churn = 1 - 2/6 ≈ 0.667
    result = compute_churn_at_k(top_k_t, top_k_t1)
    assert round(result, 3) == 0.667


def test_churn_population_cap_end_to_end():
    # 3 players, k=5 → effective k = 3 via get_top_k; churn computed over 3 players
    ranking = [(1, 1), (2, 2), (3, 3)]
    top_prior = get_top_k(ranking, k=5)
    top_current = get_top_k(ranking, k=5)
    assert len(top_prior) == 3
    result = compute_churn_at_k(top_prior, top_current)
    assert result == 0.0  # identical lists


def test_calibration_bins_count():
    scores = [float(i) for i in range(100)]
    actuals = [float(i) for i in range(100)]
    bins = compute_calibration_bins(scores, actuals, n_bins=10, n_min=5)
    assert len(bins) == 10


def test_calibration_bins_mutual_exclusivity():
    scores = [float(i) for i in range(100)]
    actuals = [float(i) for i in range(100)]
    bins = compute_calibration_bins(scores, actuals, n_bins=10, n_min=1)
    # All 100 players assigned to exactly one bin
    assert sum(b.sample_count for b in bins) == 100
    assert len(bins) == 10


def test_calibration_bins_excluded_thin():
    scores = [float(i) for i in range(15)]
    actuals = [float(i) for i in range(15)]
    bins = compute_calibration_bins(scores, actuals, n_bins=10, n_min=5)
    assert len(bins) < 10


def test_calibration_empty_input():
    bins = compute_calibration_bins([], [], n_bins=10, n_min=5)
    assert bins == []


def test_temporal_stability_identical():
    signal = [(1, 1), (2, 2), (3, 3), (4, 4)]
    result = compute_temporal_stability(signal, signal)
    assert result == 1.0


def test_temporal_stability_too_few():
    signal_t = [(1, 1), (2, 2)]
    signal_t1 = [(1, 1), (2, 2)]
    assert compute_temporal_stability(signal_t, signal_t1) is None


# ─── Schema tests ─────────────────────────────────────────────────────────────

def test_evaluation_report_sorted_ascending():
    results = [
        GwEvalResult(
            gw=gw,
            spearman=None,
            precision_at_k={"5": 0.0, "10": 0.0, "20": 0.0},
            churn_at_k=None,
            temporal_stability=None,
            calibration=[],
        )
        for gw in [33, 31, 32]
    ]
    report = EvaluationReport(
        window=EvaluationWindow(gw_start=31, gw_end=33),
        per_gw=results,
        aggregate=AggregateMetrics(
            mean_spearman=None,
            spearman_std=None,
            mean_churn=None,
            mean_temporal_stability=None,
            mean_precision_at_k={"5": None, "10": None, "20": None},
        ),
    )
    assert [r.gw for r in report.per_gw] == [31, 32, 33]


def test_churn_at_k_nullable():
    base = dict(
        gw=32,
        spearman=0.5,
        precision_at_k={"5": 0.4, "10": 0.3, "20": 0.2},
        temporal_stability=None,
        calibration=[],
    )
    r1 = GwEvalResult(**base, churn_at_k=None)
    assert r1.churn_at_k is None

    r2 = GwEvalResult(**base, churn_at_k={"5": 0.5, "10": 0.4, "20": 0.3})
    assert r2.churn_at_k["5"] == 0.5


def test_bin_stats_all_fields():
    b = BinStats(
        bin_lower_bound=0.0,
        bin_upper_bound=1.0,
        sample_count=25,
        mean_next_gw_points=4.5,
        std_next_gw_points=1.2,
    )
    assert b.bin_lower_bound == 0.0
    assert b.bin_upper_bound == 1.0
    assert b.sample_count == 25
    assert b.mean_next_gw_points == 4.5
    assert b.std_next_gw_points == 1.2
