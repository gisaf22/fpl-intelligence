"""Does rolling attacking output (xGI) predict next-GW returns?

Mode: predictive · Stage: validate · Status: PARTIAL — xgi_roll3 (DEF), xgi_roll5 (DEF, MID) approved
Population: minutes>=60; lag-1 respected; GW 3-38 (full season — holdout folded in, ADR-010)

ADLC §4 audit row B. Note: the §4 table frames this row as "minutes as a returns
signal — REJECTED"; the FORM lens as implemented evaluates rolling xGI form signals
and approved xgi_roll3/roll5 for DEF/MID. The minutes-as-returns rejection is carried
by the AVAIL reframing (row C), not here.

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
LENS = "form"
TARGET = "total_points_next_gw"   # lag-1: signal at GW N predicts points at GW N+1

# LENS_DESIGN.md §2 — registered signals, valid positions, GW lower bounds
# Position label from DAL is 'GKP', not 'GK'
SIGNALS: dict[str, dict] = {
    "xgi_roll3":          {"positions": ["DEF", "MID", "FWD"], "gw_min": 3},
    "xgi_roll5":          {"positions": ["DEF", "MID", "FWD"], "gw_min": 6},
    "goals_scored_roll3": {"positions": ["DEF", "MID", "FWD"], "gw_min": 3},
    "points_roll3":       {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "points_roll5":       {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 6},
    "minutes_roll3":      {"positions": ["DEF", "MID", "FWD"], "gw_min": 3},
}

SIGNAL_IDS: dict[str, str] = {
    "xgi_roll3":          "FORM-001",
    "xgi_roll5":          "FORM-002",
    "goals_scored_roll3": "FORM-003",
    "points_roll3":       "FORM-004",
    "points_roll5":       "FORM-005",
    "minutes_roll3":      "FORM-006",
}

# points_roll3/5 are included only as a bar-to-beat, not as governed signals.
# Any other signal must post rho > naive_rho to be considered practically useful.
NAIVE_BASELINES = {"points_roll3", "points_roll5"}

MINUTES_THRESHOLD = 60     # LENS_DESIGN.md §4, G-EDA1-04
GW_MAX = 38                # LENS_DESIGN.md §5, G-EDA1-02

GW_WINDOWS: dict[str, tuple[int, int]] = {   # LENS_DESIGN.md §6, G-EDA5-01
    "early": (3, 12),
    "mid":   (13, 26),
    "late":  (27, 38),
}

N_BOOTSTRAP = 2000         # LENS_DESIGN.md §7
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
QUINTILE_GAP_THRESHOLD = 1.0  # LENS_DESIGN.md §9 — minimum Q5-Q1 gap in points

# Written into run_metadata.json so output files are self-interpreting without
# requiring the reader to open this source file.
LENS_STATUS_LEGEND = {
    "informative": "passes all 3 qualification gates; recommended for governance inclusion",
    "uninformative": "failed CI gate or decision-relevance gate",
    "unstable": "passed CI + relevance but failed 2-of-3 GW-window stability gate",
}


# ---------------------------------------------------------------------------
# Pre-run assertion
# ---------------------------------------------------------------------------

def _assert_lag_alignment(state: pd.DataFrame, out_dir: Path) -> None:
    """Assert lag-1 alignment: signal at GW N must use only data from GWs 1..N-1.

    Future leakage would mean the signal at GW N already incorporates the GW N
    outcome it is supposed to predict — inflating correlation artificially.
    Writes lag_alignment_check.txt. Raises AssertionError on failure.
    """
    lines: list[str] = []
    failed = False

    # Check 1: GW 1 must have NaN for roll3 signals (warmup row)
    gw1 = state[state["gw"] == 1]
    gw1_roll3_null = gw1["xgi_roll3"].isna().all()
    if gw1_roll3_null:
        lines.append("PASS [1] GW 1 xgi_roll3 rows are NaN (warmup confirmed).")
    else:
        lines.append("FAIL [1] GW 1 xgi_roll3 rows contain non-null values — warmup not enforced.")
        failed = True

    # Check 2: Lag-1 target alignment for a sample of players.
    # total_points_next_gw at GW N must equal total_points at GW N+1.
    # Sample up to 5 players that have at least 3 GW rows to provide population-level coverage.
    all_player_ids = state["player_id"].unique()
    sample_ids = [
        pid for pid in sorted(all_player_ids)
        if len(state[state["player_id"] == pid]) >= 3
    ][:5]
    total_mismatches = 0
    checked_players = 0
    for pid in sample_ids:
        pdata = state[state["player_id"] == pid].sort_values("gw")
        for _, row in pdata.iterrows():
            if pd.isna(row["total_points_next_gw"]):
                continue
            nxt = pdata[pdata["gw"] == row["gw"] + 1]
            if not nxt.empty and abs(row["total_points_next_gw"] - nxt["total_points"].iloc[0]) > 1e-6:
                total_mismatches += 1
        checked_players += 1
    if total_mismatches == 0:
        lines.append(
            f"PASS [2] Lag-1 target matches total_points at GW N+1 "
            f"for {checked_players} sampled players (ids: {sample_ids})."
        )
    else:
        lines.append(
            f"FAIL [2] {total_mismatches} lag-1 target mismatches across "
            f"{checked_players} sampled players (ids: {sample_ids})."
        )
        failed = True

    # Check 3: xgi_roll3 at GW 4 = mean(xgi at GW 1, 2, 3) for the first sampled player.
    # GW 4 is the first row with a full 3-period window.
    check_pid = sample_ids[0] if sample_ids else None
    if check_pid is not None:
        pdata = state[state["player_id"] == check_pid].sort_values("gw")
        p_gw4_roll3 = pdata[pdata["gw"] == 4]["xgi_roll3"].values
        p_gw123_xgi = pdata[pdata["gw"].isin([1, 2, 3])]["xgi"].mean()
        if len(p_gw4_roll3) == 1 and abs(p_gw4_roll3[0] - p_gw123_xgi) < 1e-4:
            lines.append(
                f"PASS [3] xgi_roll3 at GW 4 = {p_gw4_roll3[0]:.4f} "
                f"matches mean(GW 1-3 xgi) = {p_gw123_xgi:.4f} for player {check_pid}."
            )
        else:
            val = p_gw4_roll3[0] if len(p_gw4_roll3) == 1 else "N/A"
            lines.append(
                f"WARN [3] xgi_roll3 at GW 4 = {val}, mean(GW 1-3 xgi) = {p_gw123_xgi:.4f} "
                f"for player {check_pid}. Check min_periods setting in DAL state layer."
            )
            # Warn only — min_periods < 3 is a known DAL characteristic documented in LENS_DESIGN §5

    status = "FAIL" if failed else "PASS"
    header = f"Lag alignment check: {status}\nProduced: {datetime.now().isoformat()}\n"
    (out_dir / "lag_alignment_check.txt").write_text(header + "\n".join(lines) + "\n")

    if failed:
        raise AssertionError(
            f"Lag alignment check FAILED. See {out_dir / 'lag_alignment_check.txt'}."
        )


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
        signal_id:  Registry identifier (e.g. ``"FORM-001"``).
        position:   Position label for this slice (e.g. ``"DEF"``).
        gw_window:  Window label — ``"full"``, ``"early"``, ``"mid"``, ``"late"``,
                    or ``"full_no_dgw"`` for DGW sensitivity.
        target:     Outcome column name. Passed explicitly so the call site
                    documents whether this is a lag-1 or same-GW target.

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
        "signal_id": signal_id,
        "signal": signal,
        "position": position,
        "gw_window": gw_window,
        "target": target,
        "rho": ci["rho"],
        "ci_lower": ci["ci_lower"],
        "ci_upper": ci["ci_upper"],
        "n": ci["n"],
        "ci_excludes_zero": bool(ci["ci_lower"] > 0 or ci["ci_upper"] < 0),
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
# Signal qualification gates  (LENS_DESIGN.md §8)
# ---------------------------------------------------------------------------

def _apply_signal_qualification_gates(
    full_window_assoc: dict | None,
    full_window_quintile: dict | None,
    gw_window_assocs: list[dict | None],
    signal: str,
    signal_id: str,
    position: str,
    naive_rho: float | None,
) -> dict:
    """Apply the three-gate decision protocol to determine a signal's qualification verdict.

    Gate 1 — CI gate: the bootstrapped Spearman CI for the full study window must
             exclude zero. Failure → uninformative.
    Gate 2 — Decision relevance gate: quintile stratification must show a Q5-Q1 gap
             ≥ QUINTILE_GAP_THRESHOLD and a monotone-increasing pattern. Signals that
             correlate weakly but produce no usable rank separation fail here.
             Failure → uninformative.
    Gate 3 — GW-window stability gate: the CI must exclude zero in ≥ 2 of the 3
             seasonal windows (early/mid/late). Passing only the full-season aggregate
             suggests the association is driven by a single sub-period.
             Failure → unstable (collapses to uninformative in governance).

    ``naive_rho`` is the baseline rho for points_roll3 at this position; it is used
    only to compute the ``clears_naive_baseline`` diagnostic flag, not as a gate.
    """
    base = {"signal_id": signal_id, "signal": signal, "position": position}

    clears_naive: bool | None = None
    if naive_rho is not None and full_window_assoc is not None:
        clears_naive = bool(full_window_assoc["rho"] > naive_rho)

    if full_window_assoc is None:
        return {**base, "lens_status": "uninformative",
                "rationale": "insufficient observations", "clears_naive_baseline": clears_naive}

    # Gate 1: CI gate
    if not full_window_assoc["ci_excludes_zero"]:
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI crosses zero [{full_window_assoc['ci_lower']:.3f}, {full_window_assoc['ci_upper']:.3f}]",
                "clears_naive_baseline": clears_naive}

    # Gate 2: decision relevance gate
    decision_relevant = (
        full_window_quintile is not None
        and full_window_quintile["q5_q1_gap"] >= QUINTILE_GAP_THRESHOLD
        and full_window_quintile["is_monotonic"]
    )
    if not decision_relevant:
        gap = f"{full_window_quintile['q5_q1_gap']:.2f}" if full_window_quintile else "N/A"
        mono = full_window_quintile["is_monotonic"] if full_window_quintile else "N/A"
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI excludes zero but fails decision relevance (Q5-Q1={gap}, monotonic={mono})",
                "clears_naive_baseline": clears_naive}

    # Gate 3: GW-window stability gate
    n_stable_windows = sum(1 for b in gw_window_assocs if b and b["ci_excludes_zero"])
    if n_stable_windows >= 2:
        status = "informative"
        rationale = f"CI excludes zero, decision relevant, passes {n_stable_windows}/3 GW windows"
    else:
        status = "unstable"
        rationale = f"CI excludes zero in aggregate but passes only {n_stable_windows}/3 GW windows"

    return {**base, "lens_status": status, "rationale": rationale,
            "clears_naive_baseline": clears_naive}


# ---------------------------------------------------------------------------
# Main run entry point
# ---------------------------------------------------------------------------

def run(db_path: Path = DB_PATH) -> Path:
    """Run the full FORM lens validation study.

    Phase 1 — Load data, derive evaluation-only features, assert lag-1 alignment.
    Phase 2 — For each (signal, position) slice: compute full-window and GW-window
               rank associations, quintile stratification, and DGW sensitivity.
    Phase 3 — Apply qualification gates, write evidence verdict, persist all CSVs.

    Returns the timestamped run output directory.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"LENS-FORM-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1: Load + feature derivation + lag alignment assertion
    # ------------------------------------------------------------------
    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart
    state = state.sort_values(["player_id", "gw"]).copy()

    # Derive the lag-1 target: total_points at GW N+1, attached to GW N row.
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)

    # Derive evaluation-only features. These are deliberately not materialised in
    # the governed DAL mart (ADR-010): points_roll3/5 are NAIVE_BASELINES (bar-to-beat
    # only) and goals_scored_roll3 is excluded from governance. Research derives them
    # here using the DAL's exact lag-1 convention: shift(1).rolling(N).mean() so that
    # GW N uses only GWs 1..N-1, with no future leakage.
    for col, window in (("points_roll3", 3), ("points_roll5", 5)):
        state[col] = state.groupby("player_id")["total_points"].transform(
            lambda x, w=window: x.shift(1).rolling(w, min_periods=1).mean()
        )
    state["goals_scored_roll3"] = state.groupby("player_id")["goals_scored"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    print("Running lag alignment assertion...")
    _assert_lag_alignment(state, out_dir)
    print("  Assertion passed.")

    # Study population: players who started (≥60 min), within the governed GW range.
    population = state[
        (state["minutes"] >= MINUTES_THRESHOLD) & (state["gw"] <= GW_MAX)
    ].copy()
    assert_population_gate(population, GW_WINDOWS)

    # ------------------------------------------------------------------
    # Phase 2: Per-(signal, position) rank association + stratification
    # ------------------------------------------------------------------

    # Naive baseline rho per position — used to set clears_naive_baseline diagnostic.
    naive_rho_by_position: dict[str, float | None] = {}
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = population[(population["position_label"] == pos) & (population["gw"] >= 3)]
        rec = _measure_rank_association(pos_df, "points_roll3", "FORM-004", pos, "full", TARGET)
        naive_rho_by_position[pos] = rec["rho"] if rec else None

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

            # Full study window association
            full_assoc = _measure_rank_association(pos_pop, signal, signal_id, pos, "full", TARGET)
            if full_assoc:
                full_assoc_rows.append(full_assoc)

            full_quintile = _stratify_by_quintile(pos_pop, signal, signal_id, pos, "full", TARGET)
            if full_quintile:
                stratification_rows.append(full_quintile)

            # DGW sensitivity: check whether double-gameweek rows inflate the association
            if full_assoc and "is_dgw" in pos_pop.columns:
                no_dgw_assoc = _measure_rank_association(
                    pos_pop[~pos_pop["is_dgw"]], signal, signal_id, pos, "full_no_dgw", TARGET
                )
                if no_dgw_assoc:
                    full_assoc_rows.append(no_dgw_assoc)

            # GW-window stratification: early / mid / late (LENS_DESIGN.md §6)
            gw_window_assocs: list[dict | None] = []
            for window_name, (wlo, whi) in GW_WINDOWS.items():
                effective_lo = max(gw_min, wlo)
                window_df = pos_pop[pos_pop["gw"].between(effective_lo, whi)]
                w_assoc = _measure_rank_association(window_df, signal, signal_id, pos, window_name, TARGET)
                gw_window_assocs.append(w_assoc)
                if w_assoc:
                    window_assoc_rows.append(w_assoc)
                w_quintile = _stratify_by_quintile(window_df, signal, signal_id, pos, window_name, TARGET)
                if w_quintile:
                    stratification_rows.append(w_quintile)

            # ------------------------------------------------------------------
            # Phase 3 (per-slice): Apply qualification gates + build evidence
            # ------------------------------------------------------------------
            naive_rho = naive_rho_by_position.get(pos) if signal not in NAIVE_BASELINES else None
            qualification = _apply_signal_qualification_gates(
                full_assoc, full_quintile, gw_window_assocs,
                signal, signal_id, pos, naive_rho,
            )
            qualification_rows.append(qualification)
            evidence_rows.append(
                build_signal_verdict(signal, pos, full_assoc, gw_window_assocs, qualification)
            )

    # ------------------------------------------------------------------
    # Phase 3 (global): Persist artefacts  (LENS_DESIGN.md §10)
    # ------------------------------------------------------------------
    pd.DataFrame(full_assoc_rows + window_assoc_rows).to_csv(
        out_dir / "correlation_results.csv", index=False
    )
    pd.DataFrame(window_assoc_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(stratification_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(qualification_rows).to_csv(out_dir / "classification_summary.csv", index=False)

    meta = {
        "timestamp": ts,
        "db_path": str(db_path),
        "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "ci_level": CI_LEVEL,
        "minutes_threshold": MINUTES_THRESHOLD,
        "gw_max": GW_MAX,
        "gw_windows": {k: list(v) for k, v in GW_WINDOWS.items()},
        "quintile_gap_threshold": QUINTILE_GAP_THRESHOLD,
        "target": TARGET,
        "signals": {s: {**cfg, "signal_id": SIGNAL_IDS[s]} for s, cfg in SIGNALS.items()},
        "lens_status_legend": LENS_STATUS_LEGEND,
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2))

    # Evidence verdict record (ADR-009 Phase C): the committed machine half consumed by
    # model/governance/generate_evaluation_metadata.py. Judgment lives in annotations.yaml.
    write_evidence(
        VALIDATE_DIR, LENS, TARGET, evidence_rows,
        evidence_run={"source": f"LENS-FORM-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    # Summary print
    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<22} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 80)
    full_assoc_index = {(r["signal"], r["position"]): r for r in full_assoc_rows if r["gw_window"] == "full"}
    for q in qualification_rows:
        key = (q["signal"], q["position"])
        assoc = full_assoc_index.get(key)
        if assoc:
            print(
                f"{q['signal']:<22} {q['position']:<5} "
                f"{assoc['rho']:>7.4f}  "
                f"[{assoc['ci_lower']:>6.3f},{assoc['ci_upper']:>6.3f}]  "
                f"{'Yes' if assoc['ci_excludes_zero'] else 'No':>8}  "
                f"{q['lens_status']}"
            )
        else:
            print(f"{q['signal']:<22} {q['position']:<5} {'N/A':>7}  {'':^17}  {'':>8}  {q['lens_status']}")

    return out_dir


if __name__ == "__main__":
    run()
