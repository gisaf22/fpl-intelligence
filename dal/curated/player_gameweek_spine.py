"""Curated DAL layer — player gameweek spine build logic."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from dal.intermediate.player_fixture import get_player_fixture_base
from dal.curated.gameweek_context import get_gameweek_context
from dal.exceptions import DALContractViolation
from dal.curated.contracts import (
    DTYPES,
    FIRST_COLS,
    FIRST_COL_SEMANTICS,
    NULL_RULES,
    PERFORMANCE_COLS,
    SPINE_COLS,
    SUM_COLS,
)
from dal.validation import (
    validate_grain_uniqueness,
    validate_row_completeness,
    validate_column_contract,
    validate_row_count_invariant,
    validate_no_future_data,
    validate_time_continuity,
    validate_bgw_correctness,
    validate_dgw_correctness,
    validate_join_safety,
    validate_null_semantics,
)

logger = logging.getLogger(__name__)


def _assert_invariant_per_gw_columns(df: pd.DataFrame) -> None:
    """Assert that invariant_per_gw columns have exactly one distinct value per (player_id, gw).

    Runs before aggregation. Raises DALContractViolation if any invariant_per_gw column
    has more than one distinct value within a (player_id, gw) group, which would indicate
    an upstream API change or join error.
    """
    invariant_cols = [
        c for c, s in FIRST_COL_SEMANTICS.items()
        if s == "invariant_per_gw" and c in df.columns
    ]
    for col in invariant_cols:
        max_unique = df.groupby(["player_id", "gw"])[col].nunique().max()
        if max_unique > 1:
            violators = df.groupby(["player_id", "gw"])[col].nunique()
            violators = violators[violators > 1].reset_index()
            raise DALContractViolation(
                f"invariant_per_gw violated for column '{col}': "
                f"{len(violators)} (player_id, gw) groups have >1 distinct value. "
                f"First violators:\n{violators.head(5)}",
                layer="curated",
                validation="_assert_invariant_per_gw_columns",
                n_violations=len(violators),
                error_code="GRAIN_DUPLICATE",
            )


def _aggregate_to_gw_grain(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fixture-grain frame to (player_id, gw) grain in a single groupby pass.

    Asserts invariant_per_gw columns before aggregation and sorts by canonical PK first
    to ensure deterministic FIRST_COLS selection regardless of staging row order (SC-9).
    """
    _assert_invariant_per_gw_columns(df)
    # SC-9: explicit sort ensures FIRST_COLS take-first is deterministic
    df = df.sort_values(["player_id", "gw", "fixture_id"]).reset_index(drop=True)
    grouped = df.groupby(["player_id", "gw"])

    base = grouped.agg(
        {**{col: "first" for col in FIRST_COLS}, **{col: "sum" for col in SUM_COLS}}
    ).reset_index()

    extra = grouped.agg(
        fixture_count=("fixture_id", "count"),
        fdr_avg=("fixture_difficulty", "mean"),
        fdr_min=("fixture_difficulty", "min"),
        fdr_max=("fixture_difficulty", "max"),
        in_dreamteam=("in_dreamteam", "max"),
    ).reset_index()
    extra["fdr_avg"] = extra["fdr_avg"].astype("Float64")
    extra["fdr_min"] = extra["fdr_min"].astype("Float64")
    extra["fdr_max"] = extra["fdr_max"].astype("Float64")

    return base.merge(extra, on=["player_id", "gw"])


def _build_player_info(df: pd.DataFrame) -> pd.DataFrame:
    """Extract per-player attributes at each GW for BGW team_id lookup.

    Returns a frame indexed by (player_id, gw) covering all non-BGW GWs. Used in
    _apply_bgw_defaults to look up the most recent pre-BGW team for each BGW row
    (BGW team_id semantic rule — DAL_CONTRACT.md Section 5).

    Columns returned: player_name, position_code, position_label, team_id, purchase_price.
    The index is reset; caller uses merge-as-of to find the last known state per player.
    """
    return (
        df.sort_values(["player_id", "gw"])
        [["player_id", "gw", "player_name", "position_code", "position_label", "team_id", "purchase_price"]]
        .reset_index(drop=True)
    )


