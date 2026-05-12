from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype, is_object_dtype, is_string_dtype

from analysis.dal.player_repo import (
    get_all_player_histories,
    get_fixtures,
    get_players,
)


CURATED_DATASET_NAME = "player_gameweek_v1"
CURATED_GRAIN = ("player_id", "gameweek")

CURATED_COLUMNS: list[str] = [
    "player_id",
    "gameweek",
    "player_name",
    "element_type",
    "team_id",
    "minutes",
    "starts",
    "total_points",
    "selected_count",
    "fixture_count",
    "home_fixture_count",
    "away_fixture_count",
    "latest_ingested_at",
]

SOURCE_TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "players": {
        "id": "integer",
        "web_name": "string",
        "element_type": "integer",
        "team": "integer",
    },
    "fixtures": {
        "id": "integer",
        "event": "integer",
        "team_h": "integer",
        "team_a": "integer",
    },
    "player_histories": {
        "element_id": "integer",
        "round": "integer",
        "fixture": "integer",
        "minutes": "integer",
        "starts": "integer",
        "total_points": "numeric",
        "selected": "numeric",
        "was_home": "integer",
        "ingested_at": "string",
    },
}


@dataclass(frozen=True)
class ContractCheck:
    status: str
    detail: str


def _matches_expected_type(series: pd.Series, expected: str) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return True
    if expected == "integer":
        return is_numeric_dtype(non_null)
    if expected == "numeric":
        return is_numeric_dtype(non_null)
    if expected == "string":
        return is_string_dtype(non_null) or is_object_dtype(non_null)
    raise ValueError(f"Unsupported expected type: {expected}")


def _check_schema(df: pd.DataFrame, schema: dict[str, str]) -> ContractCheck:
    missing = [column for column in schema if column not in df.columns]
    if missing:
        return ContractCheck("FAIL", f"missing columns: {missing}")

    invalid_types = [
        column
        for column, expected in schema.items()
        if not _matches_expected_type(df[column], expected)
    ]
    if invalid_types:
        return ContractCheck("FAIL", f"type mismatch columns: {invalid_types}")

    return ContractCheck("PASS", "required columns present with compatible types")


def _check_primary_key(df: pd.DataFrame, key_columns: list[str]) -> ContractCheck:
    null_rows = int(df[key_columns].isnull().any(axis=1).sum())
    duplicate_rows = int(df.duplicated(subset=key_columns).sum())
    if null_rows or duplicate_rows:
        return ContractCheck(
            "FAIL",
            f"null_key_rows={null_rows}, duplicate_key_rows={duplicate_rows}",
        )
    return ContractCheck("PASS", "primary key columns are non-null and unique")


def _check_subset(
    child: pd.Series,
    parent: pd.Series,
    label: str,
) -> ContractCheck:
    child_values = set(child.dropna().tolist())
    parent_values = set(parent.dropna().tolist())
    orphans = sorted(child_values - parent_values)
    if orphans:
        return ContractCheck("FAIL", f"{label} orphan_count={len(orphans)}")
    return ContractCheck("PASS", f"{label} has no orphan keys")


def _check_source_coverage(
    players: pd.DataFrame,
    fixtures: pd.DataFrame,
    histories: pd.DataFrame,
) -> ContractCheck:
    if players.empty or fixtures.empty or histories.empty:
        return ContractCheck(
            "FAIL",
            (
                f"row_counts players={len(players)}, fixtures={len(fixtures)}, "
                f"player_histories={len(histories)}"
            ),
        )

    fixture_gws = set(fixtures["event"].dropna().astype(int).tolist())
    history_gws = set(histories["round"].dropna().astype(int).tolist())
    uncovered_gws = sorted(history_gws - fixture_gws)
    if uncovered_gws:
        return ContractCheck(
            "FAIL",
            f"player_histories rounds missing in fixtures.event: {uncovered_gws}",
        )

    return ContractCheck(
        "PASS",
        (
            f"row_counts players={len(players)}, fixtures={len(fixtures)}, "
            f"player_histories={len(histories)}"
        ),
    )


def _overall_status(checks: list[ContractCheck]) -> str:
    return "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"


def validate_source_tables(db_path: Path) -> dict[str, object]:
    players = get_players(db_path).copy()
    fixtures = get_fixtures(db_path).copy()
    histories = get_all_player_histories(db_path).copy()

    schema_checks = {
        "players": _check_schema(players, SOURCE_TABLE_SCHEMAS["players"]),
        "fixtures": _check_schema(fixtures, SOURCE_TABLE_SCHEMAS["fixtures"]),
        "player_histories": _check_schema(
            histories,
            SOURCE_TABLE_SCHEMAS["player_histories"],
        ),
    }

    key_constraints = {
        "players_primary_key": _check_primary_key(players, ["id"]),
        "fixtures_primary_key": _check_primary_key(fixtures, ["id"]),
        "player_histories_primary_key": _check_primary_key(
            histories,
            ["element_id", "round", "fixture"],
        ),
    }

    coverage = {
        "source_row_coverage": _check_source_coverage(players, fixtures, histories),
    }

    referential_integrity = {
        "player_histories_element_id_to_players_id": _check_subset(
            histories["element_id"],
            players["id"],
            "player_histories.element_id -> players.id",
        ),
        "player_histories_fixture_to_fixtures_id": _check_subset(
            histories["fixture"],
            fixtures["id"],
            "player_histories.fixture -> fixtures.id",
        ),
    }

    all_checks = [
        *schema_checks.values(),
        *key_constraints.values(),
        *coverage.values(),
        *referential_integrity.values(),
    ]

    return {
        "dataset": CURATED_DATASET_NAME,
        "schema_checks": {
            name: check.__dict__ for name, check in schema_checks.items()
        },
        "key_constraints": {
            name: check.__dict__ for name, check in key_constraints.items()
        },
        "coverage": {
            name: check.__dict__ for name, check in coverage.items()
        },
        "referential_integrity": {
            name: check.__dict__ for name, check in referential_integrity.items()
        },
        "final_status": _overall_status(all_checks),
    }


