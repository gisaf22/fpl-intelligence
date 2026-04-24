from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path

from fpl_intelligence.config import MIN_EVAL_POOL_SIZE
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
    construct_evaluation_set,
    deduplicate_signals,
    filter_and_rerank_actuals,
    filter_and_rerank_signals,
    get_top_k,
)
from fpl_intelligence.eval.schema import (
    AggregateMetrics,
    EvaluationReport,
    EvaluationWindow,
    GwEvalResult,
)

logger = logging.getLogger(__name__)


def load_signal_items(briefing_path: Path) -> list[SignalRecord]:
    """Load SignalRecords from a briefing JSON.
    Extracts ownership_vs_returns undervalued and overvalued lists.
    Key path: briefing["signals"]["ownership_vs_returns"]["undervalued/overvalued"].
    Raises FileNotFoundError if briefing_path not found.
    Raises KeyError if ownership_vs_returns key absent."""
    if not briefing_path.exists():
        raise FileNotFoundError(f"Briefing not found: {briefing_path}")

    with briefing_path.open(encoding="utf-8") as f:
        briefing = json.load(f)

    ovr = briefing["signals"]["ownership_vs_returns"]
    items = ovr["undervalued"] + ovr["overvalued"]

    records = [
        SignalRecord(
            entity_id=item["entity_id"],
            value=item["value"],
            team_id=item.get("team_id"),
            position=item.get("position"),
        )
        for item in items
    ]
    return deduplicate_signals(records)


