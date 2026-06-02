"""Grain uniqueness validation — asserts no duplicate rows exist for the declared grain.

Callers pass either a dataset_name (resolved from GRAIN_CONTRACTS registry) or explicit
grain_cols + layer_name. Using dataset_name is preferred — it prevents callers from
specifying the wrong grain and keeps grain declarations centralised.
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd

from dal.exceptions import DALContractViolation


class GrainContract(TypedDict):
    pk: list[str]


GRAIN_CONTRACTS: dict[str, GrainContract] = {
    "staging_players": {"pk": ["player_id"]},
    "staging_player_histories": {"pk": ["player_id", "fixture_id"]},
    "staging_fixtures": {"pk": ["fixture_id"]},
    "staging_teams": {"pk": ["team_id"]},
    "staging_events": {"pk": ["gw"]},
    "staging_element_types": {"pk": ["position_code"]},
    "gameweek_context": {"pk": ["gw"]},
    "player_fixture_base": {"pk": ["player_id", "gw", "fixture_id"]},
    "player_gameweek_spine": {"pk": ["player_id", "gw"]},
    "player_gameweek_state": {"pk": ["player_id", "gw"]},
}


def validate_grain_uniqueness(
    df: pd.DataFrame,
    dataset_name_or_cols: str | list[str],
    layer_name: str | None = None,
) -> None:
    """Assert no duplicate rows for the declared grain.

    Args:
        df: DataFrame to check.
        dataset_name_or_cols: Either a string dataset_name (resolved from GRAIN_CONTRACTS)
            or a list of grain column names (legacy — prefer dataset_name).
        layer_name: Optional descriptive name for error messages (used when grain_cols
            are passed directly; ignored when dataset_name is passed).
    """
    if isinstance(dataset_name_or_cols, str):
        dataset_name = dataset_name_or_cols
        if dataset_name not in GRAIN_CONTRACTS:
            raise ValueError(
                f"Unknown dataset_name {dataset_name!r}. "
                f"Register it in dal/validation/grain.py before calling validate_grain_uniqueness."
            )
        grain_cols = GRAIN_CONTRACTS[dataset_name]["pk"]
        label = dataset_name
    else:
        grain_cols = list(dataset_name_or_cols)
        label = layer_name or ", ".join(grain_cols)

    dupes = df.groupby(grain_cols).size().reset_index(name="count").query("count > 1")
    if len(dupes) != 0:
        raise DALContractViolation(
            message=(
                f"{label} grain violation: {len(dupes)} duplicate ({', '.join(grain_cols)}) pairs\n{dupes.head(10)}"
            ),
            validation="validate_grain_uniqueness",
            n_violations=len(dupes),
            error_code="GRAIN_DUPLICATE",
        )
