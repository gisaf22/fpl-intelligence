"""BGW and DGW semantic correctness validation."""

import pandas as pd

from dal.curated.contracts import PERFORMANCE_COLS
from dal.exceptions import DALContractViolation


def validate_bgw_correctness(df: pd.DataFrame) -> None:
    bgw = df[df['is_bgw'] == True]
    if bgw.empty:
        return

    # fixture_count must be 0
    bad_fc = bgw[bgw['fixture_count'] != 0]
    if not bad_fc.empty:
        raise DALContractViolation(
            message=f"BGW correctness violation: {len(bad_fc)} rows have fixture_count != 0",
            layer='curated',
            validation='validate_bgw_correctness',
            n_violations=len(bad_fc),
            error_code='BGW_NONZERO',
        )

    # performance columns must be null (pd.NA) — any non-null value is a violation.
    # Using .notna() instead of != 0: non-null 0.0 (Float64) would silently pass != 0.
    for col in PERFORMANCE_COLS:
        if col not in bgw.columns:
            continue
        bad = bgw[bgw[col].notna()]
        if not bad.empty:
            raise DALContractViolation(
                message=f"BGW correctness violation: {len(bad)} rows have {col} not null",
                layer='curated',
                validation='validate_bgw_correctness',
                n_violations=len(bad),
                error_code='BGW_NONZERO',
            )

    # fdr columns must be NULL
    for col in ('fdr_avg', 'fdr_min', 'fdr_max'):
        if col not in bgw.columns:
            continue
        bad = bgw[bgw[col].notna()]
        if not bad.empty:
            raise DALContractViolation(
                message=f"BGW correctness violation: {len(bad)} rows have {col} not null",
                layer='curated',
                validation='validate_bgw_correctness',
                n_violations=len(bad),
                error_code='BGW_NONZERO',
            )

    # was_home must be NULL
    if 'was_home' in bgw.columns:
        bad = bgw[bgw['was_home'].notna()]
        if not bad.empty:
            raise DALContractViolation(
                message=f"BGW correctness violation: {len(bad)} rows have was_home not null",
                layer='curated',
                validation='validate_bgw_correctness',
                n_violations=len(bad),
                error_code='BGW_NONZERO',
            )


def validate_dgw_correctness(df: pd.DataFrame) -> None:
    # fixture_count must be in {0, 1, 2} for all rows
    if 'fixture_count' in df.columns:
        bad_bounds = df[~df['fixture_count'].isin([0, 1, 2])]
        if not bad_bounds.empty:
            raise DALContractViolation(
                message=(
                    f"DGW correctness violation: {len(bad_bounds)} rows have "
                    f"fixture_count not in {{0, 1, 2}}"
                ),
                layer='curated',
                validation='validate_dgw_correctness',
                n_violations=len(bad_bounds),
                error_code='DGW_WRONG_COUNT',
            )

    dgw = df[df['is_dgw'] == True]
    if dgw.empty:
        return

    # fixture_count must be 2
    bad_fc = dgw[dgw['fixture_count'] != 2]
    if not bad_fc.empty:
        raise DALContractViolation(
            message=f"DGW correctness violation: {len(bad_fc)} rows have fixture_count != 2",
            layer='curated',
            validation='validate_dgw_correctness',
            n_violations=len(bad_fc),
            error_code='DGW_WRONG_COUNT',
        )

    # home_count + away_count must be 2
    if 'home_count' in dgw.columns and 'away_count' in dgw.columns:
        bad_ha = dgw[(dgw['home_count'] + dgw['away_count']) != 2]
        if not bad_ha.empty:
            raise DALContractViolation(
                message=(
                    f"DGW correctness violation: {len(bad_ha)} rows have "
                    f"home_count + away_count != 2"
                ),
                layer='curated',
                validation='validate_dgw_correctness',
                n_violations=len(bad_ha),
                error_code='DGW_WRONG_COUNT',
            )

    # fdr_avg must not be NULL
    if 'fdr_avg' in dgw.columns:
        bad_fdr = dgw[dgw['fdr_avg'].isna()]
        if not bad_fdr.empty:
            raise DALContractViolation(
                message=f"DGW correctness violation: {len(bad_fdr)} rows have fdr_avg null",
                layer='curated',
                validation='validate_dgw_correctness',
                n_violations=len(bad_fdr),
                error_code='DGW_WRONG_COUNT',
            )

    # fdr_min <= fdr_avg <= fdr_max
    if all(c in dgw.columns for c in ('fdr_min', 'fdr_avg', 'fdr_max')):
        bad_order = dgw[
            (dgw['fdr_min'] > dgw['fdr_avg']) | (dgw['fdr_avg'] > dgw['fdr_max'])
        ]
        if not bad_order.empty:
            raise DALContractViolation(
                message=(
                    f"DGW correctness violation: {len(bad_order)} rows have fdr ordering "
                    f"violated (fdr_min <= fdr_avg <= fdr_max)"
                ),
                layer='curated',
                validation='validate_dgw_correctness',
                n_violations=len(bad_order),
                error_code='DGW_WRONG_COUNT',
            )

    # clean_sheets must be in {0, 1, 2}
    if 'clean_sheets' in dgw.columns:
        bad_cs = dgw[~dgw['clean_sheets'].isin([0, 1, 2])]
        if not bad_cs.empty:
            raise DALContractViolation(
                message=(
                    f"DGW correctness violation: {len(bad_cs)} rows have "
                    f"clean_sheets not in {{0, 1, 2}}"
                ),
                layer='curated',
                validation='validate_dgw_correctness',
                n_violations=len(bad_cs),
                error_code='DGW_WRONG_COUNT',
            )
