from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from validation import validate_pipeline_output

from fpl_intelligence.context import build_gameweek_context
from fpl_intelligence.models.briefing import GwType
from fpl_intelligence.pipeline.steps import (
    apply_context_weighting,
    apply_minutes_filter,
    assemble_briefing,
    compute_features_batch,
    compute_metrics_batch,
    compute_signals_base,
    generate_editorial_brief,
    load_gw_context,
    log_run,
    validate_data_freshness,
)
from fpl_intelligence.models.pipeline import RunResult

__all__ = [
    "apply_context_weighting",
    "apply_minutes_filter",
    "assemble_briefing",
    "compute_features_batch",
    "compute_metrics_batch",
    "compute_signals_base",
    "generate_editorial_brief",
    "load_gw_context",
    "log_run",
    "run_gw",
    "validate_data_freshness",
]


def run_gw(
    gw: int,
    db_path: Path,
    output_dir: Path,
    log_path: Path,
) -> RunResult:
    """
    Executes all eleven steps in order for a single GW snapshot.
    Idempotent — same inputs always produce same briefing.json.
    Handles grade 1, 2, and 3 output conditions.
    Returns RunResult describing what happened.
    """
    steps_completed: list[str] = []

    db_path = Path(os.path.expanduser(str(db_path)))

    # Validate required tables before any query — fail fast with clear message.
    _required = {"players", "fixtures", "player_histories"}
    with sqlite3.connect(str(db_path)) as _chk:
        _existing = {row[0] for row in _chk.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    _missing = _required - _existing
    if _missing:
        raise RuntimeError(f"Missing required tables: {', '.join(sorted(_missing))}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    validate_data_freshness(conn, gw)
    steps_completed.append("validate_data_freshness")

    # Build per-player gameweek context from DB — first step after validation.
    # double_teams, blank_teams, and gw_type are derived from gw_contexts so
    # there is exactly one source of truth for DGW/BGW classification.
    gw_contexts = build_gameweek_context(conn, gw)
    conn.close()

    assert len(gw_contexts) > 0, f"No player contexts built for GW {gw}; players table may be empty."

    double_teams = sorted({ctx.team_id for ctx in gw_contexts.values() if ctx.is_dgw})
    blank_teams = sorted({ctx.team_id for ctx in gw_contexts.values() if ctx.is_bgw})
    gw_type = (
        GwType.dgw if double_teams else (GwType.bgw if blank_teams else GwType.normal)
    )
    steps_completed.append("build_gameweek_context")

    context = load_gw_context(db_path)
    context = context.model_copy(update={
        "gw": gw,
        "double_teams": double_teams,
        "blank_teams": blank_teams,
        "gw_type": gw_type,
    })
    steps_completed.append("load_gw_context")

    metrics = compute_metrics_batch(db_path, context)
    steps_completed.append("compute_metrics_batch")

    features = compute_features_batch(metrics, context, gw_contexts)
    steps_completed.append("compute_features_batch")

    pool = apply_minutes_filter(features, context)
    steps_completed.append("apply_minutes_filter")

    base_outputs = compute_signals_base(features.records, pool, context, gw_contexts)
    steps_completed.append("compute_signals_base")

    weighted_outputs = apply_context_weighting(base_outputs, context, gw_contexts)
    steps_completed.append("apply_context_weighting")

    briefing = assemble_briefing(context, weighted_outputs)
    steps_completed.append("assemble_briefing")

    # replaced by validate_pipeline_output() — see validation.py
    result = validate_pipeline_output(features, briefing, gw, gw_contexts)

    for w in result.warnings:
        print(f"[WARN] {w}")

    if not result.passed:
        for e in result.errors:
            print(f"[ERROR] {e}")
        raise RuntimeError(f"Pipeline validation failed for GW {gw}")
    steps_completed.append("validate_briefing")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"gw_{gw}_briefing.json"

    if hasattr(briefing, "model_dump"):
        payload = briefing.model_dump(mode="json")
    else:
        payload = briefing.dict()

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    steps_completed.append("write_briefing")

    return RunResult(
        gw=gw,
        status="complete",
        analyst_status=briefing.meta.analyst_status,
        steps_completed=steps_completed,
        failures=[],
    )
