"""
Phase 9 Operational Validation — Retrospective Backtest
Operational Convergence Plan Phase 9

Tests SYNTH-01 approved signal compositions against actual 25/26 season outcomes
using the complete season (GW 1–38). GW 34–38 are holdout — never seen by SYNTH-01
(which used GW_MAX=33).

Population: players with minutes >= 60 in the current GW (consistent with SYNTH-01).
Target alignment: state features at GW N predict outcomes at GW N+1 (next-GW framing).

Outputs:
  outputs/phase9_backtest_results.yaml   — machine-readable validation statistics
  stdout summary table

Usage:
  python studies/operational/phase9_backtest.py
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr

from dal.access import get_curated_spine, get_state_features

DB_PATH = Path(os.environ.get("FPL_DB_PATH", "~/.fpl/fpl.db")).expanduser()
OUT_PATH = Path("outputs/phase9_backtest_results.yaml")
RUNS_DIR = Path("studies/runs")

SYNTH01_GW_MAX = 33       # last GW used in SYNTH-01 evaluation
MINUTES_THRESHOLD = 60    # consistent with SYNTH-01 population filter
MIN_N = 30                # minimum observations to report rho reliably

# SYNTH-01 approved composition groups — weights from synth01_decisions.yaml
GROUPS: list[dict] = [
    dict(
        position="DEF", lens="FORM",
        signals=["xgi_roll3", "xgi_roll5"],
        weights={"xgi_roll3": 0.5, "xgi_roll5": 0.5},
        target="total_points_next_gw",
        synth01_composite_rho=0.1191,
        synth01_baseline_rho=0.0166,
        gw_min=6,
    ),
    dict(
        position="DEF", lens="AVAIL",
        signals=["minutes_roll8"],
        weights={"minutes_roll8": 1.0},
        target="played_next_gw",
        synth01_composite_rho=0.2188,
        synth01_baseline_rho=None,
        gw_min=9,
    ),
    dict(
        position="DEF", lens="MARKET",
        signals=["transfers_in", "purchase_price"],
        weights={"transfers_in": 0.5, "purchase_price": 0.5},
        target="total_points_next_gw",
        synth01_composite_rho=0.1719,
        synth01_baseline_rho=0.0161,
        gw_min=1,
    ),
    dict(
        position="MID", lens="FORM",
        signals=["xgi_roll5"],
        weights={"xgi_roll5": 1.0},
        target="total_points_next_gw",
        synth01_composite_rho=0.1571,
        synth01_baseline_rho=0.158,
        gw_min=6,
    ),
    dict(
        position="MID", lens="AVAIL",
        signals=["minutes_roll3", "minutes_roll8"],
        weights={"minutes_roll3": 0.5, "minutes_roll8": 0.5},
        target="played_next_gw",
        synth01_composite_rho=None,
        synth01_baseline_rho=None,
        gw_min=3,
    ),
    dict(
        position="MID", lens="MARKET",
        signals=["transfers_in", "ownership_count"],
        weights={"transfers_in": 0.5, "ownership_count": 0.5},
        target="total_points_next_gw",
        synth01_composite_rho=0.1725,
        synth01_baseline_rho=0.158,
        gw_min=1,
    ),
    dict(
        position="FWD", lens="MARKET",
        signals=["purchase_price"],
        weights={"purchase_price": 1.0},
        target="total_points_next_gw",
        synth01_composite_rho=0.155,
        synth01_baseline_rho=None,
        gw_min=1,
    ),
]

POSITION_CODE_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def spearman_rho(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    """Return (rho, p_value, n) for two series after dropping NaN pairs."""
    mask = x.notna() & y.notna()
    xm, ym = x[mask], y[mask]
    n = int(mask.sum())
    if n < MIN_N:
        return float("nan"), float("nan"), n
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = spearmanr(xm, ym)
    return float(result.statistic), float(result.pvalue), n


def composite_score(group_df: pd.DataFrame, signals: list[str], weights: dict[str, float]) -> pd.Series:
    """Weighted sum of raw signal values — consistent with SYNTH-01 _composite_rho method."""
    composite = pd.Series(0.0, index=group_df.index)
    for sig in signals:
        if sig not in group_df.columns:
            continue
        composite += group_df[sig].astype(float) * weights[sig]
    return composite


# ---------------------------------------------------------------------------
# FDR moderation check (holdout)
# ---------------------------------------------------------------------------

def fdr_moderation_check(
    pop: pd.DataFrame,
    signals: list[str],
    weights: dict[str, float],
    target: str,
    threshold: float = 0.15,
) -> dict:
    """Measure rank-order change when splitting by FDR (high vs low fixture difficulty).

    Returns fraction of GW-level rank orderings that change materially when FDR is
    used as a stratification variable.
    """
    if "fdr_avg" not in pop.columns or pop["fdr_avg"].isna().all():
        return {"material": False, "n_gws": 0, "fraction_rank_changed": float("nan"), "note": "fdr_avg unavailable"}

    gw_results = []
    for gw, gw_df in pop.groupby("gw"):
        if len(gw_df) < 4:
            continue
        fdr_median = gw_df["fdr_avg"].median()
        high_fdr = gw_df[gw_df["fdr_avg"] > fdr_median]
        low_fdr = gw_df[gw_df["fdr_avg"] <= fdr_median]

        all_comp = composite_score(gw_df, signals, weights)
        high_rank_all = all_comp.rank(ascending=False)

        if len(low_fdr) < 2 or len(high_fdr) < 2:
            continue

        # Rank within low-FDR group using full-population scores
        low_rank_all = all_comp[low_fdr.index].rank(ascending=False)
        low_rank_subset = composite_score(low_fdr, signals, weights).rank(ascending=False)

        if len(low_rank_all) < 2:
            continue

        rho_change, _, _ = spearman_rho(low_rank_all, low_rank_subset)
        gw_results.append({"gw": gw, "rho_change": rho_change})

    if not gw_results:
        return {"material": False, "n_gws": 0, "fraction_rank_changed": float("nan"), "note": "insufficient GW data"}

    n_gws = len(gw_results)
    rhos = [r["rho_change"] for r in gw_results if not np.isnan(r["rho_change"])]
    mean_rho = float(np.mean(rhos)) if rhos else float("nan")
    fraction_low_rho = float(sum(r < (1 - threshold) for r in rhos) / len(rhos)) if rhos else float("nan")

    return {
        "material": fraction_low_rho > threshold,
        "n_gws": n_gws,
        "mean_within_group_rho": round(mean_rho, 4),
        "fraction_rank_changed": round(fraction_low_rho, 4),
        "note": f"fraction of GWs where within-group rho < {1 - threshold:.2f}",
    }


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

def run_backtest(state: pd.DataFrame) -> dict:
    state = state.sort_values(["player_id", "gw"]).copy()
    state["_position"] = state["position_code"].map(POSITION_CODE_MAP)

    # Build next-GW targets (shift within player)
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)
    state["minutes_next_gw"] = state.groupby("player_id")["minutes"].shift(-1)
    state["played_next_gw"] = (
        state["minutes_next_gw"].ge(MINUTES_THRESHOLD).astype(float)
        .where(state["minutes_next_gw"].notna())
    )

    # Population: active players in the current GW (consistent with SYNTH-01)
    pop_all = state[state["minutes"] >= MINUTES_THRESHOLD].copy()
    pop_in_sample = pop_all[pop_all["gw"] <= SYNTH01_GW_MAX].copy()
    pop_holdout = pop_all[pop_all["gw"] > SYNTH01_GW_MAX].copy()

    group_results = []

    for group in GROUPS:
        position = group["position"]
        lens = group["lens"]
        signals = group["signals"]
        weights = group["weights"]
        target = group["target"]
        gw_min = group["gw_min"]
        synth01_rho = group["synth01_composite_rho"]

        label = f"{position} × {lens}"

        def _analyse(pop: pd.DataFrame, split_label: str) -> dict:
            grp = pop[
                (pop["_position"] == position) & (pop["gw"] >= gw_min)
            ].copy()

            if grp.empty:
                return {"split": split_label, "n": 0, "status": "no_data"}

            # Bivariate rho for each individual signal
            signal_rhos = {}
            for sig in signals:
                rho, pval, n = spearman_rho(grp[sig] if sig in grp.columns else pd.Series(dtype=float), grp[target])
                signal_rhos[sig] = {"rho": round(rho, 4), "pval": round(pval, 4) if not np.isnan(pval) else None, "n": n}

            # Composite rho
            comp = composite_score(grp, signals, weights)
            comp_rho, comp_pval, comp_n = spearman_rho(comp, grp[target])

            result = {
                "split": split_label,
                "n": comp_n,
                "composite_rho": round(comp_rho, 4),
                "composite_pval": round(comp_pval, 4) if not np.isnan(comp_pval) else None,
                "signal_rhos": signal_rhos,
            }
            if synth01_rho is not None and not np.isnan(comp_rho):
                result["delta_vs_synth01"] = round(comp_rho - synth01_rho, 4)
            return result

        in_sample = _analyse(pop_in_sample, "in_sample")
        holdout = _analyse(pop_holdout, "holdout")
        full_season = _analyse(pop_all, "full_season")

        # FDR moderation on holdout
        fdr_check = fdr_moderation_check(
            pop_holdout[(pop_holdout["_position"] == position) & (pop_holdout["gw"] >= gw_min)],
            signals, weights, target,
        )

        group_results.append({
            "group": label,
            "position": position,
            "lens": lens,
            "signals": signals,
            "target": target,
            "synth01_composite_rho": synth01_rho,
            "in_sample": in_sample,
            "holdout": holdout,
            "full_season": full_season,
            "fdr_moderation_holdout": fdr_check,
        })

    return {
        "study": "phase9_operational_backtest",
        "produced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": str(DB_PATH),
        "synth01_gw_max": SYNTH01_GW_MAX,
        "minutes_threshold": MINUTES_THRESHOLD,
        "n_gw_total": int(pop_all["gw"].nunique()),
        "n_gw_holdout": int(pop_holdout["gw"].nunique()),
        "n_players": int(state["player_id"].nunique()),
        "groups": group_results,
    }


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _fmt_rho(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "  —  "
    return f"{v:+.3f}"


def print_summary(results: dict) -> None:
    print()
    print("=" * 78)
    print("PHASE 9 OPERATIONAL VALIDATION — RETROSPECTIVE BACKTEST")
    print(f"25/26 Season  |  GW 1–38  |  Holdout: GW {SYNTH01_GW_MAX + 1}–38")
    print("=" * 78)
    print(f"{'Group':<20} {'Target':<22} {'SYNTH01':>7} {'In-sample':>10} {'Holdout':>9} {'Full':>7} {'Δ Hold':>7}")
    print("-" * 78)

    for g in results["groups"]:
        synth_rho = g["synth01_composite_rho"]
        ins = g["in_sample"]
        hold = g["holdout"]
        full = g["full_season"]
        hold_rho = hold.get("composite_rho")
        delta = hold_rho - synth_rho if (hold_rho and synth_rho and not np.isnan(hold_rho)) else float("nan")

        print(
            f"{g['group']:<20} "
            f"{g['target']:<22} "
            f"{_fmt_rho(synth_rho):>7} "
            f"{_fmt_rho(ins.get('composite_rho')):>10}  "
            f"{_fmt_rho(hold_rho):>7}  "
            f"{_fmt_rho(full.get('composite_rho')):>5}  "
            f"{_fmt_rho(delta):>7}"
        )

    print("-" * 78)
    print()
    print("Δ Hold = holdout composite rho minus SYNTH-01 estimate (+ means better than expected)")
    print()

    # FDR summary
    print("FDR MODERATION CHECK (holdout GWs):")
    for g in results["groups"]:
        fdr = g["fdr_moderation_holdout"]
        material_flag = "MATERIAL" if fdr.get("material") else "ok"
        frac = fdr.get("fraction_rank_changed")
        frac_str = f"{frac:.2f}" if frac is not None and not np.isnan(frac) else "—"
        print(f"  {g['group']:<20}  fraction_rank_changed={frac_str}  → {material_flag}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Loading state from {DB_PATH} ...")
    spine = get_curated_spine(DB_PATH)
    state = get_state_features(spine)
    print(f"  {len(state):,} rows  |  GW {state['gw'].min()}–{state['gw'].max()}  |  {state['player_id'].nunique()} players")

    results = run_backtest(state)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as fh:
        yaml.dump(results, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"\nResults saved → {OUT_PATH}")

    print_summary(results)
