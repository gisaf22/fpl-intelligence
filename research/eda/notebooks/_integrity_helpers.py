"""EDA-0 integrity helpers — rolling window, lag alignment, and activity filter checks."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


ROLLING_COLUMNS = [
    "player_id",
    "player_name",
    "gw",
    "total_points",
    "points_roll3",
    "points_roll5",
]
LAG_COLUMNS = [
    "player_id",
    "player_name",
    "gw",
    "total_points",
    "points_roll5",
]
_LAG_SENTINEL = -9999

GW_BLOCK_BOUNDARIES = {
    "early": (6, 14),
    "mid": (15, 24),
    "late": (25, 34),
}

POSITION_LABELS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


__all__ = [
    "GW_BLOCK_BOUNDARIES",
    "LAG_COLUMNS",
    "POSITION_LABELS",
    "ROLLING_COLUMNS",
    "analyze_activity_filter_removal",
    "check_activity_filter_gate",
    "check_lag_alignment",
    "check_rolling_windows",
    "select_verification_players",
    "build_findings_template",
]


def check_rolling_windows(
    state_all: pd.DataFrame,
    position_pick: dict[int, str],
    check_gws: list[int],
) -> dict[str, Any]:
    validation_gws = set()
    for gw in check_gws:
        validation_gws.update(range(max(1, gw - 5), gw + 1))
    validation_gws = sorted(validation_gws)

    validation_data = state_all[state_all["gw"].isin(validation_gws)].copy()

    availability = (
        validation_data.groupby(["position_code", "player_id", "player_name"], as_index=False)
        .agg(gw_count=("gw", "nunique"))
        .sort_values(["position_code", "player_id"])
    )

    verification_dfs = []
    for position_code, position_label in position_pick.items():
        candidates = availability[availability["position_code"] == position_code]
        if candidates.empty:
            raise ValueError(f"No candidate found for position_code={position_code}")
        selected = candidates.iloc[[0]].copy()
        selected["position_label"] = position_label
        verification_dfs.append(selected)
    verification_df = pd.concat(verification_dfs, ignore_index=True)

    verification_tables: list[pd.DataFrame] = []
    rolling_mismatches: list[pd.DataFrame] = []

    for player_id in verification_df["player_id"]:
        sample = _build_roll_validation_frame(
            state_all[state_all["player_id"] == player_id][ROLLING_COLUMNS]
        )
        sample = sample[sample["gw"].isin(validation_gws)].copy()
        verification_tables.append(sample)

        mismatches = sample[
            sample["gw"].isin(check_gws)
            & ~(sample["roll3_match"] & sample["roll5_match"])
        ]
        if not mismatches.empty:
            rolling_mismatches.append(mismatches)

    rolling_table = pd.concat(verification_tables, ignore_index=True)
    rolling_mismatch_count = sum(len(df) for df in rolling_mismatches)

    has_gaps = availability[availability["gw_count"] < len(validation_gws)]
    edge_case_table = pd.DataFrame()
    if not has_gaps.empty:
        edge_case_player = has_gaps.iloc[0]
        edge_case_sample = _build_roll_validation_frame(
            state_all[state_all["player_id"] == edge_case_player["player_id"]][ROLLING_COLUMNS]
        )
        edge_case_table = edge_case_sample[edge_case_sample["gw"].isin(validation_gws)].copy()

    return {
        "result": "PASS" if rolling_mismatch_count == 0 else "FAIL",
        "players_verified": verification_df[["player_id", "player_name", "position_label"]].to_dict("records"),
        "gws_checked": check_gws,
        "mismatches": rolling_mismatch_count,
        "verification_df": verification_df,
        "verification_table": rolling_table,
        "edge_case_table": edge_case_table,
    }


def check_lag_alignment(
    state_all: pd.DataFrame,
    verification_df: pd.DataFrame,
    check_gws: list[int],
) -> dict[str, Any]:
    next_cols = [col for col in state_all.columns if "next" in col.lower()]

    lag_tables: list[pd.DataFrame] = []
    lag_mismatches: list[pd.DataFrame] = []
    for player in verification_df.to_dict("records"):
        sample = _build_lag_alignment_frame(
            state_all[state_all["player_id"] == player["player_id"]][LAG_COLUMNS]
        )
        sample = sample[sample["gw"].isin(check_gws)].copy()
        lag_tables.append(sample)
        bad = sample[~sample["shift_matches_merge"].fillna(True)]
        if not bad.empty:
            lag_mismatches.append(bad)

    lag_table = pd.concat(lag_tables, ignore_index=True)
    lag_mismatch_count = sum(len(df) for df in lag_mismatches)
    lag_approach = "shift construction" if not next_cols else "next_gw column present"
    return {
        "result": "PASS" if lag_approach == "shift construction" and lag_mismatch_count == 0 else "FAIL",
        "approach": lag_approach,
        "players_verified": verification_df[["player_id", "player_name"]].to_dict("records"),
        "mismatches": lag_mismatch_count,
        "next_cols": next_cols,
        "lag_table": lag_table,
    }


def check_activity_filter_gate(
    state: pd.DataFrame,
    activity_min: int = 45,
) -> dict[str, Any]:
    filtered = state[state["minutes"] >= activity_min].copy()
    filtered["gw_block"] = filtered["gw"].map(_assign_block)
    filtered["position_label"] = filtered["position_code"].map(POSITION_LABELS)

    counts = (
        filtered.groupby(["position_label", "gw_block"])
        .size()
        .unstack("gw_block")
        .reindex(columns=["early", "mid", "late"])
        .fillna(0)
        .astype(int)
    )

    empty_cells = int((counts == 0).sum().sum())
    return {
        "result": "FAIL" if empty_cells > 0 else "PASS",
        "activity_min": activity_min,
        "counts_table": counts,
        "empty_cells": empty_cells,
    }


def analyze_activity_filter_removal(
    state: pd.DataFrame,
    activity_min: int = 45,
) -> dict[str, Any]:
    filtered = state[state["minutes"] >= activity_min].copy()
    filtered["gw_block"] = filtered["gw"].map(_assign_block)
    filtered["position_label"] = filtered["position_code"].map(POSITION_LABELS)

    counts = (
        filtered.groupby(["position_label", "gw_block"])
        .size()
        .unstack("gw_block")
        .reindex(columns=["early", "mid", "late"])
        .fillna(0)
        .astype(int)
    )

    total_unfiltered = len(state)
    total_filtered = len(filtered)
    removed = total_unfiltered - total_filtered
    removed_pct = 100 * removed / total_unfiltered if total_unfiltered > 0 else 0.0

    return {
        "activity_min": activity_min,
        "total_unfiltered": total_unfiltered,
        "total_filtered": total_filtered,
        "removed": removed,
        "removed_pct": round(removed_pct, 1),
        "counts_table": counts,
        "filtered": filtered,
    }


def select_verification_players(
    state_all: pd.DataFrame,
    position_pick: dict[int, str],
    history_start: int = 1,
    history_end: int = 25,
) -> pd.DataFrame:
    full_history = state_all[state_all["gw"].between(history_start, history_end)].copy()
    expected_gw_count = history_end - history_start + 1
    availability = (
        full_history.groupby(["position_code", "player_id", "player_name"], as_index=False)
        .agg(
            gw_count=("gw", "nunique"),
            min_gw=("gw", "min"),
            max_gw=("gw", "max"),
        )
        .sort_values(["position_code", "player_id"])
    )
    eligible = availability[
        (availability["gw_count"] == expected_gw_count)
        & (availability["min_gw"] == history_start)
        & (availability["max_gw"] == history_end)
    ]

    rows: list[dict[str, Any]] = []
    for position_code, position_label in position_pick.items():
        candidates = eligible[eligible["position_code"] == position_code]
        if candidates.empty:
            raise ValueError(
                f"No continuous-history candidate found for position_code={position_code}"
            )
        chosen = candidates.iloc[0]
        rows.append({
            "player_id": int(chosen["player_id"]),
            "player_name": chosen["player_name"],
            "position_code": int(chosen["position_code"]),
            "position_label": position_label,
        })

    return pd.DataFrame(rows)


def build_findings_template(
    results: dict[str, dict[str, Any]],
    overall_result: str,
    gate_decision: str,
) -> list[str]:
    q01 = results["Q0.1"]
    q02 = results["Q0.2"]
    q03 = results["Q0.3"]
    lines = [
        "## EDA-0 — Study Construction Integrity",
        "",
        f"Overall result: {overall_result}",
        "",
        (
            "Q0.1 Rolling window construction: "
            f"players verified={q01['players_verified']}, "
            f"GWs checked={q01['gws_checked']}, "
            f"mismatches={q01['mismatches']}, "
            f"result={q01['result']}"
        ),
        (
            "Q0.2 Lag alignment: "
            f"approach={q02['approach']}, "
            f"players verified={q02['players_verified']}, "
            f"mismatches={q02['mismatches']}, "
            f"result={q02['result']}"
        ),
        (
            "Q0.3 Activity filter gate check: "
            f"filter=minutes>={q03['activity_min']}, "
            f"empty cells={q03['empty_cells']}, "
            f"result={q03['result']}"
        ),
        "",
        f"Gate decision: {gate_decision}",
    ]
    return lines


def _assign_block(gw: int) -> str:
    if gw <= 14:
        return "early"
    elif gw <= 24:
        return "mid"
    return "late"


def _build_roll_validation_frame(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.sort_values("gw").reset_index(drop=True).copy()
    frame["expected_roll3"] = frame["total_points"].shift(1).rolling(3, min_periods=1).mean()
    frame["expected_roll5"] = frame["total_points"].shift(1).rolling(5, min_periods=1).mean()
    frame["roll3_match"] = np.isclose(frame["points_roll3"], frame["expected_roll3"])
    frame["roll5_match"] = np.isclose(frame["points_roll5"], frame["expected_roll5"])
    return frame


def _build_lag_alignment_frame(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.sort_values("gw").reset_index(drop=True).copy()
    next_points_lookup = frame.set_index("gw")["total_points"]
    frame["next_gw"] = frame["gw"] + 1
    frame["merged_next_gw_total_points"] = frame["next_gw"].map(next_points_lookup)
    frame["derived_next_gw_total_points"] = frame["total_points"].shift(-1)
    frame["shift_matches_merge"] = frame["derived_next_gw_total_points"].fillna(_LAG_SENTINEL).eq(
        frame["merged_next_gw_total_points"].fillna(_LAG_SENTINEL)
    )
    return frame
