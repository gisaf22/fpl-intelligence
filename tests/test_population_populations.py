"""Regression guards for population/populations.py."""

import pandas as pd
import pytest

from domain.fpl_scoring import APPEARANCE_MIN_MINUTES, CLEAN_SHEET_MIN_MINUTES
from population.populations import filter_participation, filter_performance


def _make_df(minutes_values: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"minutes": minutes_values, "x": range(len(minutes_values))})


def test_filter_performance_keeps_at_threshold():
    df = _make_df([0, 30, 59, 60, 61, 90])
    result = filter_performance(df)
    assert set(result["minutes"].tolist()) == {60, 61, 90}


def test_filter_performance_excludes_below_threshold():
    df = _make_df([0, 59])
    result = filter_performance(df)
    assert result.empty


def test_filter_participation_keeps_at_threshold():
    df = _make_df([0, 1, 2, 59, 60])
    result = filter_participation(df)
    assert set(result["minutes"].tolist()) == {1, 2, 59, 60}


def test_filter_participation_excludes_zero_minutes():
    df = _make_df([0, 0])
    result = filter_participation(df)
    assert result.empty


def test_filter_performance_threshold_equals_clean_sheet_min():
    df = _make_df([CLEAN_SHEET_MIN_MINUTES - 1, CLEAN_SHEET_MIN_MINUTES])
    result = filter_performance(df)
    assert len(result) == 1
    assert result["minutes"].iloc[0] == CLEAN_SHEET_MIN_MINUTES


def test_filter_participation_threshold_equals_appearance_min():
    df = _make_df([APPEARANCE_MIN_MINUTES - 1, APPEARANCE_MIN_MINUTES])
    result = filter_participation(df)
    assert len(result) == 1
    assert result["minutes"].iloc[0] == APPEARANCE_MIN_MINUTES


def test_both_return_copies():
    df = _make_df([60, 90])
    perf = filter_performance(df)
    part = filter_participation(df)
    perf["minutes"] = 0
    part["minutes"] = 0
    assert df["minutes"].tolist() == [60, 90]


def test_performance_subset_of_participation():
    df = _make_df(list(range(0, 100, 10)))
    perf = set(filter_performance(df)["minutes"].tolist())
    part = set(filter_participation(df)["minutes"].tolist())
    assert perf.issubset(part)
