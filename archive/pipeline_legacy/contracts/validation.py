from __future__ import annotations

import pandas as pd

from analysis.contracts.schemas import player_gameweek_spine_schema


LIST_COLUMNS = ("fixture_ids", "opponent_team_ids", "was_home_flags")


def _validate_columns(df: pd.DataFrame) -> None:
    expected_columns = list(player_gameweek_spine_schema.keys())
    actual_columns = df.columns.tolist()
    if actual_columns != expected_columns:
        raise ValueError(
            "player_gameweek_spine schema mismatch: "
            f"expected_columns={expected_columns}, actual_columns={actual_columns}"
        )


def _validate_dtypes(df: pd.DataFrame) -> None:
    dtype_mismatches: list[str] = []
    for column, schema in player_gameweek_spine_schema.items():
        if schema.dtype.startswith("list["):
            if str(df[column].dtype) != "object":
                dtype_mismatches.append(
                    f"{column}: expected object backing dtype for {schema.dtype}, "
                    f"actual={df[column].dtype}"
                )
            continue
        actual_dtype = str(df[column].dtype)
        if actual_dtype != schema.dtype:
            dtype_mismatches.append(
                f"{column}: expected={schema.dtype}, actual={actual_dtype}"
            )

    if dtype_mismatches:
        raise TypeError(
            "player_gameweek_spine dtype mismatch: "
            + "; ".join(dtype_mismatches)
        )


def _validate_nullability(df: pd.DataFrame) -> None:
    nullability_failures: list[str] = []
    for column, schema in player_gameweek_spine_schema.items():
        if not schema.nullable:
            null_rows = df.index[df[column].isnull()].tolist()
            if null_rows:
                nullability_failures.append(f"{column}: rows={null_rows}")

    if nullability_failures:
        raise ValueError(
            "player_gameweek_spine nullability violation: "
            + "; ".join(nullability_failures)
        )


def _validate_uniqueness(df: pd.DataFrame) -> None:
    duplicate_rows = df.index[df.duplicated(subset=["player_id", "gameweek"], keep=False)].tolist()
    if duplicate_rows:
        raise ValueError(
            "player_gameweek_spine violates unique (player_id, gameweek) grain: "
            f"rows={duplicate_rows}"
        )


def _validate_list_fields(df: pd.DataFrame) -> None:
    non_list_rows: list[str] = []
    misaligned_rows: list[int] = []

    for row_idx, row in df.loc[:, LIST_COLUMNS].iterrows():
        values = [row[column] for column in LIST_COLUMNS]
        invalid_columns = [
            column for column, value in zip(LIST_COLUMNS, values) if not isinstance(value, list)
        ]
        if invalid_columns:
            non_list_rows.append(f"row={row_idx}, columns={invalid_columns}")
            continue

        lengths = [len(value) for value in values]
        if len(set(lengths)) != 1:
            misaligned_rows.append(row_idx)

    if non_list_rows:
        raise TypeError(
            "player_gameweek_spine list field type violation: "
            + "; ".join(non_list_rows)
        )

    if misaligned_rows:
        raise ValueError(
            "player_gameweek_spine list field length mismatch: "
            f"rows={misaligned_rows}"
        )


def validate_player_gameweek_spine(df: pd.DataFrame) -> None:
    _validate_columns(df)
    _validate_dtypes(df)
    _validate_nullability(df)
    _validate_uniqueness(df)
    _validate_list_fields(df)
