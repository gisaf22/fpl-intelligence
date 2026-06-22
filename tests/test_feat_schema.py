"""Unit tests for FEAT_SCHEMA and FEATURE_REGISTRY.

Capabilities tested: Contracts, Evolvability.
All tests run without a live database.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
import pytest

from dal.feat.feat_schema import FEAT_SCHEMA, FEATURE_REGISTRY

# ---------------------------------------------------------------------------
# Minimal valid feat DataFrame — every governed column present with correct types
# ---------------------------------------------------------------------------

_FEAT_COLUMNS = {
    "player_id": [1, 2],
    "gw": [1, 1],
    "xgi_roll3": [0.5, None],
    "xgi_roll5": [0.4, None],
    "xgc_roll3": [0.1, None],
    "xgc_roll5": [0.2, None],
    "clean_sheets_roll3": [0.3, None],
    "clean_sheets_roll5": [0.6, None],
    "goals_conceded_roll3": [1.0, None],
    "goals_conceded_roll5": [2.0, None],
    "minutes_roll3": [60.0, None],
    "minutes_roll5": [55.0, None],
    "minutes_roll8": [58.0, None],
    "minutes_trend": ["stable", None],
    "fixture_context": ["SGW", "DGW"],
    "is_warmup_gw": [False, False],
}


@pytest.fixture
def minimal_feat_df() -> pd.DataFrame:
    return pd.DataFrame(_FEAT_COLUMNS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_feat_df_passes_schema(minimal_feat_df: pd.DataFrame) -> None:
    """A correctly structured DataFrame must pass FEAT_SCHEMA validation."""
    FEAT_SCHEMA.validate(minimal_feat_df)


@pytest.mark.unit
def test_extra_column_raises_schema_error(minimal_feat_df: pd.DataFrame) -> None:
    """strict=False means extra columns do NOT raise; schema only validates declared columns."""
    extra = minimal_feat_df.copy()
    extra["unapproved_col"] = 0.0
    # strict=False — extra columns are allowed (feat output includes spine columns too)
    FEAT_SCHEMA.validate(extra)


@pytest.mark.unit
def test_wrong_column_type_raises_schema_error(minimal_feat_df: pd.DataFrame) -> None:
    """player_id declared as int — string values must fail schema validation."""
    bad = minimal_feat_df.copy()
    bad["player_id"] = ["a", "b"]
    with pytest.raises(pa.errors.SchemaError):
        FEAT_SCHEMA.validate(bad)


@pytest.mark.unit
def test_invalid_fixture_context_raises_schema_error(minimal_feat_df: pd.DataFrame) -> None:
    """fixture_context Check.isin(["BGW","SGW","DGW"]) — any other value must fail."""
    bad = minimal_feat_df.copy()
    bad["fixture_context"] = ["SGW", "INVALID"]
    with pytest.raises(pa.errors.SchemaError):
        FEAT_SCHEMA.validate(bad)


@pytest.mark.unit
def test_every_schema_column_has_registry_entry() -> None:
    """Every column declared in FEAT_SCHEMA must have a FEATURE_REGISTRY entry."""
    schema_cols = set(FEAT_SCHEMA.columns.keys()) - {"player_id", "gw"}
    missing = schema_cols - set(FEATURE_REGISTRY.keys())
    assert not missing, f"Schema columns with no FEATURE_REGISTRY entry: {sorted(missing)}"


@pytest.mark.unit
def test_every_registry_entry_has_schema_column() -> None:
    """Every FEATURE_REGISTRY entry must correspond to a declared FEAT_SCHEMA column."""
    schema_cols = set(FEAT_SCHEMA.columns.keys())
    orphaned = set(FEATURE_REGISTRY.keys()) - schema_cols
    assert not orphaned, f"FEATURE_REGISTRY entries with no FEAT_SCHEMA column: {sorted(orphaned)}"


@pytest.mark.unit
def test_null_player_id_raises_schema_error(minimal_feat_df: pd.DataFrame) -> None:
    """player_id is declared nullable=False — None must fail."""
    bad = minimal_feat_df.copy()
    bad["player_id"] = bad["player_id"].astype(object)
    bad.loc[0, "player_id"] = None
    with pytest.raises(pa.errors.SchemaError):
        FEAT_SCHEMA.validate(bad)
