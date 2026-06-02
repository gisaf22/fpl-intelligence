"""Schema contract models and YAML loading for the staging layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA_DIR = Path(__file__).parent / "contracts"

VALID_DTYPES = {"int64", "Int64", "float64", "Float64", "str", "bool", "datetime64[ns]"}
VALID_TRANSFORMS = {"divide_by_10", "parse_datetime"}


@dataclass
class ColumnMapping:
    """Maps one source column to its canonical form, dtype, and optional transform."""

    source: str
    canonical: str
    dtype: str
    nullable: bool
    description: str
    transform: str | None = None


@dataclass
class Schema:
    """Full contract for a source table: its name and all column mappings."""

    source_table: str
    columns: list[ColumnMapping]
    pk_columns: list[str] = None  # source column names for ORDER BY


def load_schema(entity: str) -> Schema:
    """Load and validate a DAL schema from YAML, returning a typed Schema."""
    path = SCHEMA_DIR / f"{entity}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No schema file found for entity '{entity}': {path}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _parse_schema(entity, raw)


def _parse_schema(entity: str, raw: object) -> Schema:
    """Validate top-level schema structure and delegate column parsing."""
    if not isinstance(raw, dict):
        raise ValueError(f"Schema for '{entity}' must be a YAML mapping")
    source_table = _require_str(raw, "source_table", f"schema '{entity}'")
    _validate_identifier(source_table, entity, "source_table")
    columns_raw = raw.get("columns")
    if not isinstance(columns_raw, list) or not columns_raw:
        raise ValueError(f"Schema for '{entity}' 'columns' must be a non-empty list")
    columns = [_parse_column_mapping(entity, index, col) for index, col in enumerate(columns_raw)]
    pk_columns = raw.get("pk_columns")
    if pk_columns is not None:
        if not isinstance(pk_columns, list) or not all(isinstance(c, str) for c in pk_columns):
            raise ValueError(f"Schema for '{entity}' 'pk_columns' must be a list of strings")
    return Schema(source_table=source_table, columns=columns, pk_columns=pk_columns)


def _require_str(raw: dict[str, object], field_name: str, context: str) -> str:
    """Raise if field is missing or not a non-empty string."""
    value = raw.get(field_name)
    if value is None:
        raise ValueError(f"{context} is missing required field '{field_name}'")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field '{field_name}' must be a non-empty string")
    return value


def _require_bool(raw: dict[str, object], field_name: str, context: str) -> bool:
    """Raise if field is missing or not a boolean."""
    value = raw.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{context} field '{field_name}' must be a boolean")
    return value


def _validate_identifier(identifier: str, entity: str, field_name: str) -> None:
    """Raise if identifier is not a valid Python/SQL identifier."""
    if not identifier.isidentifier():
        raise ValueError(f"Schema for '{entity}' field '{field_name}' has invalid identifier '{identifier}'")


def _validate_in_set(value: str, valid: set[str], context: str, field_name: str) -> None:
    """Raise if value is not in the allowed set."""
    if value not in valid:
        raise ValueError(f"{context} field '{field_name}' has invalid value '{value}'. Valid: {valid}")


def _parse_column_mapping(entity: str, index: int, raw: object) -> ColumnMapping:
    """Parse and validate a single column entry into a ColumnMapping."""
    if not isinstance(raw, dict):
        raise ValueError(f"Schema for '{entity}' column {index} must be a YAML mapping")
    ctx = f"Schema for '{entity}' column {index}"
    source = _require_str(raw, "source", ctx)
    canonical = _require_str(raw, "canonical", ctx)
    dtype = _require_str(raw, "dtype", ctx)
    description = _require_str(raw, "description", ctx)
    nullable = _require_bool(raw, "nullable", ctx)
    transform = _parse_transform(raw.get("transform"), ctx)
    _validate_identifier(source, entity, f"columns[{index}].source")
    _validate_identifier(canonical, entity, f"columns[{index}].canonical")
    _validate_in_set(dtype, VALID_DTYPES, ctx, "dtype")
    return ColumnMapping(
        source=source,
        canonical=canonical,
        dtype=dtype,
        nullable=nullable,
        description=description,
        transform=transform,
    )


def _parse_transform(transform: object, context: str) -> str | None:
    """Validate and return the optional transform name, or None if absent."""
    if transform is None:
        return None
    if not isinstance(transform, str):
        raise ValueError(f"{context} field 'transform' must be a string")
    _validate_in_set(transform, VALID_TRANSFORMS, context, "transform")
    return transform
