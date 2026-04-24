from __future__ import annotations

from pydantic import BaseModel, field_validator


class BinStats(BaseModel):
    bin_lower_bound: float
    bin_upper_bound: float
    sample_count: int
    mean_next_gw_points: float
    std_next_gw_points: float


class GwEvalResult(BaseModel):
    gw: int
    spearman: float | None
    precision_at_k: dict[str, float]
    # None for first GW — no prior GW to compare against
    churn_at_k: dict[str, float] | None
    # None for first GW
    temporal_stability: float | None
    # Empty list when population too small — not a bug
    calibration: list[BinStats]


class EvaluationWindow(BaseModel):
    gw_start: int
    gw_end: int


class AggregateMetrics(BaseModel):
    # float | None because single-GW backtest with population below threshold
    # cannot produce non-nullable floats (documented deviation from spec section 12)
    mean_spearman: float | None
    spearman_std: float | None
    mean_churn: float | None
    mean_temporal_stability: float | None
    mean_precision_at_k: dict[str, float | None]


class EvaluationReport(BaseModel):
    window: EvaluationWindow
    per_gw: list[GwEvalResult]
    aggregate: AggregateMetrics

    @field_validator("per_gw")
    @classmethod
    def sort_ascending(cls, v: list[GwEvalResult]) -> list[GwEvalResult]:
        return sorted(v, key=lambda r: r.gw)
