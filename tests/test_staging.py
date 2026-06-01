"""Tests for pipeline/dal/staging.py — F-DAL-001 and F-DAL-002."""

from __future__ import annotations

import pandas as pd
import pytest

from dal.staging import ColumnMapping, Schema, load_schema, stage
from dal.staging.stg_transformer import (
    _normalize_canonical_columns,
    _rename_source_columns,
    _validate_non_nullable_columns,
)

pytestmark = pytest.mark.unit

ALL_ENTITIES = [
    "element_types",
    "teams",
    "events",
    "fixtures",
    "players",
    "player_histories",
]


# ---------------------------------------------------------------------------
# load_schema — happy path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entity", ALL_ENTITIES)
def test_load_schema_all_entities(entity):
    schema = load_schema(entity)
    assert schema.source_table
    assert len(schema.columns) > 0
    for col in schema.columns:
        assert col.source
        assert col.canonical
        assert col.dtype
        assert isinstance(col.nullable, bool)
        assert col.description


# ---------------------------------------------------------------------------
# load_schema — error cases
# ---------------------------------------------------------------------------


def test_load_schema_unknown_entity_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_schema("nonexistent_entity")


def test_load_schema_missing_source_table(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    schema_yaml = (
        "columns:\n  - source: x\n    canonical: x\n    dtype: int64\n    nullable: false\n    description: x\n"
    )
    bad.write_text(schema_yaml)
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="source_table"):
        load_schema("bad")


def test_load_schema_missing_columns(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text("source_table: foo\n")
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="columns"):
        load_schema("bad")


def test_load_schema_invalid_dtype(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "source_table: foo\n"
        "columns:\n"
        "  - source: x\n"
        "    canonical: x\n"
        "    dtype: badtype\n"
        "    nullable: false\n"
        "    description: x\n"
    )
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="has invalid value"):
        load_schema("bad")


def test_load_schema_missing_required_field(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    # missing 'description'
    bad.write_text(
        "source_table: foo\n"
        "columns:\n"
        "  - source: x\n"
        "    canonical: x\n"
        "    dtype: int64\n"
        "    nullable: false\n"
    )
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="missing required field"):
        load_schema("bad")


def test_load_schema_column_must_be_mapping(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text("source_table: foo\ncolumns:\n  - [not, a, mapping]\n")
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_schema("bad")


def test_load_schema_nullable_must_be_boolean(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "source_table: foo\n"
        "columns:\n"
        "  - source: x\n"
        "    canonical: x\n"
        "    dtype: int64\n"
        "    nullable: 'false'\n"
        "    description: x\n"
    )
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="must be a boolean"):
        load_schema("bad")


def test_load_schema_invalid_transform(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "source_table: foo\n"
        "columns:\n"
        "  - source: x\n"
        "    canonical: x\n"
        "    dtype: int64\n"
        "    nullable: false\n"
        "    description: x\n"
        "    transform: unknown\n"
    )
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="has invalid value"):
        load_schema("bad")


def test_load_schema_invalid_identifier(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "source_table: bad-table\n"
        "columns:\n"
        "  - source: x\n"
        "    canonical: x\n"
        "    dtype: int64\n"
        "    nullable: false\n"
        "    description: x\n"
    )
    import dal.staging.stg_schema as staging_module
    monkeypatch.setattr(staging_module, "SCHEMA_DIR", tmp_path)
    with pytest.raises(ValueError, match="invalid identifier"):
        load_schema("bad")


# ---------------------------------------------------------------------------
# canonical normalization helpers — unit tests with synthetic data
# ---------------------------------------------------------------------------


def _simple_schema(source: str, canonical: str, dtype: str, nullable: bool, transform=None) -> Schema:
    return Schema(
        source_table="dummy",
        columns=[
            ColumnMapping(
                source=source,
                canonical=canonical,
                dtype=dtype,
                nullable=nullable,
                description="test",
                transform=transform,
            )
        ],
    )


def test_rename_source_columns_renames_column():
    df = pd.DataFrame({"src_col": [1, 2, 3]})
    schema = _simple_schema("src_col", "dst_col", "int64", False)
    result = _rename_source_columns(df, schema)
    assert "dst_col" in result.columns
    assert "src_col" not in result.columns


def test_normalize_canonical_columns_casts_dtype():
    df = pd.DataFrame({"val": ["1", "2", "3"]})
    schema = _simple_schema("val", "val", "int64", False)
    renamed = _rename_source_columns(df, schema)
    result = _normalize_canonical_columns(renamed, schema)
    assert result["val"].dtype == "int64"


def test_validate_non_nullable_columns_catches_nullable_violation():
    df = pd.DataFrame({"val": [1, None, 3]})
    schema = _simple_schema("val", "val", "Int64", False)
    with pytest.raises(ValueError, match="non-nullable"):
        renamed = _rename_source_columns(df, schema)
        normalized = _normalize_canonical_columns(renamed, schema)
        _validate_non_nullable_columns(normalized, schema)


