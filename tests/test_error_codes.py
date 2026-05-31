"""Unit tests for ErrorCode vocabulary and DALContractViolation.

Capabilities tested: Operability — consumers catching exceptions know
exactly what error codes to expect without reading source code.
All tests run without a live database.
"""

from __future__ import annotations

import pytest

from dal.exceptions import DALContractViolation, ErrorCode

# ---------------------------------------------------------------------------
# ErrorCode constants
# ---------------------------------------------------------------------------

_ALL_ERROR_CODES = [
    ErrorCode.GRAIN_DUPLICATE,
    ErrorCode.ROW_COUNT,
    ErrorCode.MISSING_COLUMNS,
    ErrorCode.COLUMN_EXTRA,
    ErrorCode.DTYPE_MISMATCH,
    ErrorCode.NULL_VIOLATION,
    ErrorCode.JOIN_SAFETY,
    ErrorCode.TIME_CONTINUITY,
    ErrorCode.FUTURE_DATA,
    ErrorCode.BGW_VIOLATION,
    ErrorCode.DGW_VIOLATION,
]


@pytest.mark.unit
def test_all_error_code_constants_are_strings() -> None:
    """Every ErrorCode attribute must be a non-empty string."""
    for code in _ALL_ERROR_CODES:
        assert isinstance(code, str), f"ErrorCode constant is not a string: {code!r}"
        assert code, "ErrorCode constant is empty string"


@pytest.mark.unit
def test_error_code_constants_are_unique() -> None:
    """No two ErrorCode constants may share the same string value."""
    assert len(_ALL_ERROR_CODES) == len(set(_ALL_ERROR_CODES)), (
        "Duplicate ErrorCode string values found"
    )


# ---------------------------------------------------------------------------
# DALContractViolation accepts all documented error codes
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("code", _ALL_ERROR_CODES)
def test_dal_contract_violation_accepts_error_code(code: str) -> None:
    """DALContractViolation must accept every documented ErrorCode without raising."""
    exc = DALContractViolation("test message", error_code=code)
    assert exc.error_code == code


@pytest.mark.unit
def test_dal_contract_violation_rejects_unknown_code() -> None:
    """DALContractViolation must raise ValueError for an undocumented error_code."""
    with pytest.raises(ValueError, match="Invalid error_code"):
        DALContractViolation("test", error_code="UNDOCUMENTED_CODE")


@pytest.mark.unit
def test_dal_contract_violation_formats_error_code_in_str() -> None:
    """The error_code constant must appear in the exception's string representation."""
    exc = DALContractViolation(
        "duplicate rows detected",
        error_code=ErrorCode.GRAIN_DUPLICATE,
        n_violations=3,
    )
    exc_str = str(exc)
    assert ErrorCode.GRAIN_DUPLICATE in exc_str


@pytest.mark.unit
def test_grain_duplicate_uses_correct_error_code() -> None:
    """Confirms the semantic intent: GRAIN_DUPLICATE names a grain uniqueness failure."""
    exc = DALContractViolation(
        "duplicate (player_id, gw) pairs",
        validation="grain_uniqueness",
        n_violations=2,
        error_code=ErrorCode.GRAIN_DUPLICATE,
    )
    assert exc.error_code == "GRAIN_DUPLICATE"
    assert exc.n_violations == 2
