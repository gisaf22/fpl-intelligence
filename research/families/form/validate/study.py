"""Does rolling attacking output (xGI) predict next-GW returns?

Mode: predictive · Stage: validate · Status: PARTIAL — xgi_roll3 (DEF), xgi_roll5 (DEF, MID) approved
Population: minutes>=60; lag-1 respected; GW 3-38 (full season — holdout folded in, ADR-010)

ADLC §4 audit row B. Note: the §4 table frames this row as "minutes as a returns
signal — REJECTED"; the FORM lens as implemented evaluates rolling xGI form signals
and approved xgi_roll3/roll5 for DEF/MID. The minutes-as-returns rejection is carried
by the AVAIL reframing (row C), not here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load as load_mart
from research.families.evidence_record import build_evidence_row, write_evidence
from research.kernels.resampling import bootstrap_spearman_ci

RUNS_DIR = Path(__file__).resolve().parents[4] / "research" / "runs"
VALIDATE_DIR = Path(__file__).parent
LENS = "form"
TARGET_TOKEN = "total_points"

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

NAIVE_BASELINES = {"points_roll3", "points_roll5"}

MINUTES_THRESHOLD = 60     # LENS_DESIGN.md §4, G-EDA1-04
GW_MAX = 38                # LENS_DESIGN.md §5, G-EDA1-02

GW_BLOCKS: dict[str, tuple[int, int]] = {   # LENS_DESIGN.md §6, G-EDA5-01
    "early": (3, 12),
    "mid":   (13, 26),
    "late":  (27, 38),
}

N_BOOTSTRAP = 2000         # LENS_DESIGN.md §7
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
QUINTILE_GAP_THRESHOLD = 1.0  # LENS_DESIGN.md §9


# ---------------------------------------------------------------------------
# Pre-run assertion
# ---------------------------------------------------------------------------

def _assert_lag_alignment(state: pd.DataFrame, out_dir: Path) -> None:
    """Verify lag-1 alignment. Writes lag_alignment_check.txt. Raises on failure."""
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

def _correlation_record(
    df: pd.DataFrame, signal: str, signal_id: str, position: str, block: str
) -> dict | None:
    valid = df[[signal, "total_points_next_gw"]].dropna()
    if len(valid) < 10:
        return None
    x, y = valid[signal].to_numpy(), valid["total_points_next_gw"].to_numpy()
    ci = bootstrap_spearman_ci(x, y, n_samples=N_BOOTSTRAP, ci_level=CI_LEVEL, seed=BOOTSTRAP_SEED)
    if ci is None:
        return None
    return {
        "signal_id": signal_id,
        "signal": signal,
        "position": position,
        "block": block,
        "rho": ci["rho"],
        "ci_lower": ci["ci_lower"],
        "ci_upper": ci["ci_upper"],
        "n": ci["n"],
        "ci_excludes_zero": ci["excludes_zero"],
    }


def _quintile_record(
    df: pd.DataFrame, signal: str, signal_id: str, position: str, block: str
) -> dict | None:
    valid = df[[signal, "total_points_next_gw"]].dropna()
    if len(valid) < 25:
        return None
    try:
        ranked = valid.copy()
        # Rank globally within this (signal, position, block) slice
        ranked["quintile"] = pd.qcut(
            ranked[signal].rank(method="first"), 5,
            labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
        )
        means_s = ranked.groupby("quintile", observed=True)["total_points_next_gw"].mean()
        if not all(f"Q{i}" in means_s.index for i in range(1, 6)):
            return None
        means = [float(means_s[f"Q{i}"]) for i in range(1, 6)]
        gap = means[4] - means[0]
        is_monotonic = all(means[i] <= means[i + 1] for i in range(4))
        return {
            "signal_id": signal_id,
            "signal": signal,
            "position": position,
            "block": block,
            "q1_mean": round(means[0], 3),
            "q2_mean": round(means[1], 3),
            "q3_mean": round(means[2], 3),
            "q4_mean": round(means[3], 3),
            "q5_mean": round(means[4], 3),
            "q5_q1_gap": round(gap, 3),
            "is_monotonic": is_monotonic,
            "decision_relevant": bool(gap >= QUINTILE_GAP_THRESHOLD and is_monotonic),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(
    full_corr: dict | None,
    full_quint: dict | None,
    block_corrs: list[dict | None],
    signal: str,
    signal_id: str,
    position: str,
    naive_rho: float | None,
) -> dict:
    """Apply LENS_DESIGN.md §8 decision sequence."""
    base = {"signal_id": signal_id, "signal": signal, "position": position}

    clears_naive: bool | None = None
    if naive_rho is not None and full_corr is not None:
        clears_naive = bool(full_corr["rho"] > naive_rho)

    if full_corr is None:
        return {**base, "lens_status": "uninformative",
                "rationale": "insufficient observations", "clears_naive_baseline": clears_naive}

    # Step 1: CI gate
    if not full_corr["ci_excludes_zero"]:
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI crosses zero [{full_corr['ci_lower']:.3f}, {full_corr['ci_upper']:.3f}]",
                "clears_naive_baseline": clears_naive}

    # Step 2: decision relevance gate
    if full_quint is None or not full_quint["decision_relevant"]:
        gap = f"{full_quint['q5_q1_gap']:.2f}" if full_quint else "N/A"
        mono = full_quint["is_monotonic"] if full_quint else "N/A"
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI excludes zero but fails decision relevance (Q5-Q1={gap}, monotonic={mono})",
                "clears_naive_baseline": clears_naive}

    # Step 3: block stability gate
    n_passing = sum(1 for b in block_corrs if b and b["ci_excludes_zero"])
    if n_passing >= 2:
        status = "informative"
        rationale = f"CI excludes zero, decision relevant, passes {n_passing}/3 GW blocks"
    else:
        status = "unstable"
        rationale = f"CI excludes zero in aggregate but passes only {n_passing}/3 GW blocks"

    return {**base, "lens_status": status, "rationale": rationale,
            "clears_naive_baseline": clears_naive}


# ---------------------------------------------------------------------------
# Main run entry point
# ---------------------------------------------------------------------------

def run(db_path: Path = DB_PATH) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"LENS-FORM-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart

    # Build lag-1 target within player groups (LENS_DESIGN.md §3, G-EDA0-01)
    state = state.sort_values(["player_id", "gw"]).copy()
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)

    # Derive the form baselines this study needs but the governed mart deliberately does
    # not materialize: points_roll3/5 are NAIVE_BASELINES (blocked as form proxies, kept
    # only as a bar-to-beat) and goals_scored_roll3 is excluded — none are governed feature
    # columns. Research derives them here with the DAL's exact lag-1 convention
    # (shift(1).rolling(N).mean(): GW N uses only GWs 1..N-1, no future leakage). See ADR-010
    # (DAL owns governed operational features; research owns evaluation-only derivations).
    for col, window in (("points_roll3", 3), ("points_roll5", 5)):
        state[col] = state.groupby("player_id")["total_points"].transform(
            lambda x, w=window: x.shift(1).rolling(w, min_periods=1).mean()
        )
    state["goals_scored_roll3"] = state.groupby("player_id")["goals_scored"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    # Pre-run assertion (LENS_DESIGN.md §11)
    print("Running lag alignment assertion...")
    _assert_lag_alignment(state, out_dir)
    print("  Assertion passed.")

    # Primary population: minutes >= 60, GW <= 33 (LENS_DESIGN.md §4, §5)
    pop = state[
        (state["minutes"] >= MINUTES_THRESHOLD) & (state["gw"] <= GW_MAX)
    ].copy()

    corr_rows: list[dict] = []
    block_rows: list[dict] = []
    quint_rows: list[dict] = []
    classify_rows: list[dict] = []
    evidence_rows: list[dict] = []

    # Naive baseline rho per position (points_roll3, full window)
    # Used to set clears_naive_baseline for non-baseline signals
    naive_rho_by_pos: dict[str, float | None] = {}
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = pop[(pop["position_label"] == pos) & (pop["gw"] >= 3)]
        rec = _correlation_record(pos_df, "points_roll3", "FORM-004", pos, "full")
        naive_rho_by_pos[pos] = rec["rho"] if rec else None

    for signal, cfg in SIGNALS.items():
        signal_id = SIGNAL_IDS[signal]
        gw_min = cfg["gw_min"]

        for pos in cfg["positions"]:
            pos_pop = pop[(pop["position_label"] == pos) & (pop["gw"] >= gw_min)]

            # Full study window
            full_corr = _correlation_record(pos_pop, signal, signal_id, pos, "full")
            if full_corr:
                corr_rows.append(full_corr)

            full_quint = _quintile_record(pos_pop, signal, signal_id, pos, "full")
            if full_quint:
                quint_rows.append(full_quint)

            # DGW sensitivity: re-run excluding DGW rows
            if full_corr and "is_dgw" in pos_pop.columns:
                no_dgw = pos_pop[~pos_pop["is_dgw"]]
                dgw_rec = _correlation_record(no_dgw, signal, signal_id, pos, "full_no_dgw")
                if dgw_rec:
                    corr_rows.append(dgw_rec)

            # GW block stratification (LENS_DESIGN.md §6)
            block_corrs: list[dict | None] = []
            for block_name, (blo, bhi) in GW_BLOCKS.items():
                effective_lo = max(gw_min, blo)
                block_df = pos_pop[pos_pop["gw"].between(effective_lo, bhi)]
                b_corr = _correlation_record(block_df, signal, signal_id, pos, block_name)
                block_corrs.append(b_corr)
                if b_corr:
                    block_rows.append(b_corr)
                b_quint = _quintile_record(block_df, signal, signal_id, pos, block_name)
                if b_quint:
                    quint_rows.append(b_quint)

            # Classification (LENS_DESIGN.md §8)
            naive_rho = naive_rho_by_pos.get(pos) if signal not in NAIVE_BASELINES else None
            cls = _classify(full_corr, full_quint, block_corrs, signal, signal_id, pos, naive_rho)
            classify_rows.append(cls)
            evidence_rows.append(build_evidence_row(signal, pos, full_corr, block_corrs, cls))

    # Write artefacts (LENS_DESIGN.md §10)
    pd.DataFrame(corr_rows).to_csv(out_dir / "correlation_results.csv", index=False)
    pd.DataFrame(block_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(quint_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(classify_rows).to_csv(out_dir / "classification_summary.csv", index=False)

    meta = {
        "timestamp": ts,
        "db_path": str(db_path),
        "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "ci_level": CI_LEVEL,
        "minutes_threshold": MINUTES_THRESHOLD,
        "gw_max": GW_MAX,
        "gw_blocks": {k: list(v) for k, v in GW_BLOCKS.items()},
        "quintile_gap_threshold": QUINTILE_GAP_THRESHOLD,
        "signals": {s: {**cfg, "signal_id": SIGNAL_IDS[s]} for s, cfg in SIGNALS.items()},
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2))

    # Evidence verdict record (ADR-009 Phase C): the committed machine half consumed by
    # model/governance/generate_evaluation_metadata.py. Judgment lives in annotations.yaml.
    write_evidence(
        VALIDATE_DIR, LENS, TARGET_TOKEN, evidence_rows,
        evidence_run={"source": f"LENS-FORM-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    # Summary print
    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<22} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 80)
    full_corrs = {(r["signal"], r["position"]): r for r in corr_rows if r["block"] == "full"}
    for cls in classify_rows:
        key = (cls["signal"], cls["position"])
        corr = full_corrs.get(key)
        if corr:
            print(
                f"{cls['signal']:<22} {cls['position']:<5} "
                f"{corr['rho']:>7.4f}  "
                f"[{corr['ci_lower']:>6.3f},{corr['ci_upper']:>6.3f}]  "
                f"{'Yes' if corr['ci_excludes_zero'] else 'No':>8}  "
                f"{cls['lens_status']}"
            )
        else:
            print(f"{cls['signal']:<22} {cls['position']:<5} {'N/A':>7}  {'':^17}  {'':>8}  {cls['lens_status']}")

    return out_dir


if __name__ == "__main__":
    run()
