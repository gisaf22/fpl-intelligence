"""Tests for the prescriptive analytical-mart schema (dal/mart/mart_schema.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from dal.exceptions import DALContractViolation, ErrorCode
from dal.feat.feat_schema import FEATURE_REGISTRY
from dal.mart.mart_analytical import build_prepared_dataset
from dal.mart.mart_schema import validate_mart


def _valid_mart_df() -> pd.DataFrame:
    """A minimal but fully schema-valid mart frame (2 rows, distinct grain)."""
    df = pd.DataFrame(
        {
            "player_id": [1, 2],
            "gw": [3, 3],
            "position": ["GK", "MID"],
            "position_code": [1, 3],
            "team_id": [10, 11],
            "player_name": ["A", "B"],
            "purchase_price": [4.5, 8.0],
            "minutes": pd.array([90, 60], dtype="Int64"),
            "total_points": pd.array([6, 2], dtype="Int64"),
            "is_bgw": pd.array([False, False], dtype="boolean"),
            "is_dgw": pd.array([False, False], dtype="boolean"),
        }
    )
    # Governed signals are required by the schema (derived from FEATURE_REGISTRY).
    for name, rec in FEATURE_REGISTRY.items():
        if name in df.columns:
            continue
        if rec.values:                       # categorical signal (e.g. fixture_context)
            df[name] = rec.values[1]
        elif name == "minutes_trend":        # categorical-ish, nullable, no enum
            df[name] = pd.Series(["stable", "stable"], dtype="object")
        else:                                # numeric rolling signal
            df[name] = pd.array([1.0, 1.0], dtype="Float64")
    return df


def test_valid_mart_passes() -> None:
    validate_mart(_valid_mart_df())  # must not raise


def test_grain_duplicate_rejected() -> None:
    df = _valid_mart_df()
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # (player_id=1, gw=3) twice
    with pytest.raises(DALContractViolation) as exc:
        validate_mart(dup)
    assert exc.value.error_code == ErrorCode.GRAIN_DUPLICATE


def test_position_null_rejected() -> None:
    df = _valid_mart_df()
    df.loc[0, "position"] = None
    with pytest.raises(DALContractViolation):
        validate_mart(df)


def test_position_bad_value_rejected() -> None:
    df = _valid_mart_df()
    df.loc[0, "position"] = "STRIKER"
    with pytest.raises(DALContractViolation):
        validate_mart(df)


def test_missing_signal_rejected() -> None:
    df = _valid_mart_df().drop(columns=["xgi_roll3"])
    with pytest.raises(DALContractViolation) as exc:
        validate_mart(df)
    assert exc.value.error_code == ErrorCode.MISSING_COLUMNS


def test_missing_purchase_price_rejected() -> None:
    df = _valid_mart_df().drop(columns=["purchase_price"])
    with pytest.raises(DALContractViolation):
        validate_mart(df)


def test_purchase_price_null_rejected() -> None:
    df = _valid_mart_df()
    df["purchase_price"] = [None, 8.0]  # introduces a NaN into a non-nullable column
    with pytest.raises(DALContractViolation):
        validate_mart(df)


def test_build_prepared_dataset_validates_by_default() -> None:
    feats = _valid_mart_df().drop(columns=["position"])  # build_prepared_dataset adds it
    out = build_prepared_dataset(feats, data_cutoff_gw=5)
    assert out["position"].tolist() == ["GK", "MID"]


def test_build_prepared_dataset_rejects_unmapped_position_code() -> None:
    feats = _valid_mart_df().drop(columns=["position"])
    feats.loc[0, "position_code"] = 9  # unmapped → position NaN → boundary must reject
    with pytest.raises(DALContractViolation):
        build_prepared_dataset(feats, data_cutoff_gw=5)


def test_build_prepared_dataset_skips_validation_when_disabled() -> None:
    feats = _valid_mart_df().drop(columns=["position", "is_bgw"])  # partial frame
    out = build_prepared_dataset(feats, data_cutoff_gw=5, validate=False)
    assert "position" in out.columns  # no raise despite missing is_bgw
