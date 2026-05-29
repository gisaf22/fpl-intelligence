"""Unit tests for dal/reproducibility.py."""

from __future__ import annotations

import pandas as pd
import pytest

from dal.reproducibility import compute_spine_fingerprint


@pytest.mark.unit
def test_fingerprint_is_deterministic() -> None:
    """Same DataFrame content must produce the same hash on repeated calls."""
    df = pd.DataFrame({"player_id": [1, 2], "gw": [1, 1], "points": [5, 8]})
    fp1 = compute_spine_fingerprint(df)
    fp2 = compute_spine_fingerprint(df)
    assert fp1["sha256"] == fp2["sha256"]


@pytest.mark.unit
def test_fingerprint_differs_on_data_change() -> None:
    """Changing any value must produce a different hash."""
    df1 = pd.DataFrame({"player_id": [1, 2], "gw": [1, 1], "points": [5, 8]})
    df2 = pd.DataFrame({"player_id": [1, 2], "gw": [1, 1], "points": [5, 9]})
    assert compute_spine_fingerprint(df1)["sha256"] != compute_spine_fingerprint(df2)["sha256"]


@pytest.mark.unit
def test_fingerprint_is_column_order_independent() -> None:
    """Same data with different column order must produce the same hash."""
    df1 = pd.DataFrame({"player_id": [1, 2], "gw": [1, 1], "points": [5, 8]})
    df2 = df1[["gw", "points", "player_id"]]
    assert compute_spine_fingerprint(df1)["sha256"] == compute_spine_fingerprint(df2)["sha256"]


@pytest.mark.unit
def test_fingerprint_contains_required_fields() -> None:
    """Output dict must include sha256, n_rows, n_cols, columns, and dtypes."""
    df = pd.DataFrame({"player_id": [1], "gw": [1]})
    fp = compute_spine_fingerprint(df)
    for field in ("sha256", "n_rows", "n_cols", "columns", "dtypes"):
        assert field in fp, f"Missing required fingerprint field: {field!r}"
    assert isinstance(fp["sha256"], str) and len(fp["sha256"]) == 64
    assert fp["n_rows"] == 1
    assert fp["n_cols"] == 2
    assert set(fp["columns"]) == {"player_id", "gw"}
    assert set(fp["dtypes"].keys()) == {"player_id", "gw"}
