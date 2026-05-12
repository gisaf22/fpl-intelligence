"""Row completeness validation — asserts every (player_id, gw) combination exists in the spine."""

import pandas as pd

from dal.exceptions import DALContractViolation


def validate_row_completeness(df: pd.DataFrame, player_ids, gw_range) -> None:
    expected = {(p, g) for p in player_ids for g in gw_range}
    actual = set(zip(df['player_id'], df['gw']))
    missing = expected - actual
    if len(missing) != 0:
        raise DALContractViolation(
            message=(
                f"Row completeness violation: {len(missing)} missing (player_id, gw) pairs\n"
                f"{sorted(missing)[:20]}"
            ),
            validation='validate_row_completeness',
            n_violations=len(missing),
            error_code='ROW_COUNT',
        )