def load_ground_truth(gw: int, db_path: Path) -> list[ActualRecord]:
    """Query player_histories for the given GW, filtering minutes > 0.
    Column names confirmed from PRAGMA: element_id, total_points, minutes, round.
    All returned records have minutes_played > 0 by construction."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT element_id, total_points, minutes "
            "FROM player_histories "
            "WHERE round = ? AND minutes > 0",
            (gw,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        ActualRecord(entity_id=row[0], total_points=row[1], minutes_played=row[2])
        for row in rows
    ]


def _null_gw_result(gw: int) -> GwEvalResult:
    return GwEvalResult(
        gw=gw,
        spearman=None,
        precision_at_k={"5": 0.0, "10": 0.0, "20": 0.0},
        churn_at_k=None,
        temporal_stability=None,
        calibration=[],
    )


def run_gw_evaluation(
    gw_t: int,
    briefing_dir: Path,
    db_path: Path,
    prior_signal_ranking: list[tuple[int, int]] | None = None,
) -> GwEvalResult:
    """Implements spec section 6.2 exactly — six steps in order."""
    # Step 1 — Load signal data
    signals = load_signal_items(briefing_dir / f"gw_{gw_t}_briefing.json")

    # Step 2 — Load ground truth (GW t+1); guard against end-of-season
    if gw_t + 1 > 38:
        return _null_gw_result(gw_t)
    actuals = load_ground_truth(gw=gw_t + 1, db_path=db_path)

    # Step 3 — Construct evaluation set
    signal_ids = {s.entity_id for s in signals}
    actual_ids = {a.entity_id for a in actuals}
    evaluation_set = construct_evaluation_set(signal_ids, actual_ids)
    if len(evaluation_set) < 2:
        return GwEvalResult(
            gw=gw_t,
            spearman=None,
            precision_at_k={"5": 0.0, "10": 0.0, "20": 0.0},
            churn_at_k=None,
            temporal_stability=None,
            calibration=[],
        )

    # Step 4 — Apply filtering and produce rankings on evaluation_set
    filtered_signal_ranking = filter_and_rerank_signals(signals, evaluation_set)
    filtered_actual_ranking = filter_and_rerank_actuals(actuals, evaluation_set)

    # Step 5 — Rankings produced in step 4; no pre-filter rankings used.

    # Step 6 — Compute metrics
    spearman = compute_spearman(filtered_signal_ranking, filtered_actual_ranking)

    precision_at_k = {
        str(k): compute_precision_at_k(filtered_signal_ranking, filtered_actual_ranking, k)
        for k in [5, 10, 20]
    }

    if prior_signal_ranking is None:
        churn_at_k = None
    else:
        churn_at_k = {
            str(k): compute_churn_at_k(
                get_top_k(prior_signal_ranking, k),
                get_top_k(filtered_signal_ranking, k),
            )
            for k in [5, 10, 20]
        }

    temporal_stability = (
        None
        if prior_signal_ranking is None
        else compute_temporal_stability(prior_signal_ranking, filtered_signal_ranking)
    )

    # Calibration — map filtered rankings back to raw signal values and actual points
    signal_value_map = {s.entity_id: s.value for s in signals}
    actual_points_map = {a.entity_id: float(a.total_points) for a in actuals}

    scores: list[float] = []
    actuals_raw: list[float] = []
    for entity_id, _ in filtered_signal_ranking:
        scores.append(signal_value_map[entity_id])
        actuals_raw.append(actual_points_map[entity_id])

    calibration = compute_calibration_bins(
        scores, actuals_raw, n_bins=10, n_min=MIN_EVAL_POOL_SIZE
    )

    return GwEvalResult(
        gw=gw_t,
        spearman=spearman,
        precision_at_k=precision_at_k,
        churn_at_k=churn_at_k,
        temporal_stability=temporal_stability,
        calibration=calibration,
    )


def run_backtest(
    gw_start: int,
    gw_end: int,
    briefing_dir: Path,
    db_path: Path,
) -> EvaluationReport:
    """Run evaluation over a GW window.
    GW 38 is clamped: effective_end = min(gw_end, 37) because GW 38 has no t+1.
    Logs a warning for missing briefings and skips that GW."""
    effective_end = min(gw_end, 37)
    if effective_end < gw_start:
        raise ValueError("gw_end must be >= gw_start after clamping")

    gw_results: list[GwEvalResult] = []
    prior_signal_ranking: list[tuple[int, int]] | None = None

    for gw_t in range(gw_start, effective_end + 1):
        briefing_path = briefing_dir / f"gw_{gw_t}_briefing.json"
        if not briefing_path.exists():
            logger.warning("briefing not found for GW %d, skipping", gw_t)
            continue

        result = run_gw_evaluation(gw_t, briefing_dir, db_path, prior_signal_ranking)
        gw_results.append(result)

        # Update prior_signal_ranking for next iteration
        if result.spearman is not None:
            try:
                fresh_signals = load_signal_items(briefing_path)
                fresh_actuals = load_ground_truth(gw_t + 1, db_path)
                eval_set = construct_evaluation_set(
                    {s.entity_id for s in fresh_signals},
                    {a.entity_id for a in fresh_actuals},
                )
                prior_signal_ranking = filter_and_rerank_signals(fresh_signals, eval_set)
            except Exception:
                prior_signal_ranking = None
        else:
            prior_signal_ranking = None

    gw_results = sorted(gw_results, key=lambda r: r.gw)

    # Aggregate over GWs with non-null spearman
    included = [r for r in gw_results if r.spearman is not None]

    if included:
        spearman_vals = [r.spearman for r in included]  # type: ignore[misc]
        mean_spearman: float | None = sum(spearman_vals) / len(spearman_vals)
        variance = sum((x - mean_spearman) ** 2 for x in spearman_vals) / len(spearman_vals)
        spearman_std: float | None = math.sqrt(variance)
    else:
        mean_spearman = None
        spearman_std = None

    churn_gws = [r.churn_at_k for r in included if r.churn_at_k is not None]
    if churn_gws:
        all_churn_vals = [v for cv in churn_gws for v in cv.values()]
        mean_churn: float | None = sum(all_churn_vals) / len(all_churn_vals)
    else:
        mean_churn = None

    ts_vals = [r.temporal_stability for r in included if r.temporal_stability is not None]
    mean_temporal_stability: float | None = (
        sum(ts_vals) / len(ts_vals) if ts_vals else None
    )

    mean_precision_at_k: dict[str, float | None] = {}
    for k_str in ["5", "10", "20"]:
        vals = [r.precision_at_k[k_str] for r in included if k_str in r.precision_at_k]
        mean_precision_at_k[k_str] = sum(vals) / len(vals) if vals else None

    return EvaluationReport(
        window=EvaluationWindow(gw_start=gw_start, gw_end=gw_end),
        per_gw=gw_results,
        aggregate=AggregateMetrics(
            mean_spearman=mean_spearman,
            spearman_std=spearman_std,
            mean_churn=mean_churn,
            mean_temporal_stability=mean_temporal_stability,
            mean_precision_at_k=mean_precision_at_k,
        ),
    )
