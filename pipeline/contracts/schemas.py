from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSchema:
    dtype: str
    nullable: bool


player_gameweek_spine_schema: dict[str, ColumnSchema] = {
    "player_id": ColumnSchema(dtype="int64", nullable=False),
    "gameweek": ColumnSchema(dtype="int64", nullable=False),
    "player_name": ColumnSchema(dtype="object", nullable=True),
    "element_type": ColumnSchema(dtype="int64", nullable=True),
    "team_id": ColumnSchema(dtype="int64", nullable=True),
    "minutes": ColumnSchema(dtype="int64", nullable=True),
    "starts": ColumnSchema(dtype="int64", nullable=True),
    "total_points": ColumnSchema(dtype="float64", nullable=True),
    "fixture_ids": ColumnSchema(dtype="list[int64]", nullable=True),
    "opponent_team_ids": ColumnSchema(dtype="list[int64]", nullable=True),
    "was_home_flags": ColumnSchema(dtype="list[int64]", nullable=True),
    "latest_ingested_at": ColumnSchema(dtype="object", nullable=True),
}
