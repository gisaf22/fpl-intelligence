"""Layer isolation tests — each DAL layer independently testable without the production DB.

Capabilities tested: Testability — full suite runs without ~/.fpl/fpl.db.

fct uses the test fixture DB (tests/fixtures/test.db).
feat and mart use the minimal_spine_df / minimal_feat_df shared fixtures from conftest.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.feat.feat_schema import FEAT_SCHEMA


@pytest.mark.unit
def test_fct_builds_from_fixture_db(db_path) -> None:
    """fct layer builds successfully from the golden test fixture DB (no production DB needed)."""
    from dal.fct.fct_player_gameweek import build_player_gameweek_spine
    from dal.intermediate.int_player_fixture import get_player_fixture_base
    from dal.staging import load_staged_entities

    staged = load_staged_entities(db_path)
    spine = build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)

    assert len(spine) > 0
    assert "player_id" in spine.columns
    assert "gw" in spine.columns
    assert spine.duplicated(subset=["player_id", "gw"]).sum() == 0


@pytest.mark.unit
def test_feat_builds_from_minimal_spine(minimal_spine_df: pd.DataFrame) -> None:
    """feat layer builds all 13 governed columns from a synthetic spine — no DB required."""
    from dal.feat.feat_player_gameweek import build_player_gameweek_state

    feat = build_player_gameweek_state(minimal_spine_df)

    assert len(feat) == len(minimal_spine_df)
    governed = set(FEAT_SCHEMA.columns.keys()) - {"player_id", "gw"}
    missing = governed - set(feat.columns)
    assert not missing, f"Governed columns absent from feat output: {sorted(missing)}"


@pytest.mark.unit
def test_mart_builds_from_minimal_spine(minimal_spine_df: pd.DataFrame) -> None:
    """mart layer builds and adds position string from a synthetic spine — no DB required."""
    from dal.mart.mart_analytical import build_prepared_dataset

    # validate=False: this exercises the position-mapping mechanics on a deliberately
    # partial synthetic frame; the full MART_SCHEMA is covered in test_mart_schema.py.
    mart = build_prepared_dataset(minimal_spine_df, data_cutoff_gw=3, validate=False)

    assert len(mart) == len(minimal_spine_df)
    assert "position" in mart.columns
    assert mart["position"].notna().all()
