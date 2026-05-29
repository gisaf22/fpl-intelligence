"""Column contract validation — asserts exact column set and dtype conformance."""

import pandas as pd

from dal.exceptions import DALContractViolation


def validate_column_contract(df: pd.DataFrame, expected_cols: list, dtypes: dict) -> None:
    actual = set(df.columns)
    expected = set(expected_cols)

    extra = actual - expected
    missing = expected - actual

    if extra:
        raise DALContractViolation(
            message=f"Extra columns: {sorted(extra)}",

            validation='validate_column_contract',
            n_violations=len(extra),
            error_code='COLUMN_EXTRA',
        )

    if missing:
        raise DALContractViolation(
            message=f"Missing columns: {sorted(missing)}",

            validation='validate_column_contract',
            n_violations=len(missing),
            error_code='MISSING_COLUMNS',
        )

    dtype_mismatches = []
    for col, expected_dtype in dtypes.items():
        if col not in df.columns:
            continue
        actual_dtype = str(df[col].dtype)
        if actual_dtype != str(expected_dtype):
            dtype_mismatches.append(
                f"  {col}: expected {expected_dtype}, got {actual_dtype}"
            )

    if dtype_mismatches:
        raise DALContractViolation(
            message="Dtype mismatches:\n" + "\n".join(dtype_mismatches),

            validation='validate_column_contract',
            n_violations=len(dtype_mismatches),
            error_code='DTYPE_MISMATCH',
        )
