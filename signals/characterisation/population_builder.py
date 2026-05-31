"""Internal registry population builder."""

from __future__ import annotations

import pandas as pd

from domain.fpl_scoring import CLEAN_SHEET_MIN_MINUTES
from population.populations import filter_performance
from signals.characterisation.population import (
    REGISTRY_BUILD_INPUT_COLUMNS,
    OUTPUT_COLUMNS,
    POSITION_CODE_MAP,
)


def _build_registry_population(
    spine: pd.DataFrame,
    data_cutoff_gw: int,
) -> pd.DataFrame:
    """Assemble the primary analytical population from a curated spine.

    Args:
        spine:          Player-gameweek spine from build_player_gameweek_spine().
                        Must contain player_id, gw, position_code, minutes,
                        total_points, and all REGISTRY_BUILD_INPUT_COLUMNS.
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
        REGISTRY_BUILD_INPUT_COLUMNS
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

    df = filter_performance(df)
    if df.empty:
        raise ValueError(
            f"no rows remain after filtering minutes >= {CLEAN_SHEET_MIN_MINUTES}; "
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
