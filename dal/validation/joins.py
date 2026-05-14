"""Join safety validation — asserts joins do not silently drop or duplicate rows."""

from dal.exceptions import DALContractViolation


def validate_join_safety(
    left_n: int,
    right_n: int,
    result_n: int,
    join_type: str,
    description: str,
) -> None:
    if join_type == 'left':
        if result_n < left_n:
            raise DALContractViolation(
                message=(
                    f"Join safety violation [{description}]: left join expected {left_n} rows, "
                    f"got {result_n}"
                ),
                validation="validate_join_safety",
                layer=None,
                n_violations=left_n - result_n,
                error_code='JOIN_ROW_LOSS',
            )
        if result_n > left_n:
            raise DALContractViolation(
                message=(
                    f"Join safety violation [{description}]: left join expected {left_n} rows, "
                    f"got {result_n}"
                ),
                validation="validate_join_safety",
                layer=None,
                n_violations=result_n - left_n,
                error_code='JOIN_FANOUT',
            )

    elif join_type == 'inner':
        # Note: this only detects result_n > min(left_n, right_n). It does NOT catch fanout
        # caused by duplicate keys on the right side — that requires the right frame's join
        # key to be validated for uniqueness before the merge.
        expected_max = min(left_n, right_n)
        if result_n > expected_max:
            raise DALContractViolation(
                message=(
                    f"Join safety violation [{description}]: inner join expected <= "
                    f"{expected_max} rows, got {result_n}"
                ),
                validation="validate_join_safety",
                layer=None,
                n_violations=result_n - expected_max,
                error_code='JOIN_FANOUT',
            )

    elif join_type == 'cross':
        expected = left_n * right_n
        if result_n < expected:
            raise DALContractViolation(
                message=(
                    f"Join safety violation [{description}]: cross join expected {expected} rows "
                    f"({left_n} × {right_n}), got {result_n}"
                ),
                validation="validate_join_safety",
                layer=None,
                n_violations=expected - result_n,
                error_code='JOIN_ROW_LOSS',
            )
        if result_n > expected:
            raise DALContractViolation(
                message=(
                    f"Join safety violation [{description}]: cross join expected {expected} rows "
                    f"({left_n} × {right_n}), got {result_n}"
                ),
                validation="validate_join_safety",
                layer=None,
                n_violations=result_n - expected,
                error_code='JOIN_FANOUT',
            )

    else:
        raise ValueError(f"Unknown join_type: {join_type!r}. Must be 'left', 'inner', or 'cross'.")
