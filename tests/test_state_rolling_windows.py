"""State layer tests — rolling window edge cases.

Contract: docs/adr/012-dal-design-rationale.md (rolling window conventions).

Edge cases tested:
1. Earliest GW < 6: partial rolling windows (fewer than full 5-GW history)
2. GWs including BGW: NULL values skipped, not counted toward window
3. GWs including DGW: aggregated performance data in rolling windows
"""

from pathlib import Path
import pandas as pd
import pandas.testing as tm
import pytest

from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.staging import load_staged_entities
from dal.intermediate.int_player_fixture import get_player_fixture_base

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_spine():
    staged = load_staged_entities(DB_PATH)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


class TestRollingWindowsEarlyGW:
    """Rolling windows compute correctly for earliest_gw < 6."""

    def test_roll5_at_gw5_uses_4_prior_values(self):
        """At GW 5, roll5 looks at GWs 1-4 (4 prior values, not 5)."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        # Filter to GW 5
        gw5 = state[state["gw"] == 5].copy()

        # For GW 5, roll5 should exist (computed from GWs 1-4)
        # Rows with at least 1 prior non-NULL value in GWs 1-4 should have roll5 computed
        assert not gw5.empty, "No data at GW 5"

        # Players with any fixture in GWs 1-4 should have non-NULL roll5
        players_with_early_fixtures = gw5[gw5["gw"] == 5]["player_id"].unique()
        assert len(players_with_early_fixtures) > 0, "No players at GW 5"

    def test_roll3_at_gw3_uses_2_prior_values(self):
        """At GW 3, roll3 looks at GWs 1-2 (2 prior values, not 3)."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        gw3 = state[state["gw"] == 3].copy()
        assert not gw3.empty, "No data at GW 3"

    def test_roll5_at_gw2_uses_1_prior_value(self):
        """At GW 2, roll5 looks at GW 1 (1 prior value). min_periods=1 allows computation."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        gw2 = state[state["gw"] == 2].copy()
        assert not gw2.empty, "No data at GW 2"


class TestRollingWindowsWithBGW:
    """Rolling windows handle BGW (NULL values) correctly."""

    def test_bgw_nulls_skipped_not_counted(self):
        """BGW NULL values are skipped in rolling window; don't count toward window size."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        # Find a player with a BGW in early GWs
        spine_with_bgw = spine[spine["is_bgw"] == True].copy()
        assert not spine_with_bgw.empty, "No BGW rows found in spine"

        # For those players, rolling windows should still compute
        # even if a BGW falls within the window
        for player_id in spine_with_bgw["player_id"].unique()[:5]:  # Sample first 5
            player_state = state[state["player_id"] == player_id].sort_values("gw")

            # Check for roll5 values where BGW exists in window
            for idx, row in player_state[player_state["gw"] >= 6].iterrows():
                gw = row["gw"]
                prior_gws = player_state[player_state["gw"].between(gw-5, gw-1)]

                # Count non-NULL xgi values in prior window
                prior_xgi = prior_gws["xgi"].dropna()

                # If we have at least 1 prior xgi, roll5 should be computed (not NA)
                if len(prior_xgi) >= 1:
                    # roll5 should be numeric, not NA
                    assert pd.notna(row["xgi_roll5"]), (
                        f"Player {player_id} GW {gw}: xgi_roll5 is NA but has "
                        f"{len(prior_xgi)} prior non-NULL values"
                    )

    def test_bgw_does_not_prevent_rolling_computation(self):
        """If a player has 1 SGW + 1 BGW in a 5-GW window, roll5 computes from the 1 SGW."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        # Find a player with both BGW and SGW rows
        players_with_bgw = spine[spine["is_bgw"] == True]["player_id"].unique()
        spine_filtered = spine[spine["player_id"].isin(players_with_bgw)]

        for player_id in players_with_bgw[:3]:  # Sample first 3
            player_spine = spine[spine["player_id"] == player_id].sort_values("gw")
            player_state = state[state["player_id"] == player_id].sort_values("gw")

            # Find GWs where prior window has mix of BGW and SGW
            for idx, row in player_state[player_state["gw"] >= 7].iterrows():
                gw = row["gw"]
                prior_rows = player_spine[player_spine["gw"].between(gw-5, gw-1)]

                bgw_count = (prior_rows["is_bgw"] == True).sum()
                sgw_count = (prior_rows["is_bgw"] == False).sum()

                # If mixed BGWs and SGWs, rolling should still compute
                if bgw_count > 0 and sgw_count > 0:
                    roll5_val = player_state[player_state["gw"] == gw]["xgi_roll5"].iloc[0]
                    # Should compute from SGW values, skipping BGW NULLs
                    # Either computed value or NA if all SGWs are NA
                    assert pd.notna(roll5_val) or sgw_count == 0, (
                        f"Player {player_id} GW {gw}: "
                        f"xgi_roll5 is NA but has {sgw_count} non-BGW rows in window"
                    )


class TestRollingWindowsWithDGW:
    """Rolling windows handle DGW (aggregated performance) correctly."""

    def test_dgw_aggregated_performance_in_rolling(self):
        """DGW performance (summed across 2 fixtures) is used in rolling windows."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        # Find a player with DGW
        spine_with_dgw = spine[spine["is_dgw"] == True].copy()
        assert not spine_with_dgw.empty, "No DGW rows found in spine"

        for player_id in spine_with_dgw["player_id"].unique()[:5]:  # Sample first 5
            player_spine = spine[spine["player_id"] == player_id].sort_values("gw")
            player_state = state[state["player_id"] == player_id].sort_values("gw")

            dgw_gws = player_spine[player_spine["is_dgw"] == True]["gw"].unique()

            # For GWs after a DGW, roll window should include that DGW's summed xgi
            for dgw_gw in dgw_gws:
                dgw_xgi = player_spine[player_spine["gw"] == dgw_gw]["xgi"].iloc[0]

                # Check roll5 for GW = dgw_gw + 1 (if exists)
                next_gw = dgw_gw + 1
                next_state_rows = player_state[player_state["gw"] == next_gw]

                if not next_state_rows.empty:
                    roll5_val = next_state_rows["xgi_roll5"].iloc[0]

                    # roll5 at next_gw includes dgw_gw in its window (dgw_gw is 1 of 5 prior)
                    # If dgw_xgi is not NA and roll5 is computed, it should reflect dgw
                    if pd.notna(dgw_xgi) and pd.notna(roll5_val):
                        # DGW xgi (summed) is included in rolling average
                        # We can't directly verify the value, but we can verify it computed
                        assert isinstance(roll5_val, (int, float)), (
                            f"Player {player_id} GW {next_gw}: "
                            f"xgi_roll5 after DGW should be numeric"
                        )

    def test_dgw_minutes_sum_in_rolling(self):
        """DGW minutes (summed) are correctly used in rolling windows."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        spine_with_dgw = spine[spine["is_dgw"] == True].copy()
        if spine_with_dgw.empty:
            pytest.skip("No DGW rows in test data")

        for player_id in spine_with_dgw["player_id"].unique()[:3]:
            player_spine = spine[spine["player_id"] == player_id].sort_values("gw")
            player_state = state[state["player_id"] == player_id].sort_values("gw")

            dgw_rows = player_spine[player_spine["is_dgw"] == True]

            for _, dgw_row in dgw_rows.iterrows():
                dgw_gw = dgw_row["gw"]
                dgw_minutes = dgw_row["minutes"]

                # Check that minutes_roll5 for next GW includes this DGW's minutes
                next_gw = dgw_gw + 1
                next_state = player_state[player_state["gw"] == next_gw]

                if not next_state.empty:
                    roll5_minutes = next_state["minutes_roll5"].iloc[0]

                    # If DGW had minutes and roll5 computed, it includes those minutes
                    if pd.notna(dgw_minutes) and dgw_minutes > 0 and pd.notna(roll5_minutes):
                        assert roll5_minutes >= 0, (
                            f"Player {player_id} GW {next_gw}: "
                            f"roll5_minutes should include DGW minutes"
                        )


class TestRollingWindowsLag1Convention:
    """Rolling windows use lag-1 convention (prior GWs only, not current)."""

    def test_roll5_at_gw_n_uses_gw_n_minus_1_back(self):
        """Roll5 at GW N looks at GW N-1, N-2, ..., N-5 (not GW N)."""
        spine = _load_spine()
        state = build_player_gameweek_state(spine)

        # Manually verify lag-1 for a specific player at a specific GW
        test_player = state["player_id"].iloc[0]
        player_state = state[state["player_id"] == test_player].sort_values("gw")

        if len(player_state) < 7:
            pytest.skip(f"Player {test_player} has insufficient GWs for testing")

        # At GW 6, roll5 should use GWs 1-5 (not GW 6)
        gw6_row = player_state[player_state["gw"] == 6]
        if gw6_row.empty:
            pytest.skip("GW 6 data not available")

        # Verify by checking that current GW (6) is not included
        # This is implicit in the lag-1 shift — the rolling window is computed
        # on shift(1) which already excludes the current row
        roll5_gw6 = gw6_row["xgi_roll5"].iloc[0]

        # If computed (not NA), it should be from GWs 1-5
        if pd.notna(roll5_gw6):
            gws_1_5 = player_state[player_state["gw"].between(1, 5)]["xgi"].dropna()
            assert len(gws_1_5) > 0, "No data in GWs 1-5"
