"""Signal profiling — marginal distributions, zero mass, variance, redundancy, status table."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

POSITION_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
POSITIONS = [1, 2, 3, 4]
BLOCK_ORDER = ["early", "mid", "late"]

# Structural zeros — signals that have no meaning for a position by football definition.
STRUCTURAL_ZERO_MAP: dict[str, set[str]] = {
    "saves":           {"DEF", "MID", "FWD"},
    "penalties_saved": {"DEF", "MID", "FWD"},
    "goals_scored":    {"GK"},
}

# Binary signals — semantically 0/1 flags, not continuous or zero-inflated.
BINARY_SIGNALS: frozenset[str] = frozenset({"was_home", "is_dgw", "starts"})

# Reason sets used for precedence resolution in build_signal_status_table.
EXCLUDE_REASONS: frozenset[str] = frozenset({"CONSTANT", "STRUCTURAL_ZERO"})
FLAG_REASONS: frozenset[str] = frozenset({
    "HIGH_ZERO_MASS", "EXTREME_ZERO_MASS", "NEAR_CONSTANT", "LOW_VARIANCE", "HIGH_REDUNDANCY",
})

HIGH_ZERO_MASS_THRESHOLD = 50.0
EXTREME_ZERO_MASS_THRESHOLD = 95.0
LOW_VARIANCE_CV_THRESHOLD = 0.10
HIGH_REDUNDANCY_RHO = 0.90
CATEGORICAL_NEAR_CONSTANT_THRESHOLD = 95.0


def split_candidate_signals(
    df: pd.DataFrame,
    candidate_signals: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    available = [s for s in candidate_signals if s in df.columns]
    missing = [s for s in candidate_signals if s not in df.columns]
    numeric = [s for s in available if pd.api.types.is_numeric_dtype(df[s])]
    categorical = [s for s in available if s not in numeric]
    return available, missing, numeric, categorical


def summarize_signals(
    df: pd.DataFrame,
    numeric_signals: list[str],
    categorical_signals: list[str],
    positions: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric_rows: list[dict[str, Any]] = []
    categorical_rows: list[dict[str, Any]] = []

    for signal in numeric_signals:
        for position in positions:
            series = df[df["position_code"] == position][signal]
            clean = series.dropna().astype(float)
            if clean.empty:
                continue

            mean_val = float(clean.mean())
            std_val = float(clean.std())
            iqr_val = float(clean.quantile(0.75) - clean.quantile(0.25))
            cv = np.nan if np.isclose(mean_val, 0.0) else float(std_val / abs(mean_val))
            skew_val = np.nan
            if len(clean) >= 3 and clean.nunique() > 1:
                skew_val = float(stats.skew(clean, bias=False))

            pos_label = POSITION_MAP.get(position, position)
            zero_pct = float((clean == 0).mean() * 100)
            numeric_rows.append({
                "signal": signal,
                "position": pos_label,
                "distribution_type": _classify_distribution_type(signal, pos_label, zero_pct),
                "n": len(clean),
                "mean": mean_val,
                "median": float(clean.median()),
                "p90": float(clean.quantile(0.90)),
                "std": std_val,
                "iqr": iqr_val,
                "cv": cv,
                "skew": skew_val,
                "min": float(clean.min()),
                "max": float(clean.max()),
                "p25": float(clean.quantile(0.25)),
                "p75": float(clean.quantile(0.75)),
                "zero_pct": zero_pct,
                "null_pct": float(series.isna().mean() * 100),
            })

    for signal in categorical_signals:
        for position in positions:
            series = df[df["position_code"] == position][signal]
            clean = series.dropna()
            if clean.empty:
                continue

            value_counts = clean.value_counts(normalize=True, dropna=True)
            mode_value = clean.mode().iloc[0] if not clean.mode().empty else None
            categorical_rows.append({
                "signal": signal,
                "position": POSITION_MAP.get(position, position),
                "n": len(clean),
                "n_unique": int(clean.nunique()),
                "mode": mode_value,
                "top_category_pct": float(value_counts.iloc[0] * 100),
                "null_pct": float(series.isna().mean() * 100),
            })

    return pd.DataFrame(numeric_rows), pd.DataFrame(categorical_rows)


def compute_zero_mass(numeric_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in numeric_summary.iterrows():
        zp = row["zero_pct"]
        if zp >= EXTREME_ZERO_MASS_THRESHOLD:
            annotation = "EXTREME_ZERO_MASS"
        elif zp >= HIGH_ZERO_MASS_THRESHOLD:
            annotation = "HIGH_ZERO_MASS"
        else:
            annotation = "OK"
        rows.append({
            "signal": row["signal"],
            "position": row["position"],
            "zero_pct": zp,
            "n": row["n"],
            "annotation": annotation,
        })
    return (
        pd.DataFrame(rows)
        .sort_values("zero_pct", ascending=False)
        .reset_index(drop=True)
    )


def compute_variance_flags(numeric_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in numeric_summary.iterrows():
        std = row["std"]
        iqr = row["iqr"]
        cv = row["cv"]

        if std == 0:
            annotation = "CONSTANT"
        elif iqr == 0:
            annotation = "NEAR_CONSTANT"
        elif pd.notna(cv) and cv < LOW_VARIANCE_CV_THRESHOLD:
            annotation = "LOW_VARIANCE"
        else:
            annotation = "OK"

        rows.append({
            "signal": row["signal"],
            "position": row["position"],
            "std": std,
            "iqr": iqr,
            "cv": cv,
            "mean": row["mean"],
            "n": row["n"],
            "annotation": annotation,
        })
    return (
        pd.DataFrame(rows)
        .sort_values(["signal", "position"])
        .reset_index(drop=True)
    )


def compute_block_variance(
    blocks: dict[str, pd.DataFrame],
    numeric_signals: list[str],
    positions: list[str],
    min_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for signal in numeric_signals:
        for position in positions:
            for block_name, block_df in blocks.items():
                clean = block_df[block_df["position_code"] == position][signal].dropna().astype(float)
                if len(clean) < min_n:
                    continue
                rows.append({
                    "signal": signal,
                    "position": POSITION_MAP.get(position, position),
                    "block": block_name,
                    "std": float(clean.std()),
                    "mean": float(clean.mean()),
                    "n": len(clean),
                })

    block_variance = pd.DataFrame(rows)
    if block_variance.empty:
        return block_variance, pd.DataFrame()

    pivot = (
        block_variance.pivot_table(
            index=["signal", "position"],
            columns="block",
            values="std",
            aggfunc="first",
        )
        .reset_index()
    )

    for col in BLOCK_ORDER:
        if col not in pivot.columns:
            pivot[col] = np.nan

    pivot["early_vs_mid_pct"] = _pct_change(pivot["early"], pivot["mid"])
    pivot["late_vs_mid_pct"] = _pct_change(pivot["late"], pivot["mid"])

    return block_variance, pivot


def compute_block_homogeneity(
    blocks: dict[str, pd.DataFrame],
    numeric_signals: list[str],
    categorical_signals: list[str],
    positions: list[str],
    min_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric_rows: list[dict[str, Any]] = []

    for signal in numeric_signals:
        for position in positions:
            block_data = {
                name: df[df["position_code"] == position][signal].dropna().astype(float)
                for name, df in blocks.items()
            }
            mid = block_data.get("mid", pd.Series(dtype=float))
            row: dict[str, Any] = {"signal": signal, "position": POSITION_MAP.get(position, position)}

            for ref_block in ["early", "late"]:
                other = block_data.get(ref_block, pd.Series(dtype=float))

                if len(other) < min_n or len(mid) < min_n:
                    row[f"ks_{ref_block}_mid"] = np.nan
                    row[f"median_diff_pct_{ref_block}"] = np.nan
                    row[f"p90_diff_pct_{ref_block}"] = np.nan
                    continue

                ks_stat, _ = stats.ks_2samp(other, mid)
                row[f"ks_{ref_block}_mid"] = round(float(ks_stat), 4)

                mid_median = float(mid.median())
                other_median = float(other.median())
                row[f"median_diff_pct_{ref_block}"] = (
                    np.nan if np.isclose(mid_median, 0.0)
                    else round(((other_median - mid_median) / abs(mid_median)) * 100, 1)
                )

                mid_p90 = float(mid.quantile(0.90))
                other_p90 = float(other.quantile(0.90))
                row[f"p90_diff_pct_{ref_block}"] = (
                    np.nan if np.isclose(mid_p90, 0.0)
                    else round(((other_p90 - mid_p90) / abs(mid_p90)) * 100, 1)
                )

            numeric_rows.append(row)

    categorical_rows: list[dict[str, Any]] = []

    for signal in categorical_signals:
        for position in positions:
            block_data = {
                name: df[df["position_code"] == position][signal].dropna()
                for name, df in blocks.items()
            }
            mid = block_data.get("mid", pd.Series(dtype=object))
            row = {"signal": signal, "position": POSITION_MAP.get(position, position)}

            if len(mid) < min_n:
                row["note"] = "INSUFFICIENT_SUPPORT"
                categorical_rows.append(row)
                continue

            mid_counts = mid.value_counts(normalize=True)
            mid_mode = mid_counts.index[0]
            mid_top_pct = float(mid_counts.iloc[0] * 100)
            row["mid_mode"] = mid_mode
            row["mid_top_pct"] = round(mid_top_pct, 1)

            for ref_block in ["early", "late"]:
                other = block_data.get(ref_block, pd.Series(dtype=object))
                if len(other) < min_n:
                    continue
                other_counts = other.value_counts(normalize=True)
                row[f"{ref_block}_mode"] = other_counts.index[0]
                row[f"{ref_block}_top_pct"] = round(float(other_counts.iloc[0] * 100), 1)

            categorical_rows.append(row)

    return pd.DataFrame(numeric_rows), pd.DataFrame(categorical_rows)


def compute_within_group_redundancy(
    df: pd.DataFrame,
    pairs: list[tuple[str, str]],
    positions: list[str],
    min_n: int = 30,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for sig_a, sig_b in pairs:
        if sig_a not in df.columns or sig_b not in df.columns:
            continue
        for position in positions:
            pos_df = df[df["position_code"] == position][[sig_a, sig_b]].dropna()
            if len(pos_df) < min_n:
                continue
            rho, _ = stats.spearmanr(pos_df[sig_a].astype(float), pos_df[sig_b].astype(float))
            rows.append({
                "signal_a": sig_a,
                "signal_b": sig_b,
                "position": POSITION_MAP.get(position, position),
                "n": len(pos_df),
                "rho": round(float(rho), 4),
                "flag": float(rho) >= HIGH_REDUNDANCY_RHO,
            })
    return pd.DataFrame(rows).sort_values(["signal_a", "position"]).reset_index(drop=True)


def build_signal_status_table(
    numeric_summary: pd.DataFrame,
    categorical_summary: pd.DataFrame,
    zero_mass: pd.DataFrame,
    variance_flags: pd.DataFrame,
    redundancy: pd.DataFrame,
) -> pd.DataFrame:
    reasons_map: dict[tuple[str, str], list[str]] = {}

    def add(signal: str, position: str, reason: str) -> None:
        reasons_map.setdefault((signal, position), []).append(reason)

    for signal, invalid_positions in STRUCTURAL_ZERO_MAP.items():
        for pos_label in invalid_positions:
            add(signal, pos_label, "STRUCTURAL_ZERO")

    for _, row in zero_mass.iterrows():
        if row["annotation"] != "OK":
            add(row["signal"], row["position"], row["annotation"])

    for _, row in variance_flags.iterrows():
        if row["annotation"] != "OK":
            add(row["signal"], row["position"], row["annotation"])

    for _, row in categorical_summary.iterrows():
        if row["top_category_pct"] >= CATEGORICAL_NEAR_CONSTANT_THRESHOLD:
            add(row["signal"], row["position"], "NEAR_CONSTANT")

    flagged_red = redundancy[redundancy["flag"] == True] if not redundancy.empty else pd.DataFrame()  # noqa: E712
    for _, row in flagged_red.iterrows():
        add(row["signal_a"], row["position"], "HIGH_REDUNDANCY")
        add(row["signal_b"], row["position"], "HIGH_REDUNDANCY")

    all_pairs: set[tuple[str, str]] = set()
    for df in [numeric_summary, categorical_summary]:
        if not df.empty:
            all_pairs.update(zip(df["signal"], df["position"]))

    output_rows = []
    for signal, position in sorted(all_pairs):
        reasons = sorted(set(reasons_map.get((signal, position), [])))
        reason_set = set(reasons)
        if reason_set & EXCLUDE_REASONS:
            status = "EXCLUDE"
        elif reason_set & FLAG_REASONS:
            status = "FLAG"
        else:
            status = "KEEP"
        output_rows.append({
            "signal": signal,
            "position": position,
            "status": status,
            "constraints": reasons,
        })

    return pd.DataFrame(output_rows)


def _classify_distribution_type(signal: str, pos_label: str, zero_pct: float) -> str:
    if pos_label in STRUCTURAL_ZERO_MAP.get(signal, set()):
        return "structural_zero"
    if signal in BINARY_SIGNALS:
        return "binary"
    if zero_pct >= HIGH_ZERO_MASS_THRESHOLD:
        return "zero_inflated"
    return "continuous"


def _pct_change(lhs: pd.Series, rhs: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=lhs.index, dtype=float)
    valid = rhs.notna() & ~np.isclose(rhs.fillna(0), 0.0)
    result.loc[valid] = ((lhs.loc[valid] / rhs.loc[valid]) - 1) * 100
    return result
