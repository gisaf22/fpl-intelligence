"""Comparison helpers for computed registry candidates."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from domain.registry.schema import PRIMARY_KEY_COLUMNS, REQUIRED_COLUMNS

COMPARISON_COLUMNS: tuple[str, ...] = (
    "change_type",
    "signal",
    "position",
    "population_scope",
    "field",
    "reference_value",
    "candidate_value",
)


@dataclass(frozen=True)
class RegistryComparison:
    """Row-level comparison between a reference registry and a candidate."""

    differences: pd.DataFrame
    summary: dict[str, int]


def _as_comparison_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def compare_registries(
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
) -> RegistryComparison:
    """Compare a computed registry candidate against a reference registry.

    The comparison is keyed by the governed registry primary key and checks
    required contract fields that exist in both frames. It is intended as a
    stabilization artifact, not as a validation gate.
    """
    key_columns = list(PRIMARY_KEY_COLUMNS)
    compare_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in key_columns and column in reference.columns and column in candidate.columns
    ]

    reference_compare = reference[key_columns + compare_columns].drop_duplicates(key_columns)
    candidate_compare = candidate[key_columns + compare_columns].drop_duplicates(key_columns)
    merged = reference_compare.merge(
        candidate_compare,
        on=key_columns,
        how="outer",
        suffixes=("_reference", "_candidate"),
        indicator=True,
    )

    rows: list[dict[str, object]] = []
    for _, row in merged.sort_values(key_columns, kind="stable").iterrows():
        key = {column: row[column] for column in key_columns}
        if row["_merge"] == "left_only":
            rows.append(
                {
                    "change_type": "missing_from_candidate",
                    **key,
                    "field": "row_presence",
                    "reference_value": "present",
                    "candidate_value": "",
                }
            )
            continue
        if row["_merge"] == "right_only":
            rows.append(
                {
                    "change_type": "new_in_candidate",
                    **key,
                    "field": "row_presence",
                    "reference_value": "",
                    "candidate_value": "present",
                }
            )
            continue

        for field in compare_columns:
            reference_value = _as_comparison_value(row[f"{field}_reference"])
            candidate_value = _as_comparison_value(row[f"{field}_candidate"])
            if reference_value == candidate_value:
                continue
            rows.append(
                {
                    "change_type": "field_changed",
                    **key,
                    "field": field,
                    "reference_value": reference_value,
                    "candidate_value": candidate_value,
                }
            )

    differences = pd.DataFrame(rows, columns=COMPARISON_COLUMNS)
    summary = {
        "reference_rows": len(reference_compare),
        "candidate_rows": len(candidate_compare),
        "difference_rows": len(differences),
        "missing_from_candidate": int(differences["change_type"].eq("missing_from_candidate").sum())
        if not differences.empty
        else 0,
        "new_in_candidate": int(differences["change_type"].eq("new_in_candidate").sum())
        if not differences.empty
        else 0,
        "field_changes": int(differences["change_type"].eq("field_changed").sum()) if not differences.empty else 0,
    }
    return RegistryComparison(differences=differences, summary=summary)
