from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class FeatureRecord(Protocol):
    """
    Static interface for signal layer consumption.
    Signals MUST only access attributes defined here.
    PlayerFeatures satisfies this structurally.
    """

    entity_id: int
    entity_name: str
    position: str | None
    is_eligible: bool
    mispricing_score: float
    returns_z: float
    ownership_z: float


@dataclass(frozen=True)
class PlayerMetrics:
    entity_id: int
    entity_name: str
    team_id: int
    position: str | None  # None when element_type is not in {1, 2, 3, 4}
    points_last_n: float
    starts_last_n: float
    selected_count_gw: float


@dataclass(frozen=True)
class PlayerFeatures:
    entity_id: int
    entity_name: str
    team_id: int
    position: str | None  # None when element_type is not in {1, 2, 3, 4}
    points_last_n: float
    starts_last_n: float
    selected_count_gw: float
    start_rate: float
    returns_z: float
    ownership_z: float
    mispricing_score: float
    is_eligible: bool  # set by is_player_eligible() in eligibility.py — sole eligibility gate


# removed duplicate type alias — caused ambiguity with Pydantic model