def _build_full_spine(player_universe: list[int], gw_range: list[int]) -> pd.DataFrame:
    """Construct the cartesian product of all players × all gameweeks."""
    return pd.DataFrame(
        [(pid, gw) for pid in player_universe for gw in gw_range],
        columns=["player_id", "gw"],
    )


def _join_gw_context(aggregated: pd.DataFrame, gw_context: pd.DataFrame) -> pd.DataFrame:
    """Join gameweek-level metadata onto the GW-grain aggregated frame."""
    n_before = len(aggregated)
    result = aggregated.merge(gw_context, on="gw", how="left")
    validate_join_safety(
        left_n=n_before,
        right_n=len(gw_context),
        result_n=len(result),
        join_type="left",
        description="aggregated × gameweek context",
    )
    return result


def _apply_bgw_defaults(
    result: pd.DataFrame,
    bgw_mask: pd.Series,
    player_info: pd.DataFrame,
) -> pd.DataFrame:
    """Fill BGW rows with correct defaults — zeros for admin columns, NULL for performance.

    player_info is a sorted (player_id, gw) frame from non-BGW GWs. For each BGW row,
    we find the most recent non-BGW GW at or before that GW per player (merge-as-of),
    giving causally correct team_id per the BGW team_id rule in DAL_CONTRACT.md.
    """
    result.loc[bgw_mask, "fixture_count"] = 0
    result.loc[bgw_mask, "is_dgw"] = False
    result.loc[bgw_mask, "home_count"] = 0
    result.loc[bgw_mask, "away_count"] = 0
    result.loc[bgw_mask, "ownership_count"] = 0
    result.loc[bgw_mask, "in_dreamteam"] = 0

    for col in SUM_COLS:
        if col in result.columns:
            result.loc[bgw_mask, col] = pd.NA if col in PERFORMANCE_COLS else 0

    # transfers_in/out/balance are GW-grain in the source — no record exists for a BGW player
    for col in ("transfers_in", "transfers_out", "transfers_balance"):
        result.loc[bgw_mask, col] = 0

    # Per-BGW-row lookup: causally correct identity columns per BGW row.
    # Strategy:
    #   1. Backward: most recent non-BGW GW at or before bgw_gw (temporally causal).
    #   2. Forward fallback: first non-BGW GW after bgw_gw for players with no prior history
    #      (e.g. mid-season joiners whose first GW is a BGW of their new team). This is the
    #      best available attribution when no prior fixture exists — still correct for position
    #      and name, and approximately correct for team (first known team).
    attr_cols = ["player_name", "position_code", "position_label", "team_id", "purchase_price"]
    bgw_rows = result.loc[bgw_mask, ["player_id", "gw"]].copy()
    lookup = player_info[["player_id", "gw"] + attr_cols].rename(columns={"gw": "gw_played"})

    # Step 1 — backward lookup
    merged_back = bgw_rows.reset_index().merge(lookup, on="player_id", how="left")
    candidates_back = merged_back[merged_back["gw_played"] <= merged_back["gw"]]
    if not candidates_back.empty:
        best_back = candidates_back.loc[
            candidates_back.groupby(["index", "player_id", "gw"])["gw_played"].idxmax()
        ].set_index("index")
        for col in attr_cols:
            if col in result.columns and col in best_back.columns:
                result.loc[bgw_mask, col] = best_back.reindex(result.index[bgw_mask])[col].values

    # Step 2 — forward fallback for any BGW rows still missing team_id after backward lookup
    # (players whose BGW precedes their first fixture — no causal prior team available)
    still_missing = bgw_mask & result["team_id"].isna()
    if still_missing.any():
        bgw_missing_rows = result.loc[still_missing, ["player_id", "gw"]].copy()
        merged_fwd = bgw_missing_rows.reset_index().merge(lookup, on="player_id", how="left")
        candidates_fwd = merged_fwd[merged_fwd["gw_played"] >= merged_fwd["gw"]]
        if not candidates_fwd.empty:
            best_fwd = candidates_fwd.loc[
                candidates_fwd.groupby(["index", "player_id", "gw"])["gw_played"].idxmin()
            ].set_index("index")
            for col in attr_cols:
                if col in result.columns and col in best_fwd.columns:
                    result.loc[still_missing, col] = best_fwd.reindex(
                        result.index[still_missing]
                    )[col].values

    return result


