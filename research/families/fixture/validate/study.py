"""Does single-GW fixture difficulty predict returns?

Mode: predictive · Stage: validate · Status: REJECTED — fdr_avg excluded (non-monotonic); reserved as binary moderator
Population: same-GW target total_points; GW 3-38 (full season — holdout folded in, ADR-010)

Note: this lens uses a same-GW target (not lag-1). The signal describes the fixture
the player faces *this* GW and the target is the points they scored *this* GW.
No lead/lag shift is needed for the predictor; the study population filter (minutes≥60)
itself conditions on the GW-N outcome being realised.

ADLC §4 audit (unlettered fixture/market lens row).

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
LENS = "fixture_gw"
TARGET = "total_points"   # same-GW: fixture difficulty and points are measured in the same GW

# Same-GW signals — no lag shift needed for the predictor.
SIGNALS: dict[str, dict] = {
    "fdr_avg":       {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "was_home":      {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "fixture_count": {"positions": ["DEF", "MID"], "gw_min": 3},   # FWD/GKP blocked in EDA
}

SIGNAL_IDS: dict[str, str] = {
    "fdr_avg":       "FIXTURE-001",
    "was_home":      "FIXTURE-002",
    "fixture_count": "FIXTURE-003",
}

MINUTES_THRESHOLD = 60
GW_MAX = 38
GW_WINDOWS: dict[str, tuple[int, int]] = {
    "early": (3, 12), "mid": (13, 26), "late": (27, 38),
}
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
# fdr_avg is an inverted signal (lower = easier fixture = more points), so
# bidirectional=True is used for quintile stratification. The threshold is the
# same as other continuous targets.
QUINTILE_GAP_THRESHOLD = 1.0

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
        signal_id:  Registry identifier (e.g. ``"FIXTURE-001"``).
        position:   Position label for this slice (e.g. ``"DEF"``).
        gw_window:  Window label — ``"full"``, ``"early"``, ``"mid"``, ``"late"``,
                    or ``"full_no_dgw"`` for DGW sensitivity.
        target:     Outcome column name. Passed explicitly to document whether this
                    is a same-GW or lag-1 target at the call site.

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
) -> dict | None:
    """Split the population slice into signal quintiles and measure target mean per group.

    bidirectional=True because fdr_avg has a negative expected direction (lower
    difficulty → higher points), so both monotone-increasing and -decreasing
    patterns are accepted as decision-relevant.
    """
    return quintile_stratification(
        df, signal, signal_id, position, gw_window,
        target=TARGET, bidirectional=True,
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
    Gate 2 — Decision relevance gate: quintile stratification must show |Q5-Q1| gap
             ≥ QUINTILE_GAP_THRESHOLD (bidirectional — accepts decreasing pattern for
             fdr_avg). Failure → uninformative.
    Gate 3 — GW-window stability gate: the CI must exclude zero in ≥ 2 of the 3
             seasonal windows (early/mid/late). Failure → unstable.
    """
    base = {"signal_id": signal_id, "signal": signal, "position": position}
    if full_window_assoc is None:
        return {**base, "lens_status": "uninformative", "rationale": "insufficient observations"}
    if not full_window_assoc["ci_excludes_zero"]:
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI crosses zero [{full_window_assoc['ci_lower']:.3f}, {full_window_assoc['ci_upper']:.3f}]"}
    decision_relevant = (
        full_window_quintile is not None
        and abs(full_window_quintile["q5_q1_gap"]) >= QUINTILE_GAP_THRESHOLD
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
    """Run the full FIXTURE_GW lens validation study.

    Phase 1 — Load data and filter to study population (same-GW design; no lag shift).
    Phase 2 — For each (signal, position) slice: compute full-window and GW-window
               rank associations, quintile stratification, and DGW sensitivity.
    Phase 3 — Apply qualification gates, write evidence verdict, persist all CSVs.

    Returns the timestamped run output directory.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"LENS-FIXTURE-GW-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1: Load data (same-GW design — no target shift needed)
    # ------------------------------------------------------------------
    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart

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
        for pos in cfg["positions"]:
            pos_pop = population[(population["position_label"] == pos) & (population["gw"] >= cfg["gw_min"])]

            full_assoc = _measure_rank_association(pos_pop, signal, signal_id, pos, "full", TARGET)
            if full_assoc:
                full_assoc_rows.append(full_assoc)
            full_quintile = _stratify_by_quintile(pos_pop, signal, signal_id, pos, "full")
            if full_quintile:
                stratification_rows.append(full_quintile)

            if full_assoc and "is_dgw" in pos_pop.columns:
                no_dgw_assoc = _measure_rank_association(
                    pos_pop[~pos_pop["is_dgw"]], signal, signal_id, pos, "full_no_dgw", TARGET
                )
                if no_dgw_assoc:
                    full_assoc_rows.append(no_dgw_assoc)

            gw_window_assocs: list[dict | None] = []
            for window_name, (wlo, whi) in GW_WINDOWS.items():
                window_df = pos_pop[pos_pop["gw"].between(max(cfg["gw_min"], wlo), whi)]
                w_assoc = _measure_rank_association(window_df, signal, signal_id, pos, window_name, TARGET)
                gw_window_assocs.append(w_assoc)
                if w_assoc:
                    window_assoc_rows.append(w_assoc)
                w_quintile = _stratify_by_quintile(window_df, signal, signal_id, pos, window_name)
                if w_quintile:
                    stratification_rows.append(w_quintile)

            # ------------------------------------------------------------------
            # Phase 3 (per-slice): Qualify + build evidence
            # ------------------------------------------------------------------
            qualification = _apply_signal_qualification_gates(
                full_assoc, full_quintile, gw_window_assocs, signal, signal_id, pos
            )
            qualification_rows.append(qualification)
            evidence_rows.append(
                build_signal_verdict(signal, pos, full_assoc, gw_window_assocs, qualification)
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
    (out_dir / "run_metadata.json").write_text(json.dumps({
        "timestamp": ts, "db_path": str(db_path), "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED, "ci_level": CI_LEVEL,
        "minutes_threshold": MINUTES_THRESHOLD, "gw_max": GW_MAX,
        "gw_windows": {k: list(v) for k, v in GW_WINDOWS.items()},
        "quintile_gap_threshold": QUINTILE_GAP_THRESHOLD,
        "target": f"{TARGET} (same-GW)",
        "signals": {s: {**cfg, "signal_id": SIGNAL_IDS[s]} for s, cfg in SIGNALS.items()},
        "lens_status_legend": LENS_STATUS_LEGEND,
    }, indent=2))

    write_evidence(
        VALIDATE_DIR, LENS, TARGET, evidence_rows,
        evidence_run={"source": f"LENS-FIXTURE-GW-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<16} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 75)
    full_assoc_index = {(r["signal"], r["position"]): r for r in full_assoc_rows if r["gw_window"] == "full"}
    for q in qualification_rows:
        assoc = full_assoc_index.get((q["signal"], q["position"]))
        if assoc:
            print(f"{q['signal']:<16} {q['position']:<5} {assoc['rho']:>7.4f}  "
                  f"[{assoc['ci_lower']:>6.3f},{assoc['ci_upper']:>6.3f}]  "
                  f"{'Yes' if assoc['ci_excludes_zero'] else 'No':>8}  {q['lens_status']}")
    return out_dir


if __name__ == "__main__":
    run()
