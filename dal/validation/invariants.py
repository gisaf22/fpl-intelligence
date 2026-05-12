"""System invariant validation — time continuity, row count, and temporal causality.

Validation layer: this module must not import from dal.curated/. All curated-layer
constants needed here (e.g. PERFORMANCE_COLS) are passed as parameters by the caller.
"""

import pandas as pd

from dal.exceptions import DALContractViolation


def validate_time_continuity(
    df: pd.DataFrame,
    player_col: str = 'player_id',
    gw_col: str = 'gw',
) -> None:
    player_errors = []
    for player_id, group in df.groupby(player_col):
        gws = sorted(group[gw_col].tolist())
        expected = list(range(min(gws), max(gws) + 1))
        if gws != expected:
            missing = sorted(set(expected) - set(gws))
            player_errors.append(f"player_id={player_id}: missing GWs {missing}")

    if player_errors:
        raise DALContractViolation(
            message=(
                f"Time continuity violation for {len(player_errors)} player(s):\n"
                + "\n".join(player_errors)
            ),
            layer='curated',
            validation='validate_time_continuity',
            n_violations=len(player_errors),
            error_code='TIME_GAP',
        )


def validate_row_count_invariant(df: pd.DataFrame, n_players: int, n_gws: int) -> None:
    expected = n_players * n_gws
    actual = len(df)
    if actual != expected:
        raise DALContractViolation(
            message=(
                f"Row count violation: expected {expected} "
                f"({n_players} players × {n_gws} GWs), "
                f"got {actual}"
            ),
            layer='curated',
            validation='validate_row_count_invariant',
            n_violations=abs(actual - expected),
            error_code='ROW_COUNT',
        )


def validate_no_future_data(
    df: pd.DataFrame,
    gw_col: str = 'gw',
    reference_gw=None,
    performance_cols=None,
) -> None:
    """Assert no future-GW rows contain non-null performance data.

    performance_cols: iterable of column names to check. Callers pass their layer's
    PERFORMANCE_COLS constant — this module does not import it to avoid upward coupling.
    If None, the check is skipped (backward-compatible for callers that have not yet
    been updated to pass performance_cols).
    """
    if reference_gw is None:
        return

    future_rows = df[df[gw_col] > reference_gw]
    if future_rows.empty:
        return

    if performance_cols is None:
        return

    violation_messages = []
    total_violations = 0
    for col in performance_cols:
        if col not in future_rows.columns:
            continue
        bad = future_rows[future_rows[col].notna()]
        if not bad.empty:
            pairs = list(zip(bad['player_id'], bad[gw_col]))[:10]
            violation_messages.append(
                f"{col}: {len(bad)} rows with non-null values beyond GW {reference_gw} "
                f"(first pairs: {pairs})"
            )
            total_violations += len(bad)

    if violation_messages:
        raise DALContractViolation(
            message=(
                f"Future data violation (reference_gw={reference_gw}):\n"
                + "\n".join(violation_messages)
            ),
            layer='curated',
            validation='validate_no_future_data',
            n_violations=total_violations,
            error_code='FUTURE_DATA',
        )
