from __future__ import annotations

import pandas as pd


STATE_COLUMNS: list[str] = [
    "player_id",
    "gameweek",
    "fixture_count",
    "fixture_context",
    "home_away_profile",
    "minutes",
    "starts",
]


def _derive_fixture_context(fixture_count: int) -> str:
    if fixture_count == 0:
        return "BGW"
    if fixture_count == 1:
        return "SGW"
    if fixture_count == 2:
        return "DGW"
    return "DGW"


def _derive_home_away_profile(was_home_flags: object) -> str:
    if not isinstance(was_home_flags, list):
        raise TypeError(
            "player_gameweek_state requires was_home_flags to be list-valued: "
            f"actual_type={type(was_home_flags).__name__}"
        )
    if all(flag == 1 for flag in was_home_flags):
        return "HOME"
    if all(flag == 0 for flag in was_home_flags):
        return "AWAY"
    return "MIXED"


def _validate_player_gameweek_state(
    state_df: pd.DataFrame,
    spine_df: pd.DataFrame,
) -> None:
    if len(state_df) != len(spine_df):
        raise ValueError(
            "player_gameweek_state row count mismatch: "
            f"state_rows={len(state_df)}, spine_rows={len(spine_df)}"
        )

    null_key_rows = state_df.index[state_df[["player_id", "gameweek"]].isnull().any(axis=1)].tolist()
    if null_key_rows:
        raise ValueError(
            "player_gameweek_state contains null key values in (player_id, gameweek): "
            f"rows={null_key_rows}"
        )

    expected_fixture_count = spine_df["fixture_ids"].map(len)
    mismatched_rows = state_df.index[state_df["fixture_count"] != expected_fixture_count].tolist()
    if mismatched_rows:
        raise ValueError(
            "player_gameweek_state fixture_count mismatch against fixture_ids: "
            f"rows={mismatched_rows}"
        )


def build_player_gameweek_state(df: pd.DataFrame) -> pd.DataFrame:
    spine = df.copy(deep=True)

    fixture_count = spine["fixture_ids"].map(len)
    state = pd.DataFrame(
        {
            "player_id": spine["player_id"],
            "gameweek": spine["gameweek"],
            "fixture_count": fixture_count,
            "fixture_context": fixture_count.map(_derive_fixture_context),
            "home_away_profile": spine["was_home_flags"].map(_derive_home_away_profile),
            "minutes": spine["minutes"],
            "starts": spine["starts"],
        }
    ).loc[:, STATE_COLUMNS]

    _validate_player_gameweek_state(state, spine)
    return state
