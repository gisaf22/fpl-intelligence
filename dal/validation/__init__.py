"""DAL validation module library — standalone validation functions for all pipeline layers."""

from dal.validation.grain import validate_grain_uniqueness
from dal.validation.completeness import validate_row_completeness
from dal.validation.semantics import validate_bgw_correctness, validate_dgw_correctness
from dal.validation.joins import validate_join_safety
from dal.validation.contracts import validate_column_contract
from dal.validation.nulls import validate_null_semantics
from dal.validation.invariants import (
    validate_time_continuity,
    validate_row_count_invariant,
    validate_no_future_data,
)


__all__ = [
    "validate_grain_uniqueness",
    "validate_row_completeness",
    "validate_bgw_correctness",
    "validate_dgw_correctness",
    "validate_join_safety",
    "validate_column_contract",
    "validate_null_semantics",
    "validate_time_continuity",
    "validate_row_count_invariant",
    "validate_no_future_data"
]
