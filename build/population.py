"""Primary analytical population builder.

Assembles the governed analytical dataset from the curated player-gameweek
spine: filters to the primary population, maps position codes, and selects
governed signal columns.

Output contract:
  Grain:      (player_id, gw) unique
  Population: minutes >= MINUTES_THRESHOLD
  Columns:    player_id, gw, position, <GOVERNED_SIGNAL_COLUMNS>, total_points
"""

from __future__ import annotations

import pandas as pd


POSITION_CODE_MAP: dict[int, str] = {
    1: "GK",
    2: "DEF",
    3: "MID",
    4: "FWD",
}

MINUTES_THRESHOLD: int = 60

GOVERNED_SIGNAL_COLUMNS: tuple[str, ...] = (
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "goals_conceded",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "fdr_avg",
    "fdr_min",
    "fdr_max",
    "transfers_balance",
    "fixture_count",
    "was_home",
    "starts",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "ownership_count",
    "purchase_price",
    "transfers_in",
    "transfers_out",
)

OUTPUT_COLUMNS: tuple[str, ...] = (
    "player_id",
    "gw",
    "position",
    *GOVERNED_SIGNAL_COLUMNS,
    "total_points",
)


def build_prepared_dataset(
    spine: pd.DataFrame,
    data_cutoff_gw: int,
) -> pd.DataFrame:
    """Assemble the primary analytical population from a curated spine.

    Args:
        spine:          Player-gameweek spine from build_player_gameweek_spine().
                        Must contain player_id, gw, position_code, minutes,
                        total_points, and all GOVERNED_SIGNAL_COLUMNS.
        data_cutoff_gw: Upper GW bound (inclusive).

    Returns:
        DataFrame satisfying the output contract. Grain: (player_id, gw) unique.

    Raises:
        ValueError: if required columns are missing, GW bound is invalid,
                    or grain is violated after assembly.
    """
    if data_cutoff_gw <= 0:
        raise ValueError(f"data_cutoff_gw must be positive, got {data_cutoff_gw!r}")

    required = {"player_id", "gw", "position_code", "minutes", "total_points"} | set(
        GOVERNED_SIGNAL_COLUMNS
    )
    missing = required - set(spine.columns)
    if missing:
        raise ValueError(f"spine missing required columns: {sorted(missing)}")

    df = spine.loc[spine["gw"] <= data_cutoff_gw].copy()
    if df.empty:
        raise ValueError(
            f"no rows remain after applying data_cutoff_gw={data_cutoff_gw}; "
            "check that spine contains gameweeks at or before this value"
        )

    df = df.loc[df["minutes"] >= MINUTES_THRESHOLD].copy()
    if df.empty:
        raise ValueError(
            f"no rows remain after filtering minutes >= {MINUTES_THRESHOLD}; "
            f"data_cutoff_gw={data_cutoff_gw}"
        )

    df["position"] = df["position_code"].map(POSITION_CODE_MAP)
    unmapped = df["position"].isna().sum()
    if unmapped:
        bad_codes = sorted(df.loc[df["position"].isna(), "position_code"].unique().tolist())
        raise ValueError(
            f"{unmapped} rows have unrecognized position_code values: {bad_codes}"
        )

    duplicates = int(df[["player_id", "gw"]].duplicated().sum())
    if duplicates:
        raise ValueError(
            f"grain violation: {duplicates} duplicate (player_id, gw) pairs in prepared dataset"
        )

    output_cols = [col for col in OUTPUT_COLUMNS if col in df.columns]
    return df[output_cols].reset_index(drop=True)