def _cast_and_validate(
    result: pd.DataFrame,
    n_players: int,
    n_gws: int,
    max_gw: int,
) -> pd.DataFrame:
    """Cast all columns to declared dtypes and run full contract validation suite."""
    for col, dtype in DTYPES.items():
        result[col] = result[col].astype(dtype)
    result = result.reset_index(drop=True)

    validate_column_contract(result, SPINE_COLS, DTYPES)
    validate_grain_uniqueness(result, "player_gameweek_spine")
    validate_row_completeness(result,
        result["player_id"].unique(), sorted(result["gw"].unique()))
    validate_row_count_invariant(result, n_players=n_players, n_gws=n_gws)
    validate_time_continuity(result)
    validate_no_future_data(result, reference_gw=max_gw, performance_cols=PERFORMANCE_COLS)
    validate_bgw_correctness(result)
    validate_dgw_correctness(result)
    validate_null_semantics(result, NULL_RULES)

    return result


def build_player_gameweek_spine(db_path: Path) -> pd.DataFrame:
    """Build the canonical (player_id, gw) spine with explicit BGW rows.

    Every player appears in every GW in the observed range. BGW rows have fixture_count=0
    and is_bgw=True with NULL performance columns. DGW rows have fixture_count=2, is_dgw=True.
    """
    df = get_player_fixture_base(db_path)
    # player_info: non-BGW rows sorted by (player_id, gw) for merge_asof BGW lookup
    player_info = _build_player_info(df)

    df["home_count"] = (df["was_home"] == 1).astype("int64")
    df["away_count"] = (df["was_home"] == 0).astype("int64")

    aggregated = _aggregate_to_gw_grain(df)
    # was_home is ambiguous for DGW — NULL for multi-fixture rows per contract Section 5
    aggregated["is_dgw"] = aggregated["fixture_count"] >= 2
    aggregated["was_home"] = aggregated["was_home"].astype("boolean")
    aggregated.loc[aggregated["is_dgw"], "was_home"] = pd.NA

    gw_context = get_gameweek_context(db_path)

    min_gw = int(df["gw"].min())
    max_gw = int(df["gw"].max())
    gw_range = list(range(min_gw, max_gw + 1))

    missing_gws = set(gw_range) - set(gw_context["gw"])
    if missing_gws:
        raise DALContractViolation(
            f"Events table is missing {len(missing_gws)} GW(s) required by fixture history: "
            f"{sorted(missing_gws)}. Spine cannot be built with incomplete GW context.",
            layer="curated",
            validation="build_player_gameweek_spine",
            n_violations=len(missing_gws),
            error_code="ROW_COUNT",
        )

    player_universe = sorted(df["player_id"].unique().tolist())
    logger.info(
        "Building spine: %d players × %d GWs (GW%d–GW%d)",
        len(player_universe), len(gw_range), min_gw, max_gw,
    )

    spine = _build_full_spine(player_universe, gw_range)
    result = spine.merge(aggregated, on=["player_id", "gw"], how="left")
    validate_join_safety(
        left_n=len(spine),
        right_n=len(aggregated),
        result_n=len(result),
        join_type="left",
        description="spine × fixture aggregation",
    )

    # Join gw_context onto the full spine so BGW rows also get gameweek metadata
    result = _join_gw_context(result, gw_context)

    bgw_mask = result["fixture_count"].isna()
    result = _apply_bgw_defaults(result, bgw_mask, player_info)
    result["is_bgw"] = result["fixture_count"] == 0

    assert not (result["is_bgw"] & result["is_dgw"]).any(), \
        "is_bgw and is_dgw are mutually exclusive — logic error in spine construction"

    n_bgw = int(result["is_bgw"].sum())
    n_dgw = int(result["is_dgw"].sum())
    logger.info("Spine built: %d BGW rows, %d DGW rows", n_bgw, n_dgw)

    result = _cast_and_validate(result, len(player_universe), len(gw_range), max_gw)
    return result[SPINE_COLS]
