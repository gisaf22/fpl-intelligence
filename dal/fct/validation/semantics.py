"""BGW and DGW semantic correctness validation."""

import pandas as pd

from dal.exceptions import DALContractViolation


def _raise_if(
    frame: pd.DataFrame,
    mask: pd.Series,
    message: str,
    validation: str,
    error_code: str,
) -> None:
    bad = frame[mask]
    if not bad.empty:
        raise DALContractViolation(
            message=f"{message}: {len(bad)} rows",
            validation=validation,
            n_violations=len(bad),
            error_code=error_code,
        )


def _raise_if_notnull(frame: pd.DataFrame, col: str, message: str, validation: str, error_code: str) -> None:
    if col not in frame.columns:
        return
    _raise_if(frame, frame[col].notna(), message, validation, error_code)


def _raise_if_null(frame: pd.DataFrame, col: str, message: str, validation: str, error_code: str) -> None:
    if col not in frame.columns:
        return
    _raise_if(frame, frame[col].isna(), message, validation, error_code)


def validate_bgw_correctness(df: pd.DataFrame, performance_cols: set[str] | list[str] | None = None) -> None:
    """Assert BGW rows conform to the BGW semantic contract.

    performance_cols: iterable of column names that must be NULL for BGW rows.
    Callers pass their layer's PERFORMANCE_COLS constant. If None, the performance
    column check is skipped — only fixture_count, fdr, and was_home are checked.
    """
    bgw = df[df["is_bgw"].astype(bool)]
    if bgw.empty:
        return

    _raise_if(
        bgw,
        bgw["fixture_count"] != 0,
        "BGW correctness violation: have fixture_count != 0",
        "validate_bgw_correctness",
        "BGW_VIOLATION",
    )

    for col in performance_cols or ():
        _raise_if_notnull(
            bgw, col, f"BGW correctness violation: have {col} not null", "validate_bgw_correctness", "BGW_VIOLATION"
        )

    _raise_if_notnull(
        bgw, "fdr_avg", "BGW correctness violation: have fdr_avg not null", "validate_bgw_correctness", "BGW_VIOLATION"
    )

    _raise_if_notnull(
        bgw,
        "was_home",
        "BGW correctness violation: have was_home not null",
        "validate_bgw_correctness",
        "BGW_VIOLATION",
    )


def validate_dgw_correctness(df: pd.DataFrame) -> None:
    # fixture_count must be in {0, 1, 2} for all rows — TGW not supported
    if "fixture_count" in df.columns:
        _raise_if(
            df,
            ~df["fixture_count"].isin([0, 1, 2]),
            (
                "fixture_count not in {0, 1, 2} — triple gameweeks not supported. "
                "Extend SUM_COLS aggregation logic and validate DGW contract before ingesting TGW data."
            ),
            "validate_dgw_correctness",
            "DGW_VIOLATION",
        )

    dgw = df[df["is_dgw"].astype(bool)]
    if dgw.empty:
        return

    _raise_if(
        dgw,
        dgw["fixture_count"] != 2,
        "DGW correctness violation: have fixture_count != 2",
        "validate_dgw_correctness",
        "DGW_VIOLATION",
    )

    if "home_count" in dgw.columns and "away_count" in dgw.columns:
        _raise_if(
            dgw,
            (dgw["home_count"] + dgw["away_count"]) != 2,
            "DGW correctness violation: have home_count + away_count != 2",
            "validate_dgw_correctness",
            "DGW_VIOLATION",
        )

    _raise_if_null(
        dgw, "fdr_avg", "DGW correctness violation: have fdr_avg null", "validate_dgw_correctness", "DGW_VIOLATION"
    )

    if "clean_sheets" in dgw.columns:
        _raise_if(
            dgw,
            ~dgw["clean_sheets"].isin([0, 1, 2]),
            "DGW correctness violation: have clean_sheets not in {0, 1, 2}",
            "validate_dgw_correctness",
            "DGW_VIOLATION",
        )
