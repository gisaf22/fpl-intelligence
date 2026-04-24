from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


# ─── Enums ───────────────────────────────────────────────────────────────────

class AnalystStatus(str, Enum):
    complete = "complete"
    partial  = "partial"
    failed   = "failed"


class GwType(str, Enum):
    normal = "normal"
    dgw    = "dgw"
    bgw    = "bgw"


class SignalStatus(str, Enum):
    complete = "complete"
    degraded = "degraded"
    absent   = "absent"


class DataCeiling(str, Enum):
    outcome_only    = "outcome_only"
    fpl_xg_estimate = "fpl_xg_estimate"
    process_quality = "process_quality"


class Position(str, Enum):
    GK  = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


# ─── BriefingMeta ─────────────────────────────────────────────────────────────

class BriefingMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw:             int
    generated_at:   datetime
    schema_version: str
    config_version: str
    prompt_version: str
    data_sources:   List[str]
    analyst_status: AnalystStatus

    @field_validator("gw")
    @classmethod
    def gw_in_range(cls, v: int) -> int:
        if not (1 <= v <= 38):
            raise ValueError("gw must be between 1 and 38")
        return v

    @field_validator("schema_version")
    @classmethod
    def schema_version_pattern(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+$", v):
            raise ValueError(r"schema_version must match pattern \d+\.\d+")
        return v

    @field_validator("data_sources")
    @classmethod
    def data_sources_non_empty(cls, v: List[str]) -> List[str]:
        if len(v) < 1:
            raise ValueError("data_sources must have at least one entry")
        return v


# ─── BriefingContext ──────────────────────────────────────────────────────────

class BriefingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gw:            int
    gw_type:       GwType
    double_teams:  List[int]
    blank_teams:   List[int]
    deadline_time: Optional[datetime] = None

    @field_validator("gw")
    @classmethod
    def gw_in_range(cls, v: int) -> int:
        if not (1 <= v <= 38):
            raise ValueError("gw must be between 1 and 38")
        return v


# ─── Signal item sub-models ───────────────────────────────────────────────────

class SignalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id:     int
    entity_name:   str
    team_id:       Optional[int] = None
    position:      Optional[Position] = None
    value:         float
    direction:     Optional[str] = None
    components:    Dict[str, float]
    context_flags: Dict[str, Any]
    data_ceiling:  DataCeiling

    @model_validator(mode="after")
    def check_context_weight_applied(self) -> "SignalItem":
        if "context_weight_applied" not in self.context_flags:
            raise ValueError(
                "context_flags.context_weight_applied: context_weight_applied is required in context_flags"
            )
        return self


class SignalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SignalStatus
    reason: Optional[str] = None
    items:  Optional[List[SignalItem]] = None

    @model_validator(mode="after")
    def check_status_fields(self) -> "SignalOutput":
        if self.status == SignalStatus.degraded:
            if self.reason is None:
                raise ValueError(
                    "reason: reason is required when status is degraded"
                )
            if self.items is None:
                raise ValueError(
                    "items: items must be present as empty list when status is degraded"
                )
        elif self.status == SignalStatus.absent:
            if self.reason is None:
                raise ValueError(
                    "reason: reason is required when status is absent"
                )
        elif self.status == SignalStatus.complete:
            if self.items is None:
                raise ValueError(
                    "items: items is required when status is complete"
                )
        return self


# OVR has a signal-specific output shape: undervalued and overvalued replace the
# generic items list. All other signals continue to use SignalOutput with items.
class OvrSignalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status:     SignalStatus
    reason:     Optional[str] = None
    undervalued: Optional[List[SignalItem]] = None
    overvalued:  Optional[List[SignalItem]] = None

    @model_validator(mode="after")
    def check_status_fields(self) -> "OvrSignalOutput":
        if self.status == SignalStatus.degraded:
            if self.reason is None:
                raise ValueError(
                    "reason: reason is required when status is degraded"
                )
            if self.undervalued is None:
                raise ValueError(
                    "undervalued: undervalued must be present as empty list when status is degraded"
                )
        elif self.status == SignalStatus.absent:
            if self.reason is None:
                raise ValueError(
                    "reason: reason is required when status is absent"
                )
        elif self.status == SignalStatus.complete:
            if self.undervalued is None:
                raise ValueError(
                    "undervalued: undervalued is required when status is complete"
                )
            if self.overvalued is None:
                raise ValueError(
                    "overvalued: overvalued is required when status is complete"
                )
        return self


# ─── MinutesFilter ────────────────────────────────────────────────────────────

class MinutesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nailed_count:   int
    rotation_count: int
    doubt_count:    int
    status:         SignalStatus

    @field_validator("nailed_count", "rotation_count", "doubt_count")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


# ─── Signals ──────────────────────────────────────────────────────────────────

class Signals(BaseModel):
    model_config = ConfigDict(extra="allow")

    minutes_filter: MinutesFilter

    @model_validator(mode="before")
    @classmethod
    def validate_signal_outputs(cls, data: Any) -> Any:
        # Validate every non-minutes_filter key as a SignalOutput, except
        # ownership_vs_returns which uses OvrSignalOutput (signal-specific shape).
        # Unknown signal keys are accepted (forward compatibility) but must
        # still satisfy the signal_output contract if present.
        if not isinstance(data, dict):
            return data
        for key, value in data.items():
            if key == "minutes_filter":
                continue
            validator = OvrSignalOutput if key == "ownership_vs_returns" else SignalOutput
            try:
                validator.model_validate(value)
            except ValidationError as exc:
                first_err = exc.errors()[0]
                raw_msg = first_err["msg"].removeprefix("Value error, ")
                # Error messages from validators carry a
                # "field_name: description" prefix to enable path reconstruction.
                if ":" in raw_msg:
                    field_name, description = raw_msg.split(":", 1)
                    raise ValueError(
                        f"signals.{key}.{field_name.strip()}: {description.strip()}"
                    ) from None
                raise ValueError(f"signals.{key}: {raw_msg}") from None
        return data


# ─── Briefing (root) ──────────────────────────────────────────────────────────

class Briefing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta:    BriefingMeta
    context: BriefingContext
    signals: Signals

    @model_validator(mode="after")
    def check_gw_match(self) -> "Briefing":
        if self.meta.gw != self.context.gw:
            raise ValueError(
                f"meta.gw / context.gw: meta.gw ({self.meta.gw}) must equal "
                f"context.gw ({self.context.gw})"
            )
        return self
