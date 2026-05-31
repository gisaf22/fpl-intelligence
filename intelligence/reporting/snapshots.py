"""Weekly registry snapshot comparison utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from signals.governance.schema import PRIMARY_KEY_COLUMNS

SNAPSHOT_COMPARE_FIELDS: tuple[str, ...] = (
    "relationship_geometry",
    "association_class",
    "downstream_status",
    "low_confidence",
    "support_type",
)

SNAPSHOT_CHANGE_COLUMNS: tuple[str, ...] = (
    "gw",
    "previous_gw",
    "change_type",
    "signal",
    "position",
    "population_scope",
    "field",
    "previous_value",
    "current_value",
    "previous_downstream_status",
    "current_downstream_status",
)


def default_previous_snapshot_path(gw: int, output_dir: str | Path) -> Path | None:
    """Return the default prior-week snapshot path for a weekly output folder."""
    if gw <= 1:
        return None
    target_dir = Path(output_dir)
    return target_dir.parent / f"gw{gw - 1}" / "registry_snapshot.csv"


def _empty_changes(gw: int, previous_gw: int | None) -> pd.DataFrame:
    return pd.DataFrame(
        columns=SNAPSHOT_CHANGE_COLUMNS
    ).astype({"gw": "int64", "previous_gw": "Int64"})


def _value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _status(row: pd.Series, side: str) -> str:
    return _value(row.get(f"downstream_status_{side}", ""))


def _field_change_type(field: str, current_value: object) -> str:
    if field == "relationship_geometry":
        return "changed_geometry"
    if field == "association_class":
        return "changed_association_class"
    if field == "support_type":
        return "changed_support_type"
    if field == "low_confidence":
        return "changed_confidence_caveat"
    if field == "downstream_status":
        if current_value == "eligible":
            return "newly_eligible"
        if current_value == "blocked":
            return "newly_blocked"
        return "changed_downstream_status"
    return "changed_field"


def build_snapshot_changes(
    current_snapshot: pd.DataFrame,
    previous_snapshot: pd.DataFrame | None,
    gw: int,
    previous_gw: int | None = None,
) -> pd.DataFrame:
    """Compare current and prior registry snapshots.

    The comparison is keyed by signal, position, and population scope rather
    than row order. If no previous snapshot exists, the current snapshot is
    represented as a baseline marker.
    """
    if previous_snapshot is None:
        return pd.DataFrame(
            [
                {
                    "gw": gw,
                    "previous_gw": pd.NA,
                    "change_type": "baseline",
                    "signal": "",
                    "position": "",
                    "population_scope": "",
                    "field": "snapshot",
                    "previous_value": "",
                    "current_value": f"{len(current_snapshot)} rows",
                    "previous_downstream_status": "",
                    "current_downstream_status": "",
                }
            ],
            columns=SNAPSHOT_CHANGE_COLUMNS,
        )

    previous_gw = previous_gw if previous_gw is not None else gw - 1
    key_columns = list(PRIMARY_KEY_COLUMNS)
    compare_columns = key_columns + [
        field for field in SNAPSHOT_COMPARE_FIELDS if field in current_snapshot.columns
    ]
    previous_compare_columns = key_columns + [
        field for field in SNAPSHOT_COMPARE_FIELDS if field in previous_snapshot.columns
    ]

    current = current_snapshot[compare_columns].drop_duplicates(key_columns)
    previous = previous_snapshot[previous_compare_columns].drop_duplicates(key_columns)

    merged = previous.merge(
        current,
        on=key_columns,
        how="outer",
        suffixes=("_previous", "_current"),
        indicator=True,
    )

    rows: list[dict[str, object]] = []
    for _, row in merged.sort_values(key_columns, kind="stable").iterrows():
        key = {column: row[column] for column in key_columns}
        if row["_merge"] == "left_only":
            rows.append(
                {
                    "gw": gw,
                    "previous_gw": previous_gw,
                    "change_type": "removed",
                    **key,
                    "field": "row_presence",
                    "previous_value": "present",
                    "current_value": "",
                    "previous_downstream_status": _status(row, "previous"),
                    "current_downstream_status": "",
                }
            )
            continue
        if row["_merge"] == "right_only":
            rows.append(
                {
                    "gw": gw,
                    "previous_gw": previous_gw,
                    "change_type": "newly_observed",
                    **key,
                    "field": "row_presence",
                    "previous_value": "",
                    "current_value": "present",
                    "previous_downstream_status": "",
                    "current_downstream_status": _status(row, "current"),
                }
            )
            continue

        for field in SNAPSHOT_COMPARE_FIELDS:
            previous_col = f"{field}_previous"
            current_col = f"{field}_current"
            if previous_col not in merged.columns or current_col not in merged.columns:
                continue

            previous_value = row[previous_col]
            current_value = row[current_col]
            if _value(previous_value) == _value(current_value):
                continue

            rows.append(
                {
                    "gw": gw,
                    "previous_gw": previous_gw,
                    "change_type": _field_change_type(field, current_value),
                    **key,
                    "field": field,
                    "previous_value": _value(previous_value),
                    "current_value": _value(current_value),
                    "previous_downstream_status": _status(row, "previous"),
                    "current_downstream_status": _status(row, "current"),
                }
            )

    if not rows:
        return _empty_changes(gw=gw, previous_gw=previous_gw)

    changes = pd.DataFrame(rows, columns=SNAPSHOT_CHANGE_COLUMNS)
    return changes.sort_values(
        ["signal", "position", "population_scope", "field", "change_type"],
        kind="stable",
    ).reset_index(drop=True)


def write_snapshot_changes(
    current_snapshot: pd.DataFrame,
    gw: int,
    output_dir: str | Path,
    previous_snapshot_path: str | Path | None = None,
) -> Path:
    """Write snapshot comparison output for a weekly run."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    previous_path = (
        Path(previous_snapshot_path)
        if previous_snapshot_path is not None
        else default_previous_snapshot_path(gw, target_dir)
    )
    previous_snapshot = (
        pd.read_csv(previous_path)
        if previous_path is not None and previous_path.exists()
        else None
    )

    output_path = target_dir / "snapshot_changes.csv"
    build_snapshot_changes(
        current_snapshot=current_snapshot,
        previous_snapshot=previous_snapshot,
        gw=gw,
        previous_gw=gw - 1 if previous_snapshot is not None else None,
    ).to_csv(output_path, index=False)
    return output_path
