"""Input contracts for computed registry builds."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from domain.registry.schema import POPULATION_SCOPE_VALUES, POSITION_VALUES


@dataclass(frozen=True)
class PreparedDatasetContract:
    """Column and threshold contract for prepared registry-build datasets."""

    target_column: str = "total_points"
    position_column: str = "position"
    gameweek_column: str = "gw"
    player_column: str = "player_id"
    population_scope: str = "primary"
    min_rows_after_cutoff: int = 1
    min_non_null_signal_rows: int = 1
    allowed_population_scopes: frozenset[str] = POPULATION_SCOPE_VALUES
    allowed_positions: frozenset[str] = POSITION_VALUES


def normalize_signal_config(signals: Iterable[str] | None) -> tuple[str, ...]:
    """Validate and normalize configured signal columns."""
    if signals is None:
        raise ValueError("signal config must include at least one signal")

    signal_list = tuple(str(signal).strip() for signal in signals)
    if not signal_list:
        raise ValueError("signal config must include at least one signal")
    if any(not signal for signal in signal_list):
        raise ValueError("signal config must include at least one non-empty signal")

    duplicates = sorted({signal for signal in signal_list if signal_list.count(signal) > 1})
    if duplicates:
        raise ValueError(f"signal config has duplicate signals: {duplicates}")

    return signal_list


def validate_prepared_dataset(
    data: pd.DataFrame,
    signals: Iterable[str],
    data_cutoff_gw: int,
    contract: PreparedDatasetContract | None = None,
) -> pd.DataFrame:
    """Validate prepared analytical input and return rows at or before cutoff."""
    cfg = contract or PreparedDatasetContract()
    signal_list = normalize_signal_config(signals)

    if data_cutoff_gw <= 0:
        raise ValueError(f"data_cutoff_gw must be positive, got {data_cutoff_gw}")
    if cfg.population_scope not in cfg.allowed_population_scopes:
        raise ValueError(
            "invalid population_scope "
            f"{cfg.population_scope!r}; expected one of "
            f"{sorted(cfg.allowed_population_scopes)}"
        )
    if cfg.min_rows_after_cutoff < 1:
        raise ValueError("min_rows_after_cutoff must be at least 1")
    if cfg.min_non_null_signal_rows < 1:
        raise ValueError("min_non_null_signal_rows must be at least 1")

    required_columns = (
        cfg.target_column,
        cfg.position_column,
        cfg.gameweek_column,
        cfg.player_column,
        *signal_list,
    )
    missing = [column for column in required_columns if column not in data.columns]
    if missing:
        raise ValueError(f"prepared data missing required columns: {missing}")

    gameweeks = pd.to_numeric(data[cfg.gameweek_column], errors="coerce")
    if gameweeks.isna().any():
        raise ValueError(f"{cfg.gameweek_column} contains non-numeric gameweek values")

    positions = set(data[cfg.position_column].dropna().astype(str))
    invalid_positions = sorted(positions - set(cfg.allowed_positions))
    if invalid_positions:
        raise ValueError(f"prepared data contains invalid positions: {invalid_positions}")

    filtered = data.loc[gameweeks.le(data_cutoff_gw)].copy()
    if len(filtered) < cfg.min_rows_after_cutoff:
        raise ValueError(f"prepared data has insufficient rows at or before GW{data_cutoff_gw}: {len(filtered)}")

    sparse_signals = [
        signal for signal in signal_list if int(filtered[signal].notna().sum()) < cfg.min_non_null_signal_rows
    ]
    if sparse_signals:
        raise ValueError(
            f"prepared data has insufficient non-null signal rows at or before GW{data_cutoff_gw}: {sparse_signals}"
        )

    return filtered
