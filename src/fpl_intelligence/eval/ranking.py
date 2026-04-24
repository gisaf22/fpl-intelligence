from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalRecord:
    entity_id: int
    value: float
    team_id: int | None
    position: str | None


@dataclass
class ActualRecord:
    entity_id: int
    total_points: int
    minutes_played: int
    # minutes_played > 0 is enforced by load_ground_truth; not re-applied here


def build_signal_ranking(
    signals: list[SignalRecord],
) -> list[tuple[int, int]]:
    """Sort by value desc, entity_id asc. Dense ranking with entity_id tiebreak
    making all ranks unique. Rank 1 = highest value."""
    sorted_signals = sorted(signals, key=lambda s: (-s.value, s.entity_id))
    return [(s.entity_id, i + 1) for i, s in enumerate(sorted_signals)]


def build_actual_ranking(
    actuals: list[ActualRecord],
) -> list[tuple[int, int]]:
    """Sort by total_points desc, minutes_played desc, entity_id asc.
    Dense ranking. Rank 1 = highest points."""
    sorted_actuals = sorted(
        actuals, key=lambda a: (-a.total_points, -a.minutes_played, a.entity_id)
    )
    return [(a.entity_id, i + 1) for i, a in enumerate(sorted_actuals)]


def construct_evaluation_set(
    signal_ids: set[int],
    actual_ids: set[int],
) -> set[int]:
    """Returns intersection only. No side effects."""
    return signal_ids & actual_ids


def filter_and_rerank_signals(
    signals: list[SignalRecord],
    evaluation_set: set[int],
) -> list[tuple[int, int]]:
    """Filter to evaluation_set, then recompute ranking on filtered set only.
    Never reuses pre-filter rankings."""
    filtered = [s for s in signals if s.entity_id in evaluation_set]
    return build_signal_ranking(filtered)


def filter_and_rerank_actuals(
    actuals: list[ActualRecord],
    evaluation_set: set[int],
) -> list[tuple[int, int]]:
    """Filter to evaluation_set, then recompute ranking on filtered set only.
    Does NOT re-apply minutes_played > 0 — ActualRecord is clean from load_ground_truth."""
    filtered = [a for a in actuals if a.entity_id in evaluation_set]
    return build_actual_ranking(filtered)


def get_top_k(
    ranking: list[tuple[int, int]],
    k: int,
) -> list[int]:
    """Returns entity_ids of top-k ranked players.
    If population < k: k = population size (spec section 8).
    Returns entity_ids sorted by rank ascending."""
    effective_k = min(k, len(ranking))
    sorted_ranking = sorted(ranking, key=lambda x: x[1])
    return [eid for eid, _ in sorted_ranking[:effective_k]]


def deduplicate_signals(
    signals: list[SignalRecord],
    strategy: str = "max",
) -> list[SignalRecord]:
    """Keep one record per entity_id. Strategy is always 'max': keeps max(value).
    Other strategy values are not supported."""
    best: dict[int, SignalRecord] = {}
    for s in signals:
        if s.entity_id not in best or s.value > best[s.entity_id].value:
            best[s.entity_id] = s
    return list(best.values())
