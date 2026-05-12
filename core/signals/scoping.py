"""Exposure-aware signal scoping — dual-scope summaries, exposure sensitivity, preferred population,
and EDA-2 signal registry assembly."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from core.signals.profiling import (
    BINARY_SIGNALS,
    POSITION_MAP,
    compute_block_variance,
    compute_variance_flags,
)


SIGNAL_FAMILY: dict[str, str] = {
    "minutes":            "exposure",
    "starts":             "exposure",
    "transfers_in":       "market",
    "transfers_out":      "market",
    "transfers_balance":  "market",
    "ownership_count":    "market",
    "purchase_price":     "market",
    "xg":                 "attacking",
    "goals_scored":       "attacking",
    "threat":             "attacking",
    "xa":                 "creativity",
    "xgi":                "creativity",
    "assists":            "creativity",
    "creativity":         "creativity",
    "clean_sheets":       "defensive",
    "goals_conceded":     "defensive",
    "xgc":                "defensive",
    "saves":              "defensive",
    "penalties_saved":    "defensive",
    "total_points":       "form",
    "bonus":              "form",
    "bps":                "form",
    "influence":          "form",
    "ict_index":          "form",
    "fdr_avg":            "fixture",
    "fdr_min":            "fixture",
    "fdr_max":            "fixture",
    "was_home":           "fixture",
    "is_dgw":             "fixture",
    "fixture_count":      "fixture",
    "own_goals":          "discipline",
    "yellow_cards":       "discipline",
    "red_cards":          "discipline",
    "penalties_missed":   "discipline",
    "in_dreamteam":       "discipline",
}

EXPOSURE_SENSITIVITY_VALUES = frozenset({
    "exposure_robust",
    "exposure_sensitive",
    "exposure_degenerate",
    "exposure_proxy",
})

PREFERRED_POPULATION_VALUES = frozenset({
    "exposure_conditioned",
    "active_population",
    "both",
})

RANK_STABILITY_ROBUST_THRESHOLD = 0.90
RANK_STABILITY_SENSITIVE_THRESHOLD = 0.85
VARIANCE_RATIO_DEGENERATE_THRESHOLD = 0.20
SUPPORT_COLLAPSE_DEGENERATE_THRESHOLD = 0.30
ZERO_DELTA_HIGH_THRESHOLD = 0.20
ZERO_DELTA_MOD_THRESHOLD = 0.10


def compute_dual_scope_summary(
    state_conditioned: pd.DataFrame,
    state_active: pd.DataFrame,
    numeric_signals: list[str],
    positions: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    scope_map = {
        "conditioned": state_conditioned,
        "active":      state_active,
    }

    for scope_name, df in scope_map.items():
        for signal in numeric_signals:
            if signal not in df.columns:
                continue
            for position in positions:
                series = df[df["position_code"] == position][signal]
                clean = series.dropna().astype(float)
                if clean.empty:
                    continue

                mean_val = float(clean.mean())
                std_val  = float(clean.std())
                iqr_val  = float(clean.quantile(0.75) - clean.quantile(0.25))
                cv = np.nan if np.isclose(mean_val, 0.0) else float(std_val / abs(mean_val))
                skew_val = np.nan
                if len(clean) >= 3 and clean.nunique() > 1:
                    skew_val = float(stats.skew(clean, bias=False))

                pos_label  = POSITION_MAP.get(position, str(position))
                zero_rate  = float((clean == 0).mean())
                null_rate  = float(series.isna().mean())

                rows.append({
                    "signal":        signal,
                    "position":      pos_label,
                    "scope":         scope_name,
                    "signal_family": SIGNAL_FAMILY.get(signal, "unknown"),
                    "n":             int(len(clean)),
                    "mean":          round(mean_val, 6),
                    "median":        float(clean.median()),
                    "std":           round(std_val, 6),
                    "iqr":           round(iqr_val, 6),
                    "cv":            round(cv, 4) if not np.isnan(cv) else np.nan,
                    "skew":          round(skew_val, 3) if not np.isnan(skew_val) else np.nan,
                    "p25":           float(clean.quantile(0.25)),
                    "p75":           float(clean.quantile(0.75)),
                    "p90":           float(clean.quantile(0.90)),
                    "zero_rate":     round(zero_rate, 4),
                    "null_rate":     round(null_rate, 4),
                })

    return pd.DataFrame(rows)


def compute_zero_rate_comparison(dual_summary: pd.DataFrame) -> pd.DataFrame:
    cond = dual_summary[dual_summary["scope"] == "conditioned"][
        ["signal", "position", "zero_rate", "n"]
    ].rename(columns={"zero_rate": "zero_rate_conditioned", "n": "n_conditioned"})

    active = dual_summary[dual_summary["scope"] == "active"][
        ["signal", "position", "zero_rate", "n"]
    ].rename(columns={"zero_rate": "zero_rate_active", "n": "n_active"})

    merged = cond.merge(active, on=["signal", "position"], how="outer")
    merged["zero_rate_delta"] = (
        merged["zero_rate_active"] - merged["zero_rate_conditioned"]
    ).round(4)

    def _classify_zero_risk(row: pd.Series) -> str:
        zc = row["zero_rate_conditioned"]
        zd = row["zero_rate_delta"]
        if pd.notna(zc) and zc >= 0.90:
            return "high"
        if pd.notna(zd) and zd >= ZERO_DELTA_HIGH_THRESHOLD:
            return "high"
        if pd.notna(zd) and zd >= ZERO_DELTA_MOD_THRESHOLD:
            return "moderate"
        return "low"

    merged["structural_zero_risk"] = merged.apply(_classify_zero_risk, axis=1)
    return merged.sort_values("zero_rate_delta", ascending=False).reset_index(drop=True)


def compute_exposure_sensitivity(
    state_conditioned: pd.DataFrame,
    state_active: pd.DataFrame,
    numeric_signals: list[str],
    positions: list[int],
    zero_comparison: pd.DataFrame,
    min_n: int = 30,
    min_overlap_players: int = 10,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for signal in numeric_signals:
        if signal not in state_conditioned.columns:
            continue
        for position in positions:
            pos_label = POSITION_MAP.get(position, str(position))
            family = SIGNAL_FAMILY.get(signal, "unknown")

            cond_df = state_conditioned[
                state_conditioned["position_code"] == position
            ][["player_id", signal]].dropna()
            act_df = state_active[
                state_active["position_code"] == position
            ][["player_id", signal]].dropna()

            if len(cond_df) < min_n or len(act_df) < min_n:
                rows.append({
                    "signal": signal, "position": pos_label,
                    "signal_family": family,
                    "rank_order_stability": np.nan,
                    "variance_ratio": np.nan,
                    "support_collapse": np.nan,
                    "exposure_sensitivity": "unknown",
                })
                continue

            cond_means  = cond_df.groupby("player_id")[signal].mean()
            act_means   = act_df.groupby("player_id")[signal].mean()
            overlap     = cond_means.index.intersection(act_means.index)

            rank_stability = np.nan
            if len(overlap) >= min_overlap_players:
                c_vals = cond_means.loc[overlap].values.astype(float)
                a_vals = act_means.loc[overlap].values.astype(float)
                if c_vals.std() > 0 and a_vals.std() > 0:
                    rho, _ = stats.spearmanr(c_vals, a_vals)
                    rank_stability = float(rho)

            var_cond   = float(state_conditioned[
                state_conditioned["position_code"] == position
            ][signal].var())
            var_active = float(state_active[
                state_active["position_code"] == position
            ][signal].var())
            var_ratio = var_active / var_cond if var_cond > 0 else np.nan

            n_eff_cond   = int((cond_df[signal] > 0).sum())
            n_eff_active = int((act_df[signal] > 0).sum())
            support_collapse = (
                n_eff_cond / n_eff_active if n_eff_active > 0 else np.nan
            )

            if family in ("exposure", "market"):
                sensitivity = "exposure_proxy"
            elif (
                pd.notna(var_ratio) and var_ratio < VARIANCE_RATIO_DEGENERATE_THRESHOLD
            ) or (
                pd.notna(support_collapse)
                and support_collapse < SUPPORT_COLLAPSE_DEGENERATE_THRESHOLD
            ):
                sensitivity = "exposure_degenerate"
            elif np.isnan(rank_stability):
                sensitivity = "exposure_degenerate"
            elif rank_stability >= RANK_STABILITY_ROBUST_THRESHOLD:
                sensitivity = "exposure_robust"
            elif rank_stability < RANK_STABILITY_SENSITIVE_THRESHOLD:
                sensitivity = "exposure_sensitive"
            else:
                sensitivity = "exposure_robust"

            rows.append({
                "signal":               signal,
                "position":             pos_label,
                "signal_family":        family,
                "rank_order_stability": round(rank_stability, 3) if not np.isnan(rank_stability) else np.nan,
                "variance_ratio":       round(var_ratio, 3) if not np.isnan(var_ratio) else np.nan,
                "support_collapse":     round(support_collapse, 3) if not np.isnan(support_collapse) else np.nan,
                "exposure_sensitivity": sensitivity,
            })

    return pd.DataFrame(rows)


def assign_preferred_population(
    exp_sens: pd.DataFrame,
    zero_comparison: pd.DataFrame,
) -> pd.DataFrame:
    merged = exp_sens.merge(
        zero_comparison[["signal", "position", "structural_zero_risk",
                         "zero_rate_conditioned", "zero_rate_active",
                         "zero_rate_delta"]],
        on=["signal", "position"], how="left",
    )

    def _assign(row: pd.Series) -> str:
        sensitivity = row["exposure_sensitivity"]
        family      = row["signal_family"]
        zero_risk   = row.get("structural_zero_risk", "low")

        if sensitivity == "exposure_degenerate":
            return "exposure_conditioned"
        if sensitivity == "exposure_proxy":
            return "active_population"
        if family in ("attacking", "creativity") and zero_risk == "high":
            return "exposure_conditioned"
        if family in ("attacking", "creativity") and sensitivity == "exposure_sensitive":
            return "exposure_conditioned"
        return "both"

    merged["preferred_population"] = merged.apply(_assign, axis=1)
    return merged



def build_exposure_aware_registry(
    preferred_df: pd.DataFrame,
    zero_comparison: pd.DataFrame,
    variance_flags: pd.DataFrame,
    block_pivot: pd.DataFrame,
    dual_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble the EDA-2 signal registry. One row per (signal, position)."""
    vf = variance_flags[["signal", "position", "annotation"]].rename(
        columns={"annotation": "variance_annotation"}
    )
    registry = preferred_df.merge(vf, on=["signal", "position"], how="left")

    eff_support = dual_summary[dual_summary["scope"] == "conditioned"][
        ["signal", "position", "n"]
    ].rename(columns={"n": "n_conditioned"})
    eff_active = dual_summary[dual_summary["scope"] == "active"][
        ["signal", "position", "n"]
    ].rename(columns={"n": "n_active"})
    registry = registry.merge(eff_support, on=["signal", "position"], how="left")
    registry = registry.merge(eff_active,  on=["signal", "position"], how="left")

    if not block_pivot.empty and "gw_block_variance_stability" in block_pivot.columns:
        bv = block_pivot[["signal", "position", "gw_block_variance_stability",
                           "early_vs_mid_pct", "late_vs_mid_pct"]]
        registry = registry.merge(bv, on=["signal", "position"], how="left")
    else:
        registry["gw_block_variance_stability"] = np.nan
        registry["early_vs_mid_pct"]  = np.nan
        registry["late_vs_mid_pct"]   = np.nan

    def _support_quality(row: pd.Series) -> str:
        n = row.get("n_conditioned", 0)
        va = row.get("variance_annotation", "OK")
        if va in ("CONSTANT",) or (pd.notna(n) and n < 30):
            return "insufficient"
        if va == "NEAR_CONSTANT" or (pd.notna(n) and n < 100):
            return "borderline"
        return "sufficient"

    def _measurement_character(row: pd.Series) -> str:
        zc  = row.get("zero_rate_conditioned", 0)
        sig = row["signal"]
        fam = row.get("signal_family", "")
        if pd.notna(zc):
            if zc >= 0.90:
                return "structural_zero"
            if zc >= 0.50:
                return "participation_proxy"
        if sig in BINARY_SIGNALS:
            return "binary_event"
        if fam in ("attacking", "creativity", "defensive", "discipline") and pd.notna(zc) and zc >= 0.30:
            return "participation_proxy"
        return "continuous_form"

    def _gw_block_stability(row: pd.Series) -> str:
        ev = row.get("early_vs_mid_pct", np.nan)
        lv = row.get("late_vs_mid_pct", np.nan)
        if pd.isna(ev) and pd.isna(lv):
            return "unknown"
        late_drop = pd.notna(lv) and lv < -30
        if late_drop:
            return "compressing"
        if (pd.notna(ev) and abs(ev) > 30) or (pd.notna(lv) and lv > 30):
            return "expanding"
        return "stable"

    def _status(row: pd.Series) -> str:
        va = row.get("variance_annotation", "OK")
        zc = row.get("zero_rate_conditioned", 0)
        if va == "CONSTANT":
            return "EXCLUDE:constant_variance"
        if pd.notna(zc) and zc >= 0.98:
            return "EXCLUDE:structural_zero"
        return "INCLUDE"

    registry["support_quality"]             = registry.apply(_support_quality, axis=1)
    registry["measurement_character"]       = registry.apply(_measurement_character, axis=1)
    registry["gw_block_variance_stability"] = registry.apply(_gw_block_stability, axis=1)
    registry["status"]                      = registry.apply(_status, axis=1)

    col_order = [
        "signal", "position", "signal_family",
        "n_conditioned", "n_active",
        "zero_rate_conditioned", "zero_rate_active", "zero_rate_delta",
        "structural_zero_risk",
        "rank_order_stability", "variance_ratio", "support_collapse",
        "exposure_sensitivity", "preferred_population",
        "support_quality", "measurement_character",
        "gw_block_variance_stability", "early_vs_mid_pct", "late_vs_mid_pct",
        "variance_annotation", "status",
    ]
    existing = [c for c in col_order if c in registry.columns]
    extra    = [c for c in registry.columns if c not in col_order]
    return registry[existing + extra].sort_values(["signal", "position"]).reset_index(drop=True)
