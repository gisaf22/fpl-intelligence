"""Tests for integrated DAL base and fixture-context datasets."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from dal.intermediate.int_fixture_context import get_fixture_context
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities, get_staged_fixtures, get_staged_teams
from dal.exceptions import DALContractViolation

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_staged():
    return load_staged_entities(DB_PATH)

_ANALYTICS_REQUIRED_COLS = [
    "player_id",
    "player_name",
    "gw",
    "fixture_id",
    "position_code",
    "position_label",
    "team_id",
    "opponent_team_id",
    "was_home",
    "fixture_difficulty",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "purchase_price",
    "ownership_count",
    "transfers_balance",
]

_FIXTURES_DIFFICULTY_REQUIRED_COLS = [
    "fixture_id",
    "gw",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "home_team_difficulty",
    "away_team_difficulty",
    "home_team_score",
    "away_team_score",
    "finished",
    "home_team_strength_overall",
    "away_team_strength_overall",
    "home_team_strength_attack",
    "away_team_strength_attack",
    "home_team_strength_defence",
    "away_team_strength_defence",
]


def test_get_player_fixture_base_required_cols_present():
    df = get_player_fixture_base(load_staged_entities(DB_PATH))
    for col in _ANALYTICS_REQUIRED_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_get_player_fixture_base_position_label_non_null():
    df = get_player_fixture_base(load_staged_entities(DB_PATH))
    assert df["position_label"].isna().sum() == 0


def test_get_player_fixture_base_fixture_difficulty_int64():
    df = get_player_fixture_base(load_staged_entities(DB_PATH))
    assert str(df["fixture_difficulty"].dtype) in ("int64", "Int64")


def test_get_player_fixture_base_opponent_team_id_non_null():
    df = get_player_fixture_base(load_staged_entities(DB_PATH))
    assert df["opponent_team_id"].isna().sum() == 0


def test_get_player_fixture_base_grain_unique():
    df = get_player_fixture_base(load_staged_entities(DB_PATH))
    assert not df.duplicated(subset=["player_id", "gw", "fixture_id"]).any()


def test_get_player_fixture_base_gw_filter():
    df = get_player_fixture_base(load_staged_entities(DB_PATH), gw=1)
    assert not df.empty
    assert (df["gw"] == 1).all()


def test_get_player_fixture_base_grain_violation_raises(monkeypatch):
    """Injecting a duplicate row triggers DALContractViolation for grain violation."""
    import dal.staging.stg_entities as entities_mod
    from dal.staging.stg_transformer import stage as real_stage

    call_count = {"n": 0}

    def patched_stage(db_path, schema):
        df = real_stage(db_path, schema)
        call_count["n"] += 1
        if schema.source_table == "player_histories":
            df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        return df

    # Patch at the binding that entities.py actually uses
    monkeypatch.setattr(entities_mod, "stage", patched_stage)

    with pytest.raises(DALContractViolation):
        get_player_fixture_base(load_staged_entities(DB_PATH))


def test_get_fixture_context_required_cols_present():
    df = get_fixture_context(get_staged_fixtures(DB_PATH), get_staged_teams(DB_PATH))
    for col in _FIXTURES_DIFFICULTY_REQUIRED_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_get_fixture_context_team_names_non_null():
    df = get_fixture_context(get_staged_fixtures(DB_PATH), get_staged_teams(DB_PATH))
    assert df["home_team_name"].isna().sum() == 0
    assert df["away_team_name"].isna().sum() == 0


def test_get_fixture_context_fixture_id_unique():
    df = get_fixture_context(get_staged_fixtures(DB_PATH), get_staged_teams(DB_PATH))
    assert not df.duplicated(subset=["fixture_id"]).any()


def test_get_fixture_context_gw_filter():
    df = get_fixture_context(get_staged_fixtures(DB_PATH), get_staged_teams(DB_PATH), gw=1)
    assert not df.empty
    assert (df["gw"] == 1).all()


def test_get_fixture_context_grain_violation_raises(monkeypatch):
    """Injecting a duplicate fixture row triggers DALContractViolation for grain violation."""
    import dal.staging.stg_entities as entities_mod
    from dal.staging.stg_transformer import stage as real_stage

    def patched_stage(db_path, schema):
        df = real_stage(db_path, schema)
        if schema.source_table == "fixtures":
            df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        return df

    monkeypatch.setattr(entities_mod, "stage", patched_stage)

    with pytest.raises(DALContractViolation):
        get_fixture_context(get_staged_fixtures(DB_PATH), get_staged_teams(DB_PATH))
