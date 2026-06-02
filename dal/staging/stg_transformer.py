"""Staging transformer — reads a SQLite table through a schema contract and
returns a canonical normalised DataFrame."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

import pandas as pd

from dal.staging.stg_schema import ColumnMapping, Schema

logger = logging.getLogger(__name__)


def stage(db_path: Path, schema: Schema) -> pd.DataFrame:
    """Read one source table from SQLite and return a canonical staged frame."""
    t0 = time.perf_counter()
    query = _build_query(schema)
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)
    staged = _rename_source_columns(df, schema)
    staged = _normalize_canonical_columns(staged, schema)
    _validate_non_nullable_columns(staged, schema)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "[DAL:staging:%s] staged | rows=%d cols=%d elapsed_ms=%.0f",
        schema.source_table,
        len(staged),
        len(staged.columns),
        elapsed_ms,
    )
    return staged


def _build_query(schema: Schema) -> str:
    """Build a SELECT query with quoted identifiers and deterministic ORDER BY.

    ORDER BY uses the schema's declared pk_columns (source column names). Without ORDER BY,
    SQLite row storage order is filesystem-dependent, making staging output non-deterministic.
    """
    source_cols = ", ".join(f'"{col.source}"' for col in schema.columns)
    base_query = f'SELECT {source_cols} FROM "{schema.source_table}"'
    if schema.pk_columns:
        order_clause = ", ".join(f'"{pk}"' for pk in schema.pk_columns)
        return f"{base_query} ORDER BY {order_clause}"
    return base_query


def _rename_source_columns(df: pd.DataFrame, schema: Schema) -> pd.DataFrame:
    """Rename source column names to their canonical equivalents."""
    return df.rename(columns={col.source: col.canonical for col in schema.columns})


def _normalize_canonical_columns(df: pd.DataFrame, schema: Schema) -> pd.DataFrame:
    """Apply transform and dtype cast to every canonical column in place."""
    staged = df.copy()
    for column in schema.columns:
        staged[column.canonical] = _cast_column_dtype(_apply_column_transform(staged[column.canonical], column), column)
    return staged


def _apply_column_transform(series: pd.Series, column: ColumnMapping) -> pd.Series:
    """Apply the column's pre-cast transform, or return the series unchanged if none."""
    if column.transform is None:
        return series
    if column.transform == "divide_by_10":
        return series / 10.0
    if column.transform == "parse_datetime":
        # errors="coerce" turns unparseable values into NaT — caught downstream by nullable check
        return pd.to_datetime(series, errors="coerce")
    # Schema validation should prevent reaching here
    raise ValueError(f"Unsupported transform '{column.transform}' for column '{column.canonical}'")


def _cast_column_dtype(series: pd.Series, column: ColumnMapping) -> pd.Series:
    """Cast series to the schema-declared dtype. 'str' uses pandas StringDtype to preserve pd.NA."""
    target_dtype = column.dtype
    try:
        if target_dtype == "str":
            return series.astype("string").where(series.notna(), other=pd.NA)
        if target_dtype in {"Int64", "Float64"}:
            return series.astype(target_dtype)
        if target_dtype == "datetime64[ns]":
            return pd.to_datetime(series, errors="coerce")
        return series.astype(target_dtype)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Failed to cast column '{column.canonical}' to dtype '{target_dtype}': {exc}") from exc


def _validate_non_nullable_columns(df: pd.DataFrame, schema: Schema) -> None:
    """Raise if any non-nullable column contains null values after staging."""
    for column in schema.columns:
        if column.nullable:
            continue
        null_count = int(df[column.canonical].isna().sum())
        if null_count:
            raise ValueError(
                f"Column '{column.canonical}' is declared non-nullable but contains {null_count} null value(s)"
            )
