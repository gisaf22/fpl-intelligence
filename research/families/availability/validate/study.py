"""Does recent minutes predict whether a player features next GW?

Mode: predictive · Stage: validate · Status: ACCEPTED — minutes_roll8 (DEF), minutes_roll3/roll8 (MID)
Population: target played_next_gw (binary); lag-1 respected; GW 3-38 (full season — holdout folded in, ADR-010)

ADLC §4 audit row C — reframes the raw minutes signal as an availability question
(after row B found minutes uninformative as a returns signal).

Entry point: ``run()``  — produces correlation_results.csv, block_results.csv,
quintile_results.csv, classification_summary.csv, run_metadata.json, evidence.yaml.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load as load_mart
from research.families.evidence_record import build_signal_verdict, write_evidence
from research.families.population_gate import assert_population_gate
from research.kernels.inferential.resampling import bootstrap_spearman_ci
from research.kernels.hypothesis.stratification import quintile_stratification

RUNS_DIR = Path(__file__).resolve().parents[4] / "research" / "runs"
VALIDATE_DIR = Path(__file__).parent
LENS = "avail"

# Primary target: binary — did the player accumulate ≥60 min the following GW?
# Secondary target: continuous points (used only for supplementary correlation rows).
PRIMARY_TARGET = "played_next_gw"
SECONDARY_TARGET = "total_points_next_gw"

# LENS_DESIGN.md §2 — primary target is played_next_gw (binary)
SIGNALS: dict[str, dict] = {
    "minutes_roll3": {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "minutes_roll5": {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 6},
    "minutes_roll8": {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 9},
}

SIGNAL_IDS: dict[str, str] = {
    "minutes_roll3": "AVAIL-001",
    "minutes_roll5": "AVAIL-002",
    "minutes_roll8": "AVAIL-003",
}

MINUTES_THRESHOLD = 60
GW_MAX = 38

GW_WINDOWS: dict[str, tuple[int, int]] = {
    "early": (3, 12),
    "mid":   (13, 26),
    "late":  (27, 38),
}

N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
# Binary target has range [0,1]; a meaningful Q5-Q1 gap is ≥10 percentage points.
QUINTILE_GAP_THRESHOLD_PRIMARY = 0.10    # LENS_DESIGN.md §8
QUINTILE_GAP_THRESHOLD_SECONDARY = 1.0  # continuous points target uses standard threshold

LENS_STATUS_LEGEND = {
    "informative": "passes all 3 qualification gates; recommended for governance inclusion",
    "uninformative": "failed CI gate or decision-relevance gate",
    "unstable": "passed CI + relevance but failed 2-of-3 GW-window stability gate",
}


# ---------------------------------------------------------------------------
# Per-slice computation helpers
# ---------------------------------------------------------------------------

def _measure_rank_association(
    df: pd.DataFrame,
    signal: str,
    signal_id: str,
    position: str,
    gw_window: str,
    target: str,
) -> dict | None:
    """Compute bootstrapped Spearman CI between signal and target for one population slice.

    Args:
        df:         Population slice (already filtered to position and GW range).
        signal:     Predictor column name.
        signal_id:  Registry identifier (e.g. ``"AVAIL-001"``).
        position:   Position label for this slice (e.g. ``"DEF"``).
        gw_window:  Window label — ``"full"``, ``"early"``, ``"mid"``, ``"late"``,
                    or ``"full_no_dgw"`` for DGW sensitivity.
        target:     Outcome column name. Passed explicitly so the call site
                    documents whether this is the binary or continuous target.

    Returns:
        Dict with rho, CI bounds, n, ci_excludes_zero, or None when there are
        fewer than 10 paired observations or the bootstrap fails.
    """
    valid = df[[signal, target]].dropna()
    if len(valid) < 10:
        return None
    x, y = valid[signal].to_numpy(), valid[target].to_numpy()
    ci = bootstrap_spearman_ci(x, y, n_samples=N_BOOTSTRAP, ci_level=CI_LEVEL, seed=BOOTSTRAP_SEED)
    if ci is None:
        return None
    return {
        "signal_id": signal_id, "signal": signal, "position": position,
        "gw_window": gw_window, "target": target,
        "rho": ci["rho"], "ci_lower": ci["ci_lower"], "ci_upper": ci["ci_upper"],
        "n": ci["n"], "ci_excludes_zero": bool(ci["ci_lower"] > 0 or ci["ci_upper"] < 0),
    }


def _stratify_by_quintile(
    df: pd.DataFrame,
    signal: str,
    signal_id: str,
    position: str,
    gw_window: str,
    target: str,
) -> dict | None:
    """Split the population slice into signal quintiles and measure target mean per group."""
    return quintile_stratification(
        df, signal, signal_id, position, gw_window,
        target=target, bidirectional=False,
    )


# ---------------------------------------------------------------------------
# Signal qualification gates
# ---------------------------------------------------------------------------

def _apply_signal_qualification_gates(
    full_window_assoc: dict | None,
    full_window_quintile: dict | None,
    gw_window_assocs: list[dict | None],
    signal: str,
    signal_id: str,
    position: str,
) -> dict:
    """Apply the three-gate decision protocol to determine a signal's qualification verdict.

    Gate 1 — CI gate: the bootstrapped Spearman CI for the full study window must
             exclude zero. Failure → uninformative.
    Gate 2 — Decision relevance gate: quintile stratification must show a Q5-Q1 gap
             ≥ QUINTILE_GAP_THRESHOLD_PRIMARY and monotone-increasing pattern.
             Failure → uninformative.
    Gate 3 — GW-window stability gate: the CI must exclude zero in ≥ 2 of the 3
             seasonal windows (early/mid/late). Failure → unstable.

    All gates operate on the primary target (played_next_gw).
    """
    base = {"signal_id": signal_id, "signal": signal, "position": position}
    if full_window_assoc is None:
        return {**base, "lens_status": "uninformative", "rationale": "insufficient observations"}
    if not full_window_assoc["ci_excludes_zero"]:
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI crosses zero [{full_window_assoc['ci_lower']:.3f}, {full_window_assoc['ci_upper']:.3f}]"}
    decision_relevant = (
        full_window_quintile is not None
        and full_window_quintile["q5_q1_gap"] >= QUINTILE_GAP_THRESHOLD_PRIMARY
        and full_window_quintile["is_monotonic"]
    )
    if not decision_relevant:
        gap = f"{full_window_quintile['q5_q1_gap']:.3f}" if full_window_quintile else "N/A"
        mono = full_window_quintile["is_monotonic"] if full_window_quintile else "N/A"
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI excludes zero but fails decision relevance (Q5-Q1={gap}, monotonic={mono})"}
    n_stable_windows = sum(1 for b in gw_window_assocs if b and b["ci_excludes_zero"])
    if n_stable_windows >= 2:
        return {**base, "lens_status": "informative",
                "rationale": f"CI excludes zero, decision relevant, passes {n_stable_windows}/3 GW windows"}
    return {**base, "lens_status": "unstable",
            "rationale": f"CI excludes zero in aggregate but passes only {n_stable_windows}/3 GW windows"}


# ---------------------------------------------------------------------------
# Main run entry point
# ---------------------------------------------------------------------------

def run(db_path: Path = DB_PATH) -> Path:
    """Run the full AVAIL lens validation study.

    Phase 1 — Load data, derive binary availability target (played_next_gw).
    Phase 2 — For each (signal, position) slice: compute full-window and GW-window
               rank associations for both the primary (binary) and secondary
               (continuous) targets; compute quintile stratification.
    Phase 3 — Apply qualification gates on the primary target, write evidence
               verdict, persist all CSVs.

    Returns the timestamped run output directory.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"LENS-AVAIL-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1: Load + derive binary availability target
    # ------------------------------------------------------------------
    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart
    state = state.sort_values(["player_id", "gw"]).copy()

    # Lag-1 targets: both are attached to GW N and reference GW N+1 outcomes.
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)
    state["minutes_next_gw"] = state.groupby("player_id")["minutes"].shift(-1)
    # played_next_gw: 1 if the player started the following GW (≥60 min), else 0.
    state["played_next_gw"] = (
        state["minutes_next_gw"].ge(60).astype(float)
        .where(state["minutes_next_gw"].notna())
    )

    population = state[
        (state["minutes"] >= MINUTES_THRESHOLD) & (state["gw"] <= GW_MAX)
    ].copy()
    assert_population_gate(population, GW_WINDOWS)

    # ------------------------------------------------------------------
    # Phase 2: Per-(signal, position) rank association + stratification
    # ------------------------------------------------------------------
    full_assoc_rows: list[dict] = []
    window_assoc_rows: list[dict] = []
    stratification_rows: list[dict] = []
    qualification_rows: list[dict] = []
    evidence_rows: list[dict] = []

    for signal, cfg in SIGNALS.items():
        signal_id = SIGNAL_IDS[signal]
        gw_min = cfg["gw_min"]

        for pos in cfg["positions"]:
            pos_pop = population[(population["position_label"] == pos) & (population["gw"] >= gw_min)]

            # Compute associations for both primary and secondary targets (supplementary view)
            for target, gap_thr in [
                (PRIMARY_TARGET, QUINTILE_GAP_THRESHOLD_PRIMARY),
                (SECONDARY_TARGET, QUINTILE_GAP_THRESHOLD_SECONDARY),
            ]:
                full_assoc = _measure_rank_association(pos_pop, signal, signal_id, pos, "full", target)
                if full_assoc:
                    full_assoc_rows.append(full_assoc)

                full_quintile = _stratify_by_quintile(pos_pop, signal, signal_id, pos, "full", target)
                if full_quintile:
                    stratification_rows.append(full_quintile)

                # DGW sensitivity
                if full_assoc and "is_dgw" in pos_pop.columns:
                    no_dgw_assoc = _measure_rank_association(
                        pos_pop[~pos_pop["is_dgw"]], signal, signal_id, pos, "full_no_dgw", target
                    )
                    if no_dgw_assoc:
                        full_assoc_rows.append(no_dgw_assoc)

            # GW-window stratification on the primary target only (gates are primary-only)
            gw_window_assocs: list[dict | None] = []
            for window_name, (wlo, whi) in GW_WINDOWS.items():
                effective_lo = max(gw_min, wlo)
                window_df = pos_pop[pos_pop["gw"].between(effective_lo, whi)]
                w_assoc = _measure_rank_association(
                    window_df, signal, signal_id, pos, window_name, PRIMARY_TARGET
                )
                gw_window_assocs.append(w_assoc)
                if w_assoc:
                    window_assoc_rows.append(w_assoc)
                w_quintile = _stratify_by_quintile(
                    window_df, signal, signal_id, pos, window_name, PRIMARY_TARGET,
                )
                if w_quintile:
                    stratification_rows.append(w_quintile)

            # ------------------------------------------------------------------
            # Phase 3 (per-slice): Qualify on primary target + build evidence
            # ------------------------------------------------------------------
            primary_full = next(
                (r for r in full_assoc_rows
                 if r["signal"] == signal and r["position"] == pos
                 and r["gw_window"] == "full" and r["target"] == PRIMARY_TARGET),
                None,
            )
            primary_quintile = next(
                (r for r in stratification_rows
                 if r["signal"] == signal and r["position"] == pos
                 and r["block"] == "full" and r["target"] == PRIMARY_TARGET),
                None,
            )
            qualification = _apply_signal_qualification_gates(
                primary_full, primary_quintile, gw_window_assocs, signal, signal_id, pos
            )
            qualification_rows.append(qualification)
            evidence_rows.append(
                build_signal_verdict(signal, pos, primary_full, gw_window_assocs, qualification)
            )

    # ------------------------------------------------------------------
    # Phase 3 (global): Persist artefacts
    # ------------------------------------------------------------------
    pd.DataFrame(full_assoc_rows + window_assoc_rows).to_csv(
        out_dir / "correlation_results.csv", index=False
    )
    pd.DataFrame(window_assoc_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(stratification_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(qualification_rows).to_csv(out_dir / "classification_summary.csv", index=False)

    meta = {
        "timestamp": ts, "db_path": str(db_path),
        "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED,
        "ci_level": CI_LEVEL, "minutes_threshold": MINUTES_THRESHOLD,
        "gw_max": GW_MAX, "gw_windows": {k: list(v) for k, v in GW_WINDOWS.items()},
        "primary_target": PRIMARY_TARGET,
        "secondary_target": SECONDARY_TARGET,
        "quintile_gap_threshold_primary": QUINTILE_GAP_THRESHOLD_PRIMARY,
        "quintile_gap_threshold_secondary": QUINTILE_GAP_THRESHOLD_SECONDARY,
        "signals": {s: {**cfg, "signal_id": SIGNAL_IDS[s]} for s, cfg in SIGNALS.items()},
        "lens_status_legend": LENS_STATUS_LEGEND,
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2))

    write_evidence(
        VALIDATE_DIR, LENS, PRIMARY_TARGET, evidence_rows,
        evidence_run={"source": f"LENS-AVAIL-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<16} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 75)
    primary_full_index = {
        (r["signal"], r["position"]): r
        for r in full_assoc_rows
        if r["gw_window"] == "full" and r["target"] == PRIMARY_TARGET
    }
    for q in qualification_rows:
        assoc = primary_full_index.get((q["signal"], q["position"]))
        if assoc:
            print(
                f"{q['signal']:<16} {q['position']:<5} "
                f"{assoc['rho']:>7.4f}  [{assoc['ci_lower']:>6.3f},{assoc['ci_upper']:>6.3f}]  "
                f"{'Yes' if assoc['ci_excludes_zero'] else 'No':>8}  {q['lens_status']}"
            )

    return out_dir


if __name__ == "__main__":
    run()
