from __future__ import annotations

import math

from scipy.stats import spearmanr

from fpl_intelligence.eval.ranking import get_top_k
from fpl_intelligence.eval.schema import BinStats


def compute_spearman(
    signal_ranking: list[tuple[int, int]],
    actual_ranking: list[tuple[int, int]],
) -> float | None:
    """Align on entity_id. Compute Spearman on rank values directly.
    Returns None if fewer than 2 common entities.
    Returns 0.0 (not NaN) when all ranks are identical."""
    signal_map = dict(signal_ranking)
    actual_map = dict(actual_ranking)
    common = set(signal_map) & set(actual_map)
    if len(common) < 2:
        return None
    ids = sorted(common)
    x = [signal_map[i] for i in ids]
    y = [actual_map[i] for i in ids]
    if len(set(x)) == 1 or len(set(y)) == 1:
        return 0.0
    result = spearmanr(x, y)
    corr = result.statistic if hasattr(result, "statistic") else result.correlation
    if math.isnan(corr):
        return 0.0
    return round(float(corr), 6)


def compute_precision_at_k(
    signal_ranking: list[tuple[int, int]],
    actual_ranking: list[tuple[int, int]],
    k: int,
) -> float:
    """Precision@k. Uses same effective k (capped at population) for both rankings.
    Returns 0.0 if effective_k == 0."""
    n = min(len(signal_ranking), len(actual_ranking))
    effective_k = min(k, n)
    if effective_k == 0:
        return 0.0
    top_signal = set(get_top_k(signal_ranking, effective_k))
    top_actual = set(get_top_k(actual_ranking, effective_k))
    return len(top_signal & top_actual) / effective_k


def compute_churn_at_k(
    top_k_t: list[int],
    top_k_t1: list[int],
) -> float:
    """churn = 1 - Jaccard(top_k_t, top_k_t1).
    Returns 1.0 if union is empty. Range: 0.0 (identical) to 1.0 (no overlap)."""
    a = set(top_k_t)
    b = set(top_k_t1)
    union = a | b
    if not union:
        return 1.0
    return 1.0 - len(a & b) / len(union)


def compute_calibration_bins(
    scores: list[float],
    actuals: list[float],
    n_bins: int = 10,
    n_min: int = 20,
) -> list[BinStats]:
    """Quantile-based (equal-frequency) binning of signal scores against actual points.
    scores[i] and actuals[i] correspond to the same player.
    Thin bin strategy: exclude bins with sample_count < n_min (not merge).
    Returns empty list if fewer than n_bins players total.
    Note: OVR_TOP_N=20 players with n_bins=10 and n_min=20 always produces empty
    calibration because ~2 players per bin < 20. This is correct behaviour."""
    n = len(scores)
    if n < n_bins:
        return []

    # Sort indices by score ascending for equal-frequency binning
    sorted_indices = sorted(range(n), key=lambda i: scores[i])
    sorted_scores = [scores[i] for i in sorted_indices]
    sorted_actuals = [actuals[i] for i in sorted_indices]

    bin_size = n / n_bins
    result: list[BinStats] = []

    for b in range(n_bins):
        start = int(b * bin_size)
        end = int((b + 1) * bin_size) if b < n_bins - 1 else n
        bin_scores = sorted_scores[start:end]
        bin_actuals = sorted_actuals[start:end]

        count = len(bin_scores)
        if count < n_min:
            continue

        mean_pts = sum(bin_actuals) / count
        variance = sum((x - mean_pts) ** 2 for x in bin_actuals) / count
        std_pts = math.sqrt(variance)

        result.append(
            BinStats(
                bin_lower_bound=bin_scores[0],
                bin_upper_bound=bin_scores[-1],
                sample_count=count,
                mean_next_gw_points=mean_pts,
                std_next_gw_points=std_pts,
            )
        )

    return sorted(result, key=lambda b: b.bin_lower_bound)


def compute_temporal_stability(
    signal_t: list[tuple[int, int]],
    signal_t1: list[tuple[int, int]],
) -> float | None:
    """Spearman on intersection of entity_ids, with dense rankings recomputed
    on the intersection before computing Spearman.
    Returns None if fewer than 3 common entities."""
    t_map = dict(signal_t)
    t1_map = dict(signal_t1)
    common = set(t_map) & set(t1_map)
    if len(common) < 3:
        return None

    ids = sorted(common)

    # Recompute dense rankings on intersection by sorting by original rank
    t_sorted = sorted(ids, key=lambda eid: t_map[eid])
    t1_sorted = sorted(ids, key=lambda eid: t1_map[eid])

    t_ranks = {eid: rank for rank, eid in enumerate(t_sorted, start=1)}
    t1_ranks = {eid: rank for rank, eid in enumerate(t1_sorted, start=1)}

    x = [t_ranks[eid] for eid in ids]
    y = [t1_ranks[eid] for eid in ids]

    if len(set(x)) == 1 or len(set(y)) == 1:
        return 0.0

    result = spearmanr(x, y)
    corr = result.statistic if hasattr(result, "statistic") else result.correlation
    if math.isnan(corr):
        return 0.0
    return round(float(corr), 6)
