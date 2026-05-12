from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.source.player_histories import fetch_player_histories_raw


def stage_player_histories(db_path: Path) -> pd.DataFrame:
    histories = (
        fetch_player_histories_raw(db_path)
        .copy()[
            [
                "element_id",
                "round",
                "fixture",
                "minutes",
                "starts",
                "total_points",
                "opponent_team",
                "was_home",
                "ingested_at",
            ]
        ]
        .rename(
            columns={
                "element_id": "player_id",
                "round": "gameweek",
                "fixture": "fixture_id",
            }
        )
    )
    histories["player_id"] = histories["player_id"].astype("int64")
    histories["gameweek"] = histories["gameweek"].astype("int64")
    histories["fixture_id"] = histories["fixture_id"].astype("int64")
    histories["minutes"] = histories["minutes"].astype("int64")
    histories["starts"] = histories["starts"].astype("int64")
    histories["total_points"] = pd.to_numeric(histories["total_points"])
    histories["opponent_team"] = histories["opponent_team"].astype("int64")
    histories["was_home"] = histories["was_home"].astype("int64")
    return histories
