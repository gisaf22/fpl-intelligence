from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from fpl_intelligence.datasets import PlayerFeatures, PlayerMetrics
from fpl_intelligence.models.briefing import AnalystStatus, GwType


class GwContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    gw_type: GwType
    double_teams: list[int]
    blank_teams: list[int]
    deadline_time: Optional[datetime] = None


class MetricsDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    records: list[PlayerMetrics]


class FeaturesDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    records: list[PlayerFeatures]


class FilteredPool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    nailed: list[int]
    rotation: list[int]
    doubt: list[int]


class BaseSignalOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    signals: dict[str, Any]


class WeightedSignalOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    signals: dict[str, Any]


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw: int
    status: str
    analyst_status: AnalystStatus
    steps_completed: list[str]
    failures: list[dict[str, str]]
