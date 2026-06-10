"""Row completeness validation.

Two concerns:
  validate_row_completeness  — structural: asserts every (player_id, gw) pair exists in the spine.
  summarise_population_coverage — descriptive: counts rows, NULLs, and late-joining players for EDA.
"""

import pandas as pd

from dal.exceptions import DALContractViolation


def validate_row_completeness(
    df: pd.DataFrame,
    player_ids: list[int],
    gw_range: list[int],
) -> None:
    expected = {(p, g) for p in player_ids for g in gw_range}
    actual = set(zip(df["player_id"], df["gw"]))
    missing = expected - actual
    if len(missing) != 0:
        raise DALContractViolation(
            message=(
                f"Row completeness violation: {len(missing)} missing (player_id, gw) pairs\n{sorted(missing)[:20]}"
            ),
            validation="validate_row_completeness",
            n_violations=len(missing),
            error_code="ROW_COUNT",
        )


def summarise_population_coverage(
    df: pd.DataFrame,
    player_id_col: str = "player_id",
    gw_col: str = "gw",
    started_col: str = "starts",
    study_gw_min: int = 6,
) -> dict:
    """Descriptive population coverage summary for EDA integrity checks.

    Reports row counts, NULL rates on the activity column, and late-joining
    players. Used by EDA-0 to assess study population before any statistical
    work begins.

    Note: checks started_col (default: starts) — NULL means the player did not
    feature that GW and would be excluded by the activity filter. GWs 1 to
    study_gw_min-1 are excluded from studies because rolling window signals are
    undefined there. Late joiners are players whose first non-null appearance is
    after study_gw_min — mid-season signings who miss the valid study window.

    Returns dict with keys:
      total_rows        — GW-player rows (not distinct players)
      null_rows         — rows where started_col is NULL
      null_pct          — null_rows as % of total_rows
      late_joiners      — distinct players first seen after study_gw_min
      first_appearances — Series: player_id → first non-null GW
    """
    total = len(df)
    null_count = df[started_col].isna().sum()
    first_gw = df[df[started_col].notna()].groupby(player_id_col)[gw_col].min()
    late_joiners = (first_gw > study_gw_min).sum()
    return {
        "total_rows": total,
        "null_rows": null_count,
        "null_pct": (null_count / total * 100),
        "late_joiners": late_joiners,
        "first_appearances": first_gw,
    }
