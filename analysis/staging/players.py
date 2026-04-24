from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.source.players import fetch_players_raw


def stage_players(db_path: Path) -> pd.DataFrame:
    players = fetch_players_raw(db_path).copy().rename(
        columns={
            "id": "player_id",
            "web_name": "player_name",
            "team": "team_id",
        }
    )
    players["player_id"] = players["player_id"].astype("int64")
    players["element_type"] = players["element_type"].astype("int64")
    players["team_id"] = players["team_id"].astype("int64")
    return players
