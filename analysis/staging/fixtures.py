from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.source.fixtures import fetch_fixtures_raw


def stage_fixtures(db_path: Path) -> pd.DataFrame:
    fixtures = fetch_fixtures_raw(db_path).copy()
    fixture_columns = ["id"]
    if "kickoff_time" in fixtures.columns:
        fixture_columns.append("kickoff_time")
    fixtures = fixtures[fixture_columns].rename(columns={"id": "fixture_id"})
    fixtures["fixture_id"] = fixtures["fixture_id"].astype("int64")
    return fixtures
