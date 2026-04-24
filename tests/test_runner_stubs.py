from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import get_type_hints

import pytest

from fpl_intelligence.exceptions import (
    BriefingValidationError,
    DataFreshnessError,
    SchemaContractError,
)
from fpl_intelligence.models.briefing import (
    AnalystStatus,
    Briefing,
    BriefingContext,
    BriefingMeta,
    DataCeiling,
    GwType,
    MinutesFilter,
    SignalStatus,
    Signals,
)
from fpl_intelligence.pipeline.runner import run_gw
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
from fpl_intelligence.models.pipeline import (
    BaseSignalOutputs,
    FeaturesDataset,
    FilteredPool,
    GwContext,
    MetricsDataset,
    RunResult,
    WeightedSignalOutputs,
)


def _sample_briefing() -> Briefing:
    return Briefing(
        meta=BriefingMeta(
            gw=1,
            generated_at=datetime(2026, 1, 1, 12, 0, 0),
            schema_version="1.0",
            config_version="1.0",
            prompt_version="1.0",
            data_sources=["fpl.db"],
            analyst_status=AnalystStatus.complete,
        ),
        context=BriefingContext(
            gw=1,
            gw_type=GwType.normal,
            double_teams=[],
            blank_teams=[],
            deadline_time=datetime(2026, 1, 1, 18, 0, 0),
        ),
        signals=Signals(
            minutes_filter=MinutesFilter(
                nailed_count=1,
                rotation_count=0,
                doubt_count=0,
                status=SignalStatus.complete,
            ),
            captaincy={
                "status": "complete",
                "items": [
                    {
                        "entity_id": 1,
                        "entity_name": "Player One",
                        "value": 1.0,
                        "components": {"form": 1.0},
                        "context_flags": {"context_weight_applied": False},
                        "data_ceiling": DataCeiling.outcome_only,
                    }
                ],
            },
        ),
    )


def _sample_context() -> GwContext:
    return GwContext(
        gw=1,
        gw_type=GwType.normal,
        double_teams=[],
        blank_teams=[],
        deadline_time=datetime(2026, 1, 1, 18, 0, 0),
    )


def _sample_metrics() -> MetricsDataset:
    return MetricsDataset(
        gw=1,
        records=[
            {
                "entity_id": 1,
                "entity_name": "Player One",
                "team_id": 1,
                "position": "MID",
                "points_last_n": 10.0,
                "starts_last_n": 4.0,
                "selected_count_gw": 0.5,
            }
        ],
    )


def _sample_features() -> FeaturesDataset:
    return FeaturesDataset(
        gw=1,
        records=[
            {
                "entity_id": 1,
                "entity_name": "Player One",
                "team_id": 1,
                "position": "MID",
                "points_last_n": 10.0,
                "starts_last_n": 4.0,
                "selected_count_gw": 0.5,
                "start_rate": 0.66,
                "returns_z": 0.5,
                "ownership_z": -0.5,
                "mispricing_score": 1.0,
                "is_eligible": True,
            }
        ],
    )


def _sample_pool() -> FilteredPool:
    return FilteredPool(gw=1, nailed=[1], rotation=[], doubt=[])


def _sample_base_outputs() -> BaseSignalOutputs:
    return BaseSignalOutputs(gw=1, signals={"captaincy": {"items": []}})


def _sample_weighted_outputs() -> WeightedSignalOutputs:
    return WeightedSignalOutputs(
        gw=1,
        signals={
            "minutes_filter": {
                "nailed_count": 1,
                "rotation_count": 0,
                "doubt_count": 0,
                "status": "complete",
            },
            "ownership_vs_returns": {"status": "complete", "undervalued": [], "overvalued": []},
        },
    )


def _sample_gw_contexts() -> dict:
    from fpl_intelligence.context import GameweekContext
    return {
        1: GameweekContext(
            gw=1,
            team_id=1,
            is_dgw=False,
            is_bgw=False,
            fixture_count=1,
            opponent_team_ids=[],
            home_flags=[],
        )
    }


def _sample_result() -> RunResult:
    return RunResult(
        gw=1,
        status="complete",
        analyst_status=AnalystStatus.complete,
        steps_completed=[],
        failures=[],
    )


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (compute_metrics_batch, (Path("fpl.db"), _sample_context())),
        (compute_features_batch, (_sample_metrics(), _sample_context(), _sample_gw_contexts())),
        (apply_minutes_filter, (_sample_features(), _sample_context())),
        (compute_signals_base, (_sample_features().records, _sample_pool(), _sample_context(), _sample_gw_contexts())),
        (apply_context_weighting, (_sample_base_outputs(), _sample_context(), _sample_gw_contexts())),
        (assemble_briefing, (_sample_context(), _sample_weighted_outputs())),
    ],
)
def test_pipeline_steps_execute(func, args):
    func(*args)


def test_run_gw_raises_on_missing_tables(tmp_path):
    db_path = tmp_path / "empty.db"
    # sqlite3.connect creates the file; no tables exist in it.
    sqlite3.connect(str(db_path)).close()
    with pytest.raises(RuntimeError, match="Missing required tables"):
        run_gw(1, db_path, tmp_path / "output", tmp_path / "run.log")


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (generate_editorial_brief, (_sample_briefing(), Path("output"))),
        (log_run, (_sample_context(), _sample_result(), Path("run.log"))),
    ],
)
def test_optional_steps_remain_stubs(func, args):
    with pytest.raises(NotImplementedError):
        func(*args)


@pytest.mark.parametrize(
    "func",
    [
        validate_data_freshness,
        load_gw_context,
        compute_metrics_batch,
        compute_features_batch,
        apply_minutes_filter,
        compute_signals_base,
        apply_context_weighting,
        assemble_briefing,
        generate_editorial_brief,
        log_run,
        run_gw,
    ],
)
def test_stubs_have_complete_type_annotations(func):
    hints = get_type_hints(func)
    parameter_count = func.__code__.co_argcount
    parameter_names = func.__code__.co_varnames[:parameter_count]

    for name in parameter_names:
        assert name in hints, f"Missing type annotation for parameter '{name}'"

    assert "return" in hints, "Missing return type annotation"


def test_data_freshness_error_is_exception_subclass():
    assert issubclass(DataFreshnessError, Exception)


def test_briefing_validation_error_is_exception_subclass():
    assert issubclass(BriefingValidationError, Exception)


def test_schema_contract_error_is_exception_subclass():
    assert issubclass(SchemaContractError, Exception)
