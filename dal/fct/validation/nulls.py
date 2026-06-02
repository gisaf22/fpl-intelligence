"""Null semantics validation — asserts columns conform to declared null rules."""

import pandas as pd

from dal.exceptions import DALContractViolation


def validate_null_semantics(df: pd.DataFrame, rules: dict[str, str]) -> None:
    errors = []
    total_violations = 0

    for col, rule in rules.items():
        if col not in df.columns:
            continue

        if rule == "never_null":
            n_nulls = int(df[col].isna().sum())
            if n_nulls > 0:
                errors.append(f"{col} (never_null): {n_nulls} null rows found")
                total_violations += n_nulls

        elif rule == "null_if_bgw":
            if "is_bgw" not in df.columns:
                continue
            bgw_mask = df["is_bgw"].astype(bool)
            bgw_rows = df[bgw_mask]
            non_bgw_rows = df[~bgw_mask]

            not_null_in_bgw = bgw_rows[bgw_rows[col].notna()]
            if not not_null_in_bgw.empty:
                errors.append(f"{col} (null_if_bgw): {len(not_null_in_bgw)} BGW rows are not null")
                total_violations += len(not_null_in_bgw)

            null_in_non_bgw = non_bgw_rows[non_bgw_rows[col].isna()]
            if not null_in_non_bgw.empty:
                errors.append(f"{col} (null_if_bgw): {len(null_in_non_bgw)} non-BGW rows are null")
                total_violations += len(null_in_non_bgw)

        elif rule == "always_nullable":
            pass  # no assertion

        else:
            raise ValueError(f"Unknown null rule {rule!r} for column {col!r}")

    if errors:
        raise DALContractViolation(
            message="Null semantics violation:\n" + "\n".join(errors),
            validation="validate_null_semantics",
            n_violations=total_violations,
            error_code="NULL_VIOLATION",
        )