def build_player_gameweek_v1(db_path: Path) -> pd.DataFrame:
    players = get_players(db_path).copy().rename(
        columns={
            "id": "player_id",
            "web_name": "player_name",
            "team": "team_id",
        }
    )
    fixtures = get_fixtures(db_path).copy().rename(
        columns={
            "id": "fixture_id",
            "event": "gameweek",
        }
    )
    histories = get_all_player_histories(db_path).copy()[
        [
            "element_id",
            "round",
            "fixture",
            "minutes",
            "starts",
            "total_points",
            "selected",
            "was_home",
            "ingested_at",
        ]
    ].rename(
        columns={
            "element_id": "player_id",
            "round": "gameweek",
            "fixture": "fixture_id",
            "selected": "selected_count",
        }
    )

    spine = (
        histories.merge(
            players[["player_id", "player_name", "element_type", "team_id"]],
            on="player_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            fixtures[["fixture_id", "gameweek"]],
            on=["fixture_id", "gameweek"],
            how="left",
            validate="many_to_one",
        )
    )

    curated = (
        spine.assign(
            home_fixture_count=spine["was_home"].fillna(0).astype(int),
            away_fixture_count=(1 - spine["was_home"].fillna(0).astype(int)),
        )
        .groupby(["player_id", "gameweek"], as_index=False)
        .agg(
            player_name=("player_name", "first"),
            element_type=("element_type", "first"),
            team_id=("team_id", "first"),
            minutes=("minutes", "sum"),
            starts=("starts", "sum"),
            total_points=("total_points", "sum"),
            selected_count=("selected_count", "max"),
            fixture_count=("fixture_id", "nunique"),
            home_fixture_count=("home_fixture_count", "sum"),
            away_fixture_count=("away_fixture_count", "sum"),
            latest_ingested_at=("ingested_at", "max"),
        )
        .sort_values(["player_id", "gameweek"], kind="stable")
        .reset_index(drop=True)
    )

    curated = curated[CURATED_COLUMNS]

    if curated.duplicated(subset=list(CURATED_GRAIN)).any():
        raise ValueError(f"{CURATED_DATASET_NAME} violates grain {CURATED_GRAIN}")

    return curated


def define_initial_state_variables(player_gameweek_v1: pd.DataFrame) -> pd.DataFrame:
    curated = player_gameweek_v1.sort_values(
        ["player_id", "gameweek"],
        kind="stable",
    ).copy()

    player_groups = curated.groupby("player_id", group_keys=False)

    curated["recent_starts"] = (
        player_groups["starts"]
        .rolling(window=3, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    curated["previous_minutes"] = player_groups["minutes"].shift(1)
    curated["minutes_trend"] = (
        curated["minutes"] - curated["previous_minutes"].fillna(curated["minutes"])
    )
    curated["home_away_flag"] = curated.apply(_derive_home_away_flag, axis=1)
    curated["fixture_context"] = curated["fixture_count"].map(
        {
            0: "BGW",
            1: "SGW",
            2: "DGW",
        }
    ).fillna("OTHER")

    return curated[
        [
            "player_id",
            "gameweek",
            "recent_starts",
            "minutes_trend",
            "home_away_flag",
            "fixture_context",
        ]
    ].copy()


def _derive_home_away_flag(row: pd.Series) -> str:
    fixture_count = int(row["fixture_count"])
    home_count = int(row["home_fixture_count"])
    away_count = int(row["away_fixture_count"])

    if fixture_count == 0:
        return "BGW"
    if home_count == fixture_count:
        return "HOME"
    if away_count == fixture_count:
        return "AWAY"
    return "MIXED"


def get_curated_schema_spec() -> dict[str, object]:
    return {
        "dataset": CURATED_DATASET_NAME,
        "grain": list(CURATED_GRAIN),
        "columns": CURATED_COLUMNS.copy(),
    }


def get_state_definitions() -> list[dict[str, str]]:
    return [
        {
            "feature_name": "recent_starts",
            "definition": "Rolling sum of starts over the current and prior two gameweeks at player grain.",
            "derivation_source": f"{CURATED_DATASET_NAME}.starts",
        },
        {
            "feature_name": "minutes_trend",
            "definition": "Current-gameweek minutes minus prior-gameweek minutes for the same player.",
            "derivation_source": f"{CURATED_DATASET_NAME}.minutes",
        },
        {
            "feature_name": "home_away_flag",
            "definition": "HOME if all current-gameweek fixtures are home, AWAY if all are away, MIXED if split, BGW if no fixture.",
            "derivation_source": (
                f"{CURATED_DATASET_NAME}.fixture_count, "
                f"{CURATED_DATASET_NAME}.home_fixture_count, "
                f"{CURATED_DATASET_NAME}.away_fixture_count"
            ),
        },
        {
            "feature_name": "fixture_context",
            "definition": "BGW for zero fixtures, SGW for one fixture, DGW for two fixtures, OTHER otherwise.",
            "derivation_source": f"{CURATED_DATASET_NAME}.fixture_count",
        },
    ]
