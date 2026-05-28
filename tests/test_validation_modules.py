"""Unit tests for dal/validation/* modules."""

import numpy as np
import pandas as pd
import pytest

from dal.curated.contracts import PERFORMANCE_COLS
from dal.exceptions import DALContractViolation
from dal.validation import (
    validate_grain_uniqueness,
    validate_row_completeness,
    validate_bgw_correctness,
    validate_dgw_correctness,
    validate_join_safety,
    validate_column_contract,
    validate_null_semantics,
    validate_time_continuity,
    validate_row_count_invariant,
    validate_no_future_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_perf_row(**overrides):
    base = dict(
        player_id=1, gw=1,
        is_bgw=False, is_dgw=False,
        fixture_count=1,
        home_count=1, away_count=0,
        total_points=6, minutes=90,
        goals_scored=1, assists=0,
        clean_sheets=1, yellow_cards=0, red_cards=0,
        saves=0, bonus=3, bps=30,
        xg=0.4, xa=0.1, xgi=0.5,
        fdr_avg=3.0,
        was_home=True,
    )
    base.update(overrides)
    return base


def _make_bgw_row(**overrides):
    # Contract: BGW performance columns must be NULL (pd.NA), not zero — see DAL_CONTRACT.md Section 5
    base = dict(
        player_id=1, gw=2,
        is_bgw=True, is_dgw=False,
        fixture_count=0,
        home_count=0, away_count=0,
        total_points=None, minutes=None,
        goals_scored=None, assists=None,
        clean_sheets=None, yellow_cards=None, red_cards=None,
        saves=None, bonus=None, bps=None,
        xg=None, xa=None, xgi=None,
        fdr_avg=None,
        was_home=None,
    )
    base.update(overrides)
    return base


def _make_dgw_row(**overrides):
    base = dict(
        player_id=1, gw=3,
        is_bgw=False, is_dgw=True,
        fixture_count=2,
        home_count=1, away_count=1,
        total_points=10, minutes=180,
        goals_scored=2, assists=1,
        clean_sheets=1, yellow_cards=0, red_cards=0,
        saves=0, bonus=5, bps=50,
        xg=0.8, xa=0.3, xgi=1.1,
        fdr_avg=3.0,
        was_home=None,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_grain_uniqueness
# ---------------------------------------------------------------------------

class TestValidateGrainUniqueness:
    def test_no_duplicates_passes(self):
        df = pd.DataFrame([
            {'player_id': 1, 'gw': 1},
            {'player_id': 1, 'gw': 2},
            {'player_id': 2, 'gw': 1},
        ])
        assert validate_grain_uniqueness(df, ['player_id', 'gw'], 'test') is None

    def test_one_duplicate_pair_fails(self):
        df = pd.DataFrame([
            {'player_id': 1, 'gw': 1},
            {'player_id': 1, 'gw': 1},
        ])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_grain_uniqueness(df, ['player_id', 'gw'], 'curated')
        assert 'curated' in str(exc_info.value)
        assert '1 duplicate' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'GRAIN_DUPLICATE'
        assert exc.validation == 'validate_grain_uniqueness'
        assert exc.n_violations == 1

    def test_multiple_duplicate_pairs_fails_with_count(self):
        df = pd.DataFrame([
            {'player_id': 1, 'gw': 1},
            {'player_id': 1, 'gw': 1},
            {'player_id': 2, 'gw': 5},
            {'player_id': 2, 'gw': 5},
        ])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_grain_uniqueness(df, ['player_id', 'gw'], 'curated')
        assert '2 duplicate' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'GRAIN_DUPLICATE'
        assert exc.validation == 'validate_grain_uniqueness'
        assert exc.n_violations == 2


# ---------------------------------------------------------------------------
# validate_row_completeness
# ---------------------------------------------------------------------------

class TestValidateRowCompleteness:
    def test_exact_cartesian_product_passes(self):
        players = [1, 2]
        gws = [1, 2, 3]
        rows = [{'player_id': p, 'gw': g} for p in players for g in gws]
        df = pd.DataFrame(rows)
        assert validate_row_completeness(df, players, gws) is None

    def test_missing_one_pair_fails(self):
        players = [1, 2]
        gws = [1, 2, 3]
        rows = [{'player_id': p, 'gw': g} for p in players for g in gws
                if not (p == 1 and g == 2)]
        df = pd.DataFrame(rows)
        with pytest.raises(DALContractViolation) as exc_info:
            validate_row_completeness(df, players, gws)
        assert '(1, 2)' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'ROW_COUNT'
        assert exc.validation == 'validate_row_completeness'
        assert exc.n_violations == 1

    def test_missing_all_rows_for_one_player_fails(self):
        players = [1, 2]
        gws = [1, 2, 3]
        rows = [{'player_id': 2, 'gw': g} for g in gws]
        df = pd.DataFrame(rows)
        with pytest.raises(DALContractViolation) as exc_info:
            validate_row_completeness(df, players, gws)
        assert '3 missing' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'ROW_COUNT'
        assert exc.validation == 'validate_row_completeness'
        assert exc.n_violations == 3


# ---------------------------------------------------------------------------
# validate_bgw_correctness
# ---------------------------------------------------------------------------

class TestValidateBgwCorrectness:
    def test_correct_bgw_rows_passes(self):
        df = pd.DataFrame([_make_bgw_row()])
        assert validate_bgw_correctness(df) is None

    def test_no_bgw_rows_passes(self):
        df = pd.DataFrame([_make_perf_row()])
        assert validate_bgw_correctness(df) is None

    def test_bgw_row_with_total_points_nonzero_fails(self):
        df = pd.DataFrame([_make_bgw_row(total_points=5)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_bgw_correctness(df, performance_cols=PERFORMANCE_COLS)
        assert 'total_points' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'BGW_NONZERO'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_bgw_correctness'
        assert exc.n_violations == 1

    def test_bgw_row_with_fdr_avg_not_null_fails(self):
        df = pd.DataFrame([_make_bgw_row(fdr_avg=3.0)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_bgw_correctness(df)
        assert 'fdr_avg' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'BGW_NONZERO'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_bgw_correctness'
        assert exc.n_violations == 1

    def test_bgw_row_with_fixture_count_nonzero_fails(self):
        df = pd.DataFrame([_make_bgw_row(fixture_count=1)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_bgw_correctness(df)
        assert 'fixture_count' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'BGW_NONZERO'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_bgw_correctness'
        assert exc.n_violations == 1

    def test_bgw_row_with_was_home_not_null_fails(self):
        df = pd.DataFrame([_make_bgw_row(was_home=True)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_bgw_correctness(df)
        assert 'was_home' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'BGW_NONZERO'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_bgw_correctness'
        assert exc.n_violations == 1


# ---------------------------------------------------------------------------
# validate_dgw_correctness
# ---------------------------------------------------------------------------

class TestValidateDgwCorrectness:
    def test_correct_dgw_row_passes(self):
        df = pd.DataFrame([_make_dgw_row()])
        assert validate_dgw_correctness(df) is None

    def test_dgw_row_fixture_count_not_two_fails(self):
        df = pd.DataFrame([_make_dgw_row(fixture_count=1)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_dgw_correctness(df)
        assert 'fixture_count' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'DGW_WRONG_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_dgw_correctness'
        assert exc.n_violations == 1

    def test_dgw_row_clean_sheets_three_fails(self):
        df = pd.DataFrame([_make_dgw_row(clean_sheets=3)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_dgw_correctness(df)
        assert 'clean_sheets' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'DGW_WRONG_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_dgw_correctness'
        assert exc.n_violations == 1

    def test_fixture_count_out_of_bounds_fails(self):
        df = pd.DataFrame([_make_perf_row(fixture_count=3)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_dgw_correctness(df)
        assert 'fixture_count' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'DGW_WRONG_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_dgw_correctness'
        assert exc.n_violations == 1

    def test_dgw_home_away_not_summing_to_two_fails(self):
        df = pd.DataFrame([_make_dgw_row(home_count=2, away_count=1)])  # sums to 3, not 2
        with pytest.raises(DALContractViolation) as exc_info:
            validate_dgw_correctness(df)
        exc = exc_info.value
        assert exc.error_code == 'DGW_WRONG_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_dgw_correctness'
        assert exc.n_violations == 1

    def test_dgw_fdr_avg_null_fails(self):
        df = pd.DataFrame([_make_dgw_row(fdr_avg=None)])
        with pytest.raises(DALContractViolation) as exc_info:
            validate_dgw_correctness(df)
        assert 'fdr_avg' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'DGW_WRONG_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_dgw_correctness'
        assert exc.n_violations == 1


# ---------------------------------------------------------------------------
# validate_join_safety
# ---------------------------------------------------------------------------

class TestValidateJoinSafety:
    def test_left_join_exact_passes(self):
        assert validate_join_safety(100, 50, 100, 'left', 'test join') is None

    def test_left_join_row_loss_fails(self):
        with pytest.raises(DALContractViolation) as exc_info:
            validate_join_safety(100, 50, 90, 'left', 'staging join')
        assert 'staging join' in str(exc_info.value)
        assert '100' in str(exc_info.value)
        assert '90' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'JOIN_ROW_LOSS'
        assert exc.validation == 'validate_join_safety'
        assert exc.n_violations == 10

    def test_left_join_fanout_fails(self):
        with pytest.raises(DALContractViolation) as exc_info:
            validate_join_safety(100, 50, 120, 'left', 'fanout join')
        assert '120' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'JOIN_FANOUT'
        assert exc.validation == 'validate_join_safety'
        assert exc.n_violations == 20

    def test_cross_join_correct_passes(self):
        assert validate_join_safety(10, 38, 380, 'cross', 'spine') is None

    def test_cross_join_wrong_count_fails(self):
        with pytest.raises(DALContractViolation) as exc_info:
            validate_join_safety(10, 38, 370, 'cross', 'spine')
        assert '380' in str(exc_info.value)
        assert '370' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'JOIN_ROW_LOSS'
        assert exc.validation == 'validate_join_safety'
        assert exc.n_violations == 10

    def test_inner_join_within_bounds_passes(self):
        assert validate_join_safety(100, 80, 75, 'inner', 'inner join') is None

    def test_inner_join_exceeds_min_fails(self):
        with pytest.raises(DALContractViolation) as exc_info:
            validate_join_safety(100, 80, 90, 'inner', 'bad inner')
        assert '80' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'JOIN_FANOUT'
        assert exc.validation == 'validate_join_safety'
        assert exc.n_violations == 10


# ---------------------------------------------------------------------------
# validate_column_contract
# ---------------------------------------------------------------------------

class TestValidateColumnContract:
    def _make_df(self):
        return pd.DataFrame({
            'player_id': pd.array([1], dtype='int64'),
            'gw': pd.array([1], dtype='int64'),
            'total_points': pd.array([6], dtype='int64'),
        })

    def test_exact_columns_and_dtypes_passes(self):
        df = self._make_df()
        assert validate_column_contract(
            df,
            ['player_id', 'gw', 'total_points'],
            {'player_id': 'int64', 'gw': 'int64', 'total_points': 'int64'},
        ) is None

    def test_extra_column_fails_with_name(self):
        df = self._make_df()
        df['extra_col'] = 0
        with pytest.raises(DALContractViolation) as exc_info:
            validate_column_contract(
                df,
                ['player_id', 'gw', 'total_points'],
                {},
            )
        assert 'extra_col' in str(exc_info.value)
        assert 'Extra' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'COLUMN_EXTRA'
        assert exc.validation == 'validate_column_contract'
        assert exc.n_violations == 1

    def test_missing_column_fails_with_name(self):
        df = pd.DataFrame({'player_id': pd.array([1], dtype='int64')})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_column_contract(df, ['player_id', 'gw'], {})
        assert 'gw' in str(exc_info.value)
        assert 'Missing' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'COLUMN_MISSING'
        assert exc.validation == 'validate_column_contract'
        assert exc.n_violations == 1

    def test_wrong_dtype_fails_with_detail(self):
        df = pd.DataFrame({'player_id': pd.array([1], dtype='int64')})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_column_contract(df, ['player_id'], {'player_id': 'float64'})
        assert 'player_id' in str(exc_info.value)
        assert 'int64' in str(exc_info.value)
        assert 'float64' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'DTYPE_MISMATCH'
        assert exc.validation == 'validate_column_contract'
        assert exc.n_violations == 1


# ---------------------------------------------------------------------------
# validate_null_semantics
# ---------------------------------------------------------------------------

class TestValidateNullSemantics:
    def test_never_null_no_nulls_passes(self):
        df = pd.DataFrame({'player_id': [1, 2, 3]})
        assert validate_null_semantics(df, {'player_id': 'never_null'}) is None

    def test_never_null_with_null_fails(self):
        df = pd.DataFrame({'player_id': [1, None, 3]})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_null_semantics(df, {'player_id': 'never_null'})
        assert 'player_id' in str(exc_info.value)
        assert 'never_null' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'NULL_SEMANTICS'
        assert exc.validation == 'validate_null_semantics'
        assert exc.n_violations == 1

    def test_null_if_bgw_correct_pattern_passes(self):
        df = pd.DataFrame({
            'is_bgw': [True, False],
            'fdr_avg': [None, 3.0],
        })
        assert validate_null_semantics(df, {'fdr_avg': 'null_if_bgw'}) is None

    def test_null_if_bgw_not_null_in_bgw_fails(self):
        df = pd.DataFrame({
            'is_bgw': [True, False],
            'fdr_avg': [3.0, 3.0],
        })
        with pytest.raises(DALContractViolation) as exc_info:
            validate_null_semantics(df, {'fdr_avg': 'null_if_bgw'})
        assert 'fdr_avg' in str(exc_info.value)
        assert 'BGW' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'NULL_SEMANTICS'
        assert exc.validation == 'validate_null_semantics'
        assert exc.n_violations == 1

    def test_null_if_bgw_null_in_non_bgw_fails(self):
        df = pd.DataFrame({
            'is_bgw': [True, False],
            'fdr_avg': [None, None],
        })
        with pytest.raises(DALContractViolation) as exc_info:
            validate_null_semantics(df, {'fdr_avg': 'null_if_bgw'})
        assert 'non-BGW' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'NULL_SEMANTICS'
        assert exc.validation == 'validate_null_semantics'
        assert exc.n_violations == 1

    def test_always_nullable_passes_regardless(self):
        df = pd.DataFrame({'was_home': [None, True, None]})
        assert validate_null_semantics(df, {'was_home': 'always_nullable'}) is None


# ---------------------------------------------------------------------------
# validate_time_continuity
# ---------------------------------------------------------------------------

class TestValidateTimeContinuity:
    def test_contiguous_gws_passes(self):
        df = pd.DataFrame({
            'player_id': [1] * 38,
            'gw': list(range(1, 39)),
        })
        assert validate_time_continuity(df) is None

    def test_gap_in_gws_fails_with_player_and_gw(self):
        gws = list(range(1, 15)) + list(range(16, 39))  # gap at 15
        df = pd.DataFrame({'player_id': [1] * len(gws), 'gw': gws})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_time_continuity(df)
        assert 'player_id=1' in str(exc_info.value)
        assert '15' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'TIME_GAP'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_time_continuity'
        assert exc.n_violations == 1

    def test_multiple_players_one_with_gap_fails(self):
        p1 = pd.DataFrame({'player_id': [1] * 38, 'gw': list(range(1, 39))})
        gws2 = list(range(1, 10)) + list(range(11, 39))  # gap at 10
        p2 = pd.DataFrame({'player_id': [2] * len(gws2), 'gw': gws2})
        df = pd.concat([p1, p2], ignore_index=True)
        with pytest.raises(DALContractViolation) as exc_info:
            validate_time_continuity(df)
        assert 'player_id=2' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'TIME_GAP'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_time_continuity'
        assert exc.n_violations == 1


# ---------------------------------------------------------------------------
# validate_row_count_invariant
# ---------------------------------------------------------------------------

class TestValidateRowCountInvariant:
    def test_exact_count_passes(self):
        df = pd.DataFrame({'x': range(38 * 5)})
        assert validate_row_count_invariant(df, 5, 38) is None

    def test_extra_row_fails(self):
        df = pd.DataFrame({'x': range(191)})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_row_count_invariant(df, 5, 38)
        assert '190' in str(exc_info.value)
        assert '191' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'ROW_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_row_count_invariant'
        assert exc.n_violations == 1

    def test_missing_row_fails(self):
        df = pd.DataFrame({'x': range(189)})
        with pytest.raises(DALContractViolation) as exc_info:
            validate_row_count_invariant(df, 5, 38)
        assert '190' in str(exc_info.value)
        assert '189' in str(exc_info.value)
        exc = exc_info.value
        assert exc.error_code == 'ROW_COUNT'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_row_count_invariant'
        assert exc.n_violations == 1


# ---------------------------------------------------------------------------
# validate_no_future_data
# ---------------------------------------------------------------------------

class TestValidateNoFutureData:
    # Contract: future GW rows must have NULL (pd.NA) performance — see DAL_CONTRACT.md Section 5
    _PERF_COLS = [
        "total_points", "minutes", "goals_scored", "assists", "clean_sheets",
        "yellow_cards", "red_cards", "saves", "bonus", "bps", "xg", "xa", "xgi",
    ]

    def _base_df(self):
        rows = []
        for p in [1, 2]:
            for g in range(1, 39):
                rows.append(dict(
                    player_id=p, gw=g,
                    total_points=None, minutes=None,
                    goals_scored=None, assists=None,
                    clean_sheets=None, yellow_cards=None, red_cards=None,
                    saves=None, bonus=None, bps=None,
                    xg=None, xa=None, xgi=None,
                ))
        return pd.DataFrame(rows)

    def test_reference_gw_none_always_passes(self):
        df = self._base_df()
        df.loc[df['gw'] > 20, 'total_points'] = 5
        assert validate_no_future_data(df, reference_gw=None) is None

    def test_future_rows_all_null_passes(self):
        # All future rows have NULL performance — no data exists for future GWs (correct)
        df = self._base_df()
        assert validate_no_future_data(df, reference_gw=20,
                                       performance_cols=self._PERF_COLS) is None

    def test_future_row_nonzero_fails_with_player_and_gw(self):
        df = self._base_df()
        df.loc[(df['player_id'] == 1) & (df['gw'] == 21), 'total_points'] = 5
        with pytest.raises(DALContractViolation) as exc_info:
            validate_no_future_data(df, reference_gw=20, performance_cols=self._PERF_COLS)
        msg = str(exc_info.value)
        assert 'total_points' in msg
        assert '21' in msg
        exc = exc_info.value
        assert exc.error_code == 'FUTURE_DATA'
        assert exc.layer == 'curated'
        assert exc.validation == 'validate_no_future_data'
        assert exc.n_violations == 1