def test_validate_non_nullable_columns_nullable_column_allows_nulls():
    df = pd.DataFrame({"val": [1, None, 3]})
    schema = _simple_schema("val", "val", "Int64", True)
    renamed = _rename_source_columns(df, schema)
    result = _normalize_canonical_columns(renamed, schema)
    _validate_non_nullable_columns(result, schema)
    assert result["val"].isna().sum() == 1


def test_normalize_canonical_columns_divide_by_10():
    df = pd.DataFrame({"price": [55, 60, 100]})
    schema = _simple_schema("price", "purchase_price", "float64", False, transform="divide_by_10")
    renamed = _rename_source_columns(df, schema)
    result = _normalize_canonical_columns(renamed, schema)
    assert list(result["purchase_price"]) == [5.5, 6.0, 10.0]


def test_validate_non_nullable_columns_checked_after_parse_datetime():
    df = pd.DataFrame({"team_join_date": ["not-a-date"]})
    schema = _simple_schema(
        "team_join_date",
        "team_join_date",
        "datetime64[ns]",
        False,
        transform="parse_datetime",
    )
    with pytest.raises(ValueError, match="non-nullable"):
        renamed = _rename_source_columns(df, schema)
        normalized = _normalize_canonical_columns(renamed, schema)
        _validate_non_nullable_columns(normalized, schema)


# ---------------------------------------------------------------------------
# stage — fixture DB tests (golden test.db)
# ---------------------------------------------------------------------------


def test_stage_players_returns_canonical_columns(db_path):
    schema = load_schema("players")
    df = stage(db_path, schema)
    assert "player_id" in df.columns
    assert "player_name" in df.columns
    assert "position_code" in df.columns
    assert "team_id" in df.columns
    assert "purchase_price" in df.columns
    assert len(df) > 0


def test_stage_fixtures_returns_canonical_columns(db_path):
    schema = load_schema("fixtures")
    df = stage(db_path, schema)
    assert "fixture_id" in df.columns
    assert "gw" in df.columns
    assert "home_team_id" in df.columns
    assert "away_team_id" in df.columns
    assert "home_team_difficulty" in df.columns
    assert len(df) > 0


def test_stage_player_histories_returns_canonical_columns(db_path):
    schema = load_schema("player_histories")
    df = stage(db_path, schema)
    assert "player_id" in df.columns
    assert "gw" in df.columns
    assert "fixture_id" in df.columns
    assert "purchase_price" in df.columns
    assert len(df) > 0


def test_stage_players_purchase_price_is_float64_divided_by_10(db_path):
    schema = load_schema("players")
    df = stage(db_path, schema)
    assert df["purchase_price"].dtype == "float64"
    assert df["purchase_price"].min() >= 3.0
    assert df["purchase_price"].max() <= 20.0


def test_stage_player_histories_purchase_price_is_float64_divided_by_10(db_path):
    schema = load_schema("player_histories")
    df = stage(db_path, schema)
    assert df["purchase_price"].dtype == "float64"
    assert df["purchase_price"].min() >= 3.0
    assert df["purchase_price"].max() <= 20.0


def test_stage_players_code_present_and_populated(db_path):
    schema = load_schema("players")
    df = stage(db_path, schema)
    assert "code" in df.columns
    assert df["code"].dtype == "int64"
    assert df["code"].notna().all()


def test_stage_players_team_join_date_present_and_datetime(db_path):
    schema = load_schema("players")
    df = stage(db_path, schema)
    assert "team_join_date" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["team_join_date"])
    assert df["team_join_date"].notna().any()


def test_normalize_canonical_columns_parse_datetime_nat_for_null():
    df = pd.DataFrame({"team_join_date": [None, "2022-07-01", None]})
    schema = _simple_schema("team_join_date", "team_join_date", "datetime64[ns]", True, transform="parse_datetime")
    renamed = _rename_source_columns(df, schema)
    result = _normalize_canonical_columns(renamed, schema)
    assert pd.isna(result["team_join_date"].iloc[0])
    assert pd.isna(result["team_join_date"].iloc[2])
    assert result["team_join_date"].iloc[1] == pd.Timestamp("2022-07-01")


def test_normalize_canonical_columns_string_dtype_preserves_nulls():
    df = pd.DataFrame({"news": [None, "fit"]})
    schema = _simple_schema("news", "news", "str", True)
    renamed = _rename_source_columns(df, schema)
    result = _normalize_canonical_columns(renamed, schema)
    assert result["news"].dtype.name == "string"
    assert pd.isna(result["news"].iloc[0])
    assert result["news"].iloc[1] == "fit"
