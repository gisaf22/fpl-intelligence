"""EDA-8 — Gap Study.

Mode: descriptive/diagnostic · Stage: explore · Status: answered — gate decisions produced
Population: gap study across saves (GK), xgc, penalties_saved, assists rolling windows.
Not a §4 audit row — explore-stage gate study feeding the lenses.

Four independent sub-studies (EDA-8A through EDA-8D) as specified in
research/foundation/gap/EDA_08_DESIGN.md. All may run in parallel but are executed
sequentially here for a single output directory.

Sub-studies:
  EDA-8A: saves (GK) — Layer 1 raw association
  EDA-8B: xgc       — Layer 1 raw association + Layer 2 redundancy
  EDA-8C: penalties_saved — sparsity gate only
  EDA-8D: assists rolling windows — Layer 3 representation validation

Gate decisions produced: G-EDA8-01 through G-EDA8-10.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from dal.config import DB_PATH
from dal.pipeline import load as load_mart

RUNS_DIR = Path("research/runs")

# EDA_08_DESIGN.md §3 — inherited from EVAL_DESIGN.md v2.2
MINUTES_THRESHOLD = 60
GW_MIN = 6      # G-EDA1-02
GW_MAX = 33     # G-EDA1-02; GW 34 excluded
GW_MIN_ROLL3 = 8
GW_MIN_ROLL5 = 10

# EDA_08_DESIGN.md §3 — three-block structure (LENS-FORM standard)
GW_BLOCKS: dict[str, tuple[int, int]] = {
    "early": (6, 15),
    "mid":   (16, 25),
    "late":  (26, 33),
}

N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
PARTIAL_RHO_REDUNDANCY_THRESHOLD = 0.30  # EDA_08_DESIGN.md §4 EDA-8B

# Position labels from DAL (GKP, not GK)
GKP = "GKP"


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

def _bootstrap_spearman_ci(
    x: np.ndarray, y: np.ndarray, n_samples: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float, float]:
    """Return (rho_obs, ci_lower, ci_upper) via bootstrap resampling."""
    rho_obs = float(spearmanr(x, y).statistic)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_samples)
    for i in range(n_samples):
        idx = rng.integers(0, len(x), size=len(x))
        boot[i] = float(spearmanr(x[idx], y[idx]).statistic)
    alpha = 1.0 - CI_LEVEL
    return (
        rho_obs,
        float(np.percentile(boot, 100 * alpha / 2)),
        float(np.percentile(boot, 100 * (1 - alpha / 2))),
    )


def _correlation_record(
    df: pd.DataFrame,
    signal: str,
    position: str,
    block: str,
    sub_study: str,
    target: str = "total_points_next_gw",
) -> dict | None:
    valid = df[[signal, target]].dropna()
    if len(valid) < 10:
        return None
    x, y = valid[signal].to_numpy(dtype=float), valid[target].to_numpy(dtype=float)
    rho, ci_lo, ci_hi = _bootstrap_spearman_ci(x, y)
    return {
        "sub_study": sub_study,
        "signal": signal,
        "position": position,
        "block": block,
        "rho": round(rho, 4),
        "ci_lower": round(ci_lo, 4),
        "ci_upper": round(ci_hi, 4),
        "n": len(valid),
        "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0),
    }


def _partial_spearman(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    z_col: str,
) -> float | None:
    """Rank-based partial Spearman rho of x and y controlling for z.

    Approach: regress rank(x) and rank(y) separately on rank(z) via OLS;
    compute Pearson correlation of residuals.
    """
    sub = df[[x_col, y_col, z_col]].dropna()
    if len(sub) < 30:
        return None
    rx = sub[x_col].rank().to_numpy(dtype=float)
    ry = sub[y_col].rank().to_numpy(dtype=float)
    rz = sub[z_col].rank().to_numpy(dtype=float)

    def _residuals(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        rz_c = rz - rz.mean()
        coef = float(np.dot(a - a.mean(), rz_c) / np.dot(rz_c, rz_c))
        return a - a.mean() - coef * rz_c

    ex = _residuals(rx, rz)
    ey = _residuals(ry, rz)
    denom = float(np.std(ex) * np.std(ey))
    if denom < 1e-10:
        return None
    return round(float(np.dot(ex, ey) / (len(ex) * np.std(ex) * np.std(ey))), 4)


def _block_stability_count(block_corrs: list[dict | None]) -> int:
    return sum(1 for b in block_corrs if b and b["ci_excludes_zero"])


# ---------------------------------------------------------------------------
# EDA-8C: penalties_saved sparsity gate
# ---------------------------------------------------------------------------

def run_8c(state: pd.DataFrame) -> dict:
    """EDA-8C: sparsity characterisation for penalties_saved (GKP only).

    Returns the sparsity record and gate decision G-EDA8-06.
    """
    # All GKP rows in study window — no minutes filter for sparsity characterisation
    gkp = state[
        (state["position_label"] == GKP) &
        (state["gw"].between(GW_MIN, GW_MAX)) &
        (~state["is_bgw"])
    ]["penalties_saved"].dropna()

    total_records = len(gkp)
    nonzero = int((gkp > 0).sum())
    zero_rate = round(float((gkp == 0).mean()), 4)
    distinct_gks_with_saves = int(
        state[
            (state["position_label"] == GKP) &
            (state["gw"].between(GW_MIN, GW_MAX)) &
            (~state["is_bgw"]) &
            (state["penalties_saved"] > 0)
        ]["player_id"].nunique()
    )

    dist = {
        "mean": round(float(gkp.mean()), 4),
        "median": round(float(gkp.median()), 4),
        "p90": round(float(gkp.quantile(0.90)), 4),
        "max": int(gkp.max()),
        "total_nonzero_records": nonzero,
        "total_records": total_records,
        "zero_rate": zero_rate,
        "distinct_gks_with_any_save": distinct_gks_with_saves,
    }

    if zero_rate > 0.95 and nonzero < 30:
        decision = "structurally-sparse"
    elif 0.80 <= zero_rate <= 0.95 and nonzero >= 30:
        decision = "assessable-with-caution"
    else:
        decision = "assessable"

    return {
        "sub_study": "EDA-8C",
        "signal": "penalties_saved",
        "position": GKP,
        **dist,
        "G-EDA8-06": decision,
    }


# ---------------------------------------------------------------------------
# EDA-8A: saves (GK) Layer 1
# ---------------------------------------------------------------------------

def run_8a(state: pd.DataFrame) -> tuple[list[dict], list[dict], dict]:
    """EDA-8A: raw association and sparsity pre-check for saves at GKP.

    Returns (correlation_rows, block_rows, gate_decisions).
    """
    pop = state[
        (state["position_label"] == GKP) &
        (state["minutes"] >= MINUTES_THRESHOLD) &
        (state["gw"].between(GW_MIN, GW_MAX))
    ].copy()

    # Sparsity pre-check (EDA_08_DESIGN.md §4 EDA-8A Step 1)
    saves_all = state[
        (state["position_label"] == GKP) &
        (state["gw"].between(GW_MIN, GW_MAX)) &
        (~state["is_bgw"])
    ]["saves"].dropna()
    saves_zero_rate = round(float((saves_all == 0).mean()), 4)

    # Raw association
    full_rec = _correlation_record(pop, "saves", GKP, "full", "EDA-8A")

    block_recs: list[dict | None] = []
    for block_name, (blo, bhi) in GW_BLOCKS.items():
        block_df = pop[pop["gw"].between(blo, bhi)]
        b = _correlation_record(block_df, "saves", GKP, block_name, "EDA-8A")
        block_recs.append(b)

    corr_rows = [r for r in [full_rec, *block_recs] if r]

    # Gate decisions
    g01: str
    g02: str
    if full_rec is None:
        g01 = "uninformative"
        g02 = "ineligible"
    elif full_rec["ci_excludes_zero"]:
        g01 = "informative"
        _stability = _block_stability_count(block_recs)
        # Layer 3 eligibility: informative + sparsity acceptable (zero_rate < 0.80)
        if saves_zero_rate < 0.80:
            g02 = "eligible"
        else:
            g02 = "ineligible"
    else:
        g01 = "uninformative"
        g02 = "ineligible"

    gates = {
        "sub_study": "EDA-8A",
        "signal": "saves",
        "position": GKP,
        "saves_zero_rate_gkp": saves_zero_rate,
        "rho_full": full_rec["rho"] if full_rec else None,
        "ci_lower": full_rec["ci_lower"] if full_rec else None,
        "ci_upper": full_rec["ci_upper"] if full_rec else None,
        "ci_excludes_zero": full_rec["ci_excludes_zero"] if full_rec else False,
        "block_stability_count": _block_stability_count(block_recs),
        "G-EDA8-01": g01,
        "G-EDA8-02": g02,
    }
    return corr_rows, [r for r in block_recs if r], gates


# ---------------------------------------------------------------------------
# EDA-8B: xgc Layer 1 + Layer 2 redundancy
# ---------------------------------------------------------------------------

def run_8b(state: pd.DataFrame) -> tuple[list[dict], list[dict], list[dict]]:
    """EDA-8B: raw association + redundancy check for xgc at DEF and GKP.

    Returns (correlation_rows, block_rows, gate_decision_rows).
    """
    positions = ["DEF", GKP]
    corr_rows: list[dict] = []
    block_rows: list[dict] = []
    gate_rows: list[dict] = []

    # Gate decisions with defaults
    g03 = "uninformative"  # xgc DEF
    g04 = "uninformative"  # xgc GKP
    xgc_informative_positions: list[str] = []

    for pos in positions:
        pop = state[
            (state["position_label"] == pos) &
            (state["minutes"] >= MINUTES_THRESHOLD) &
            (state["gw"].between(GW_MIN, GW_MAX))
        ].copy()

        full_rec = _correlation_record(pop, "xgc", pos, "full", "EDA-8B")
        if full_rec:
            corr_rows.append(full_rec)

        # DGW sensitivity
        if full_rec and "is_dgw" in pop.columns:
            no_dgw = pop[~pop["is_dgw"]]
            dgw_rec = _correlation_record(no_dgw, "xgc", pos, "full_no_dgw", "EDA-8B")
            if dgw_rec:
                corr_rows.append(dgw_rec)

        block_recs: list[dict | None] = []
        for block_name, (blo, bhi) in GW_BLOCKS.items():
            block_df = pop[pop["gw"].between(blo, bhi)]
            b = _correlation_record(block_df, "xgc", pos, block_name, "EDA-8B")
            block_recs.append(b)
            if b:
                block_rows.append(b)

        informative = (
            full_rec is not None and full_rec["ci_excludes_zero"]
        )

        gate_row: dict = {
            "sub_study": "EDA-8B",
            "signal": "xgc",
            "position": pos,
            "rho_full": full_rec["rho"] if full_rec else None,
            "ci_lower": full_rec["ci_lower"] if full_rec else None,
            "ci_upper": full_rec["ci_upper"] if full_rec else None,
            "ci_excludes_zero": full_rec["ci_excludes_zero"] if full_rec else False,
            "block_stability_count": _block_stability_count(block_recs),
        }

        if pos == "DEF":
            g03 = "informative" if informative else "uninformative"
            gate_row["G-EDA8-03"] = g03
        else:
            g04 = "informative" if informative else "uninformative"
            gate_row["G-EDA8-04"] = g04

        if informative:
            xgc_informative_positions.append(pos)
        gate_rows.append(gate_row)

    # Layer 2 redundancy (only if xgc informative at any position)
    if xgc_informative_positions:
        redundancy_rows: list[dict] = []
        for pos in xgc_informative_positions:
            pop_pos = state[
                (state["position_label"] == pos) &
                (state["minutes"] >= MINUTES_THRESHOLD) &
                (state["gw"].between(GW_MIN, GW_MAX))
            ].copy()
            pr_gc = _partial_spearman(pop_pos, "xgc", "total_points_next_gw", "goals_conceded")
            pr_cs = _partial_spearman(pop_pos, "xgc", "total_points_next_gw", "clean_sheets")
            redundancy_rows.append({
                "sub_study": "EDA-8B",
                "position": pos,
                "partial_rho_xgc_vs_goals_conceded": pr_gc,
                "partial_rho_xgc_vs_clean_sheets": pr_cs,
            })

        # G-EDA8-05: redundant if both partial rhos < threshold at all informative positions
        all_redundant = all(
            (r["partial_rho_xgc_vs_goals_conceded"] is not None and
             abs(r["partial_rho_xgc_vs_goals_conceded"]) < PARTIAL_RHO_REDUNDANCY_THRESHOLD) and
            (r["partial_rho_xgc_vs_clean_sheets"] is not None and
             abs(r["partial_rho_xgc_vs_clean_sheets"]) < PARTIAL_RHO_REDUNDANCY_THRESHOLD)
            for r in redundancy_rows
        )
        g05 = "redundant" if all_redundant else "independent"
        for r in redundancy_rows:
            r["G-EDA8-05"] = g05
        gate_rows.extend(redundancy_rows)
    else:
        gate_rows.append({
            "sub_study": "EDA-8B",
            "note": "Layer 2 not reached — xgc uninformative at all positions",
            "G-EDA8-05": "not-assessed",
        })

    return corr_rows, block_rows, gate_rows


# ---------------------------------------------------------------------------
# EDA-8D: assists rolling windows Layer 3
# ---------------------------------------------------------------------------

def _quintile_ev_record(
    df: pd.DataFrame,
    signal: str,
    position: str,
    block: str,
    sub_study: str,
    target: str = "total_points_next_gw",
) -> dict | None:
    valid = df[[signal, target]].dropna()
    if len(valid) < 25:
        return None
    try:
        ranked = valid.copy()
        ranked["quintile"] = pd.qcut(
            ranked[signal].rank(method="first"), 5,
            labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
        )
        g = ranked.groupby("quintile", observed=True)[target]
        means = g.mean()
        sds = g.std()
        if not all(f"Q{i}" in means.index for i in range(1, 6)):
            return None
        ev = {f"q{i}_mean": round(float(means[f"Q{i}"]), 3) for i in range(1, 6)}
        sd = {f"q{i}_sd": round(float(sds[f"Q{i}"]), 3) for i in range(1, 6)}
        gap = round(float(means["Q5"] - means["Q1"]), 3)
        is_monotonic = all(
            float(means[f"Q{i}"]) <= float(means[f"Q{i+1}"]) for i in range(1, 5)
        )
        return {
            "sub_study": sub_study, "signal": signal, "position": position, "block": block,
            **ev, **sd, "q5_q1_gap": gap, "is_monotonic": is_monotonic,
            "decision_relevant": bool(gap >= 1.0 and is_monotonic),
        }
    except Exception:
        return None


def _haul_record(
    df: pd.DataFrame,
    signal: str,
    position: str,
    sub_study: str,
    target: str = "total_points_next_gw",
) -> dict | None:
    """Haul identification rate: fraction of top-10% outcomes in top signal quintile.

    Position-relative top 10% threshold (G-EDA8-D). Base rate = 20%.
    """
    valid = df[[signal, target]].dropna()
    if len(valid) < 50:
        return None
    try:
        haul_threshold = float(valid[target].quantile(0.90))
        valid = valid.copy()
        valid["is_haul"] = valid[target] >= haul_threshold
        valid["quintile"] = pd.qcut(
            valid[signal].rank(method="first"), 5,
            labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
        )
        total_hauls = int(valid["is_haul"].sum())
        hauls_in_q5 = int(valid[valid["quintile"] == "Q5"]["is_haul"].sum())
        haul_rate = round(float(hauls_in_q5 / total_hauls), 4) if total_hauls > 0 else None
        return {
            "sub_study": sub_study,
            "signal": signal,
            "position": position,
            "haul_threshold_pts": round(haul_threshold, 2),
            "total_hauls": total_hauls,
            "hauls_in_q5": hauls_in_q5,
            "haul_identification_rate": haul_rate,
            "base_rate": 0.20,
            "lift_over_base": round(float(haul_rate - 0.20), 4) if haul_rate is not None else None,
        }
    except Exception:
        return None


def run_8d(state: pd.DataFrame) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """EDA-8D: assists rolling window Layer 3 validation.

    Returns (corr_rows, block_rows, quint_rows, haul_rows, gate_rows).
    """
    positions_assists = ["MID", "FWD", "DEF"]

    # Signal registry for EDA-8D
    signals_cfg: dict[str, dict] = {
        "assists":       {"gw_min": GW_MIN,       "label": "assists (lag-1)"},
        "assists_roll3": {"gw_min": GW_MIN_ROLL3,  "label": "assists_roll3"},
        "assists_roll5": {"gw_min": GW_MIN_ROLL5,  "label": "assists_roll5"},
    }
    naive_signal = "points_roll3"  # G-EDA7-02

    corr_rows: list[dict] = []
    block_rows: list[dict] = []
    quint_rows: list[dict] = []
    haul_rows: list[dict] = []
    gate_rows: list[dict] = []

    # Naive baseline rho per position
    naive_rho: dict[str, float | None] = {}
    for pos in positions_assists:
        base_pop = state[
            (state["position_label"] == pos) &
            (state["minutes"] >= MINUTES_THRESHOLD) &
            (state["gw"].between(GW_MIN, GW_MAX))
        ]
        rec = _correlation_record(base_pop, naive_signal, pos, "full", "EDA-8D")
        naive_rho[pos] = rec["rho"] if rec else None

    # Per signal per position
    for signal, cfg in signals_cfg.items():
        gw_min_s = cfg["gw_min"]
        for pos in positions_assists:
            pop = state[
                (state["position_label"] == pos) &
                (state["minutes"] >= MINUTES_THRESHOLD) &
                (state["gw"].between(gw_min_s, GW_MAX))
            ].copy()

            full_rec = _correlation_record(pop, signal, pos, "full", "EDA-8D")
            if full_rec:
                full_rec["clears_naive_baseline"] = (
                    naive_rho[pos] is not None and full_rec["rho"] > naive_rho[pos]
                )
                corr_rows.append(full_rec)

            full_quint = _quintile_ev_record(pop, signal, pos, "full", "EDA-8D")
            if full_quint:
                quint_rows.append(full_quint)

            haul_rec = _haul_record(pop, signal, pos, "EDA-8D")
            if haul_rec:
                haul_rows.append(haul_rec)

            # DGW sensitivity
            if full_rec and "is_dgw" in pop.columns:
                no_dgw = pop[~pop["is_dgw"]]
                dgw_rec = _correlation_record(no_dgw, signal, pos, "full_no_dgw", "EDA-8D")
                if dgw_rec:
                    corr_rows.append(dgw_rec)

            block_recs: list[dict | None] = []
            for block_name, (blo, bhi) in GW_BLOCKS.items():
                effective_lo = max(gw_min_s, blo)
                block_df = pop[pop["gw"].between(effective_lo, bhi)]
                b = _correlation_record(block_df, signal, pos, block_name, "EDA-8D")
                block_recs.append(b)
                if b:
                    block_rows.append(b)
                bq = _quintile_ev_record(block_df, signal, pos, block_name, "EDA-8D")
                if bq:
                    quint_rows.append(bq)

    # Gate decisions: G-EDA8-07/08/09/10
    # Compute per (signal, position) full_window rho and quint for comparison
    full_corr_idx = {
        (r["signal"], r["position"]): r
        for r in corr_rows if r["block"] == "full"
    }
    full_quint_idx = {
        (r["signal"], r["position"]): r
        for r in quint_rows if r["block"] == "full"
    }

    def _improvement_over_raw(
        roll_signal: str, pos: str,
    ) -> bool:
        """True if rolling variant improves on raw assists and naive baseline at pos."""
        raw_rec = full_corr_idx.get(("assists", pos))
        roll_rec = full_corr_idx.get((roll_signal, pos))
        naive_r = naive_rho.get(pos)
        if not roll_rec or not raw_rec:
            return False
        roll_quint = full_quint_idx.get((roll_signal, pos))
        raw_quint = full_quint_idx.get(("assists", pos))
        # Criterion 1: rho higher, CI not overlapping
        rho_higher = roll_rec["rho"] > raw_rec["rho"]
        raw_ci_hi = raw_rec.get("ci_upper", 0)
        roll_ci_lo = roll_rec.get("ci_lower", 0)
        ci_no_overlap = roll_ci_lo > raw_ci_hi
        # Criterion 2: Q5-Q1 gap materially larger
        ev_better = (
            roll_quint is not None and
            raw_quint is not None and
            roll_quint["q5_q1_gap"] > raw_quint["q5_q1_gap"]
        )
        # Criterion 3: stability no worse
        # (assessed qualitatively; require that roll_rec passes CI excludes zero)
        improves_raw = (rho_higher and ci_no_overlap) or ev_better
        # Also must clear naive baseline
        clears_naive = naive_r is None or roll_rec["rho"] > naive_r
        return improves_raw and clears_naive

    # G-EDA8-07: assists_roll3 MID
    g07 = "improves" if _improvement_over_raw("assists_roll3", "MID") else "no-improvement"
    # G-EDA8-08: assists_roll3 FWD
    g08 = "improves" if _improvement_over_raw("assists_roll3", "FWD") else "no-improvement"
    # G-EDA8-09: assists_roll3 DEF — check for conditionally-informative (late-season only)
    def _g09_decision() -> str:
        roll_full = full_corr_idx.get(("assists_roll3", "DEF"))
        if not roll_full:
            return "no-improvement"
        if _improvement_over_raw("assists_roll3", "DEF"):
            return "improves"
        # Conditionally informative: CI excludes zero overall but driven by late block
        if roll_full["ci_excludes_zero"]:
            # Check if late block drives the result (G-EDA5-04 caveat)
            late_rec = next(
                (r for r in block_rows
                 if r["signal"] == "assists_roll3" and r["position"] == "DEF"
                 and r["block"] == "late"),
                None,
            )
            early_rec = next(
                (r for r in block_rows
                 if r["signal"] == "assists_roll3" and r["position"] == "DEF"
                 and r["block"] == "early"),
                None,
            )
            if (late_rec and late_rec["ci_excludes_zero"] and
                    (early_rec is None or not early_rec["ci_excludes_zero"])):
                return "conditionally-informative"
        return "no-improvement"

    g09 = _g09_decision()

    # G-EDA8-10: preferred window per position
    def _preferred_window(pos: str) -> str:
        candidates = ["assists_roll5", "assists_roll3", "assists"]
        best = "raw"
        best_rho: float | None = None
        for sig in candidates:
            rec = full_corr_idx.get((sig, pos))
            if rec and rec["ci_excludes_zero"]:
                if best_rho is None or rec["rho"] > best_rho:
                    best_rho = rec["rho"]
                    best = sig
        # Require improvement over raw to pick rolling variant
        if best == "assists_roll5" and not _improvement_over_raw("assists_roll5", pos):
            best = "assists_roll3" if _improvement_over_raw("assists_roll3", pos) else "raw"
        if best == "assists_roll3" and not _improvement_over_raw("assists_roll3", pos):
            best = "raw"
        return best

    g10_mid = _preferred_window("MID")
    g10_fwd = _preferred_window("FWD")
    g10_def = _preferred_window("DEF")

    gate_rows.extend([
        {"sub_study": "EDA-8D", "gate": "G-EDA8-07", "signal": "assists_roll3",
         "position": "MID", "decision": g07,
         "rho": full_corr_idx.get(("assists_roll3", "MID"), {}).get("rho"),
         "raw_rho": full_corr_idx.get(("assists", "MID"), {}).get("rho"),
         "naive_rho": naive_rho.get("MID")},
        {"sub_study": "EDA-8D", "gate": "G-EDA8-08", "signal": "assists_roll3",
         "position": "FWD", "decision": g08,
         "rho": full_corr_idx.get(("assists_roll3", "FWD"), {}).get("rho"),
         "raw_rho": full_corr_idx.get(("assists", "FWD"), {}).get("rho"),
         "naive_rho": naive_rho.get("FWD")},
        {"sub_study": "EDA-8D", "gate": "G-EDA8-09", "signal": "assists_roll3",
         "position": "DEF", "decision": g09,
         "rho": full_corr_idx.get(("assists_roll3", "DEF"), {}).get("rho"),
         "raw_rho": full_corr_idx.get(("assists", "DEF"), {}).get("rho"),
         "naive_rho": naive_rho.get("DEF")},
        {"sub_study": "EDA-8D", "gate": "G-EDA8-10-MID", "signal": "assists_preferred_window",
         "position": "MID", "decision": g10_mid},
        {"sub_study": "EDA-8D", "gate": "G-EDA8-10-FWD", "signal": "assists_preferred_window",
         "position": "FWD", "decision": g10_fwd},
        {"sub_study": "EDA-8D", "gate": "G-EDA8-10-DEF", "signal": "assists_preferred_window",
         "position": "DEF", "decision": g10_def},
    ])

    return corr_rows, block_rows, quint_rows, haul_rows, gate_rows


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(db_path: Path = DB_PATH) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"EDA8-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart

    # Lag-1 target: total_points at GW N+1
    state = state.sort_values(["player_id", "gw"]).copy()
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)

    print("Running EDA-8C: penalties_saved sparsity gate...")
    c_rec = run_8c(state)

    print("Running EDA-8A: saves (GKP) Layer 1...")
    a_corr, a_block, a_gates = run_8a(state)

    print("Running EDA-8B: xgc Layer 1 + Layer 2...")
    b_corr, b_block, b_gates = run_8b(state)

    print("Running EDA-8D: assists rolling Layer 3...")
    d_corr, d_block, d_quint, d_haul, d_gates = run_8d(state)

    # Write outputs
    all_corr = a_corr + b_corr + d_corr
    all_block = a_block + b_block + d_block

    pd.DataFrame(all_corr).to_csv(out_dir / "correlation_results.csv", index=False)
    pd.DataFrame(all_block).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(d_quint).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(d_haul).to_csv(out_dir / "haul_results.csv", index=False)

    # Gate decisions
    gate_rows = [
        c_rec,        # 8C sparsity
        a_gates,      # 8A gates
        *b_gates,     # 8B gates
        *d_gates,     # 8D gates
    ]
    pd.DataFrame(gate_rows).to_csv(out_dir / "gate_decisions.csv", index=False)

    meta = {
        "timestamp": ts,
        "db_path": str(db_path),
        "design_doc": "research/foundation/gap/EDA_08_DESIGN.md",
        "framework": "EVAL_DESIGN.md v2.2",
        "gw_min": GW_MIN,
        "gw_max": GW_MAX,
        "minutes_threshold": MINUTES_THRESHOLD,
        "gw_blocks": {k: list(v) for k, v in GW_BLOCKS.items()},
        "n_bootstrap": N_BOOTSTRAP,
        "ci_level": CI_LEVEL,
        "partial_rho_redundancy_threshold": PARTIAL_RHO_REDUNDANCY_THRESHOLD,
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2))

    # -------------------------------------------------------------------------
    # Summary print
    # -------------------------------------------------------------------------
    print(f"\n{'='*70}")
    print(f"EDA-8 run complete: {out_dir}")
    print(f"{'='*70}")

    print("\n--- EDA-8C: penalties_saved sparsity gate ---")
    print(f"  zero_rate={c_rec['zero_rate']:.3f}  nonzero_records={c_rec['total_nonzero_records']}  "
          f"total_records={c_rec['total_records']}")
    print(f"  G-EDA8-06: {c_rec['G-EDA8-06']}")

    print("\n--- EDA-8A: saves (GKP) ---")
    print(f"  saves_zero_rate_gkp={a_gates['saves_zero_rate_gkp']:.3f}")
    print(f"  rho={a_gates['rho_full']}  CI=[{a_gates['ci_lower']}, {a_gates['ci_upper']}]  "
          f"ci_excludes_zero={a_gates['ci_excludes_zero']}")
    print(f"  block_stability={a_gates['block_stability_count']}/3")
    print(f"  G-EDA8-01: {a_gates['G-EDA8-01']}   G-EDA8-02: {a_gates['G-EDA8-02']}")

    print("\n--- EDA-8B: xgc ---")
    for row in b_gates:
        if "G-EDA8-03" in row:
            print(f"  DEF rho={row['rho_full']}  CI=[{row['ci_lower']}, {row['ci_upper']}]  "
                  f"G-EDA8-03: {row['G-EDA8-03']}")
        elif "G-EDA8-04" in row:
            print(f"  GKP rho={row['rho_full']}  CI=[{row['ci_lower']}, {row['ci_upper']}]  "
                  f"G-EDA8-04: {row['G-EDA8-04']}")
        elif "G-EDA8-05" in row:
            print(f"  partial_rho vs goals_conceded: {row.get('partial_rho_xgc_vs_goals_conceded')}  "
                  f"vs clean_sheets: {row.get('partial_rho_xgc_vs_clean_sheets')}  "
                  f"G-EDA8-05: {row['G-EDA8-05']}")

    print("\n--- EDA-8D: assists rolling ---")
    for row in d_gates:
        gate = row.get("gate", "")
        if gate in ("G-EDA8-07", "G-EDA8-08", "G-EDA8-09"):
            print(f"  {gate} ({row['position']}): rho={row['rho']}  raw_rho={row['raw_rho']}  "
                  f"naive_rho={row['naive_rho']}  → {row['decision']}")
        elif "G-EDA8-10" in gate:
            print(f"  {gate} ({row['position']}): preferred_window={row['decision']}")

    return out_dir


if __name__ == "__main__":
    run()
