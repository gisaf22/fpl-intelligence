from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.contracts.validation import validate_player_gameweek_spine
from analysis.staging.fixtures import stage_fixtures
from analysis.staging.player_histories import stage_player_histories
from analysis.staging.players import stage_players


FINAL_COLUMNS: list[str] = [
    "player_id",
    "gameweek",
    "player_name",
    "element_type",
    "team_id",
    "minutes",
    "starts",
    "total_points",
    "fixture_ids",
    "opponent_team_ids",
    "was_home_flags",
    "latest_ingested_at",
]


def build_player_gameweek_spine(db_path: Path) -> pd.DataFrame:
    players = stage_players(db_path).copy()[["player_id", "player_name", "element_type", "team_id"]]
    histories = stage_player_histories(db_path).copy()
    fixtures = stage_fixtures(db_path).copy()

    spine_rows = histories.merge(
        players,
        on="player_id",
        how="left",
        validate="many_to_one",
    ).merge(
        fixtures,
        on="fixture_id",
        how="left",
        validate="many_to_one",
    )

    if "kickoff_time" in spine_rows.columns:
        kickoff_ts = pd.to_datetime(spine_rows["kickoff_time"], errors="coerce", utc=True)
        spine_rows = spine_rows.assign(
            _kickoff_missing=kickoff_ts.isna(),
            _kickoff_sort=kickoff_ts,
        )
    else:
        spine_rows = spine_rows.assign(
            _kickoff_missing=True,
            _kickoff_sort=pd.NaT,
        )

    spine_rows = spine_rows.sort_values(
        by=["player_id", "gameweek", "_kickoff_missing", "_kickoff_sort", "fixture_id"],
        kind="stable",
    ).reset_index(drop=True)

    spine = (
        spine_rows.groupby(["player_id", "gameweek"], as_index=False, sort=False)
        .agg(
            player_name=("player_name", "first"),
            element_type=("element_type", "first"),
            team_id=("team_id", "first"),
            minutes=("minutes", "sum"),
            starts=("starts", "sum"),
            total_points=("total_points", "sum"),
            fixture_ids=("fixture_id", list),
            opponent_team_ids=("opponent_team", list),
            was_home_flags=("was_home", list),
            latest_ingested_at=("ingested_at", "max"),
        )
        .loc[:, FINAL_COLUMNS]
        .astype({"total_points": "float64"})
        .reset_index(drop=True)
    )

    validate_player_gameweek_spine(spine)
    return spine
