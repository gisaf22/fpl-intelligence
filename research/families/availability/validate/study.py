"""Does recent minutes predict whether a player features next GW?

Mode: predictive · Stage: validate · Status: ACCEPTED — minutes_roll8 (DEF), minutes_roll3/roll8 (MID)
Population: target played_next_gw (binary); lag-1 respected; GW 3-38 (full season — holdout folded in, ADR-010)

ADLC §4 audit row C — reframes the raw minutes signal as an availability question
(after row B found minutes uninformative as a returns signal).
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
LENS = "avail"
TARGET_TOKEN = "played_next_gw"

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

GW_BLOCKS: dict[str, tuple[int, int]] = {
    "early": (3, 12),
    "mid":   (13, 26),
    "late":  (27, 38),
}

N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
QUINTILE_GAP_THRESHOLD = 0.10   # LENS_DESIGN.md §8 — binary target range [0,1]


def _correlation_record(
    df: pd.DataFrame, signal: str, signal_id: str, position: str,
    block: str, target: str
) -> dict | None:
    valid = df[[signal, target]].dropna()
    if len(valid) < 10:
        return None
    x, y = valid[signal].to_numpy(), valid[target].to_numpy()
    ci = bootstrap_spearman_ci(x, y, n_samples=N_BOOTSTRAP, ci_level=CI_LEVEL, seed=BOOTSTRAP_SEED)
    if ci is None:
        return None
    return {
        "signal_id": signal_id, "signal": signal, "position": position,
        "block": block, "target": target,
        "rho": ci["rho"], "ci_lower": ci["ci_lower"], "ci_upper": ci["ci_upper"],
        "n": ci["n"], "ci_excludes_zero": ci["excludes_zero"],
    }


def _quintile_record(
    df: pd.DataFrame, signal: str, signal_id: str, position: str,
    block: str, target: str, gap_threshold: float
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
        means_s = ranked.groupby("quintile", observed=True)[target].mean()
        if not all(f"Q{i}" in means_s.index for i in range(1, 6)):
            return None
        means = [float(means_s[f"Q{i}"]) for i in range(1, 6)]
        gap = means[4] - means[0]
        is_monotonic = all(means[i] <= means[i + 1] for i in range(4))
        return {
            "signal_id": signal_id, "signal": signal, "position": position,
            "block": block, "target": target,
            "q1_mean": round(means[0], 3), "q2_mean": round(means[1], 3),
            "q3_mean": round(means[2], 3), "q4_mean": round(means[3], 3),
            "q5_mean": round(means[4], 3),
            "q5_q1_gap": round(gap, 3), "is_monotonic": is_monotonic,
            "decision_relevant": bool(gap >= gap_threshold and is_monotonic),
        }
    except Exception:
        return None



def _classify(
    full_corr: dict | None, full_quint: dict | None,
    block_corrs: list[dict | None],
    signal: str, signal_id: str, position: str,
) -> dict:
    base = {"signal_id": signal_id, "signal": signal, "position": position}
    if full_corr is None:
        return {**base, "lens_status": "uninformative", "rationale": "insufficient observations"}
    if not full_corr["ci_excludes_zero"]:
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI crosses zero [{full_corr['ci_lower']:.3f}, {full_corr['ci_upper']:.3f}]"}
    if full_quint is None or not full_quint["decision_relevant"]:
        gap = f"{full_quint['q5_q1_gap']:.3f}" if full_quint else "N/A"
        mono = full_quint["is_monotonic"] if full_quint else "N/A"
        return {**base, "lens_status": "uninformative",
                "rationale": f"CI excludes zero but fails decision relevance (Q5-Q1={gap}, monotonic={mono})"}
    n_passing = sum(1 for b in block_corrs if b and b["ci_excludes_zero"])
    if n_passing >= 2:
        return {**base, "lens_status": "informative",
                "rationale": f"CI excludes zero, decision relevant, passes {n_passing}/3 GW blocks"}
    return {**base, "lens_status": "unstable",
            "rationale": f"CI excludes zero in aggregate but passes only {n_passing}/3 GW blocks"}


def run(db_path: Path = DB_PATH) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / f"LENS-AVAIL-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart

    state = state.sort_values(["player_id", "gw"]).copy()
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)
    state["minutes_next_gw"] = state.groupby("player_id")["minutes"].shift(-1)
    state["played_next_gw"] = (
        state["minutes_next_gw"].ge(60).astype(float)
        .where(state["minutes_next_gw"].notna())
    )

    pop = state[
        (state["minutes"] >= MINUTES_THRESHOLD) & (state["gw"] <= GW_MAX)
    ].copy()

    corr_rows: list[dict] = []
    block_rows: list[dict] = []
    quint_rows: list[dict] = []
    classify_rows: list[dict] = []
    evidence_rows: list[dict] = []

    for signal, cfg in SIGNALS.items():
        signal_id = SIGNAL_IDS[signal]
        gw_min = cfg["gw_min"]

        for pos in cfg["positions"]:
            pos_pop = pop[(pop["position_label"] == pos) & (pop["gw"] >= gw_min)]

            # Primary target: played_next_gw
            for target, gap_thr in [("played_next_gw", QUINTILE_GAP_THRESHOLD),
                                     ("total_points_next_gw", 1.0)]:
                full_corr = _correlation_record(pos_pop, signal, signal_id, pos, "full", target)
                if full_corr:
                    corr_rows.append(full_corr)

                full_quint = _quintile_record(pos_pop, signal, signal_id, pos, "full", target, gap_thr)
                if full_quint:
                    quint_rows.append(full_quint)

                # DGW sensitivity
                if full_corr and "is_dgw" in pos_pop.columns:
                    dgw_rec = _correlation_record(
                        pos_pop[~pos_pop["is_dgw"]], signal, signal_id, pos, "full_no_dgw", target
                    )
                    if dgw_rec:
                        corr_rows.append(dgw_rec)

            # Block stratification — primary target only
            block_corrs: list[dict | None] = []
            for block_name, (blo, bhi) in GW_BLOCKS.items():
                effective_lo = max(gw_min, blo)
                block_df = pos_pop[pos_pop["gw"].between(effective_lo, bhi)]
                b = _correlation_record(block_df, signal, signal_id, pos, block_name, "played_next_gw")
                block_corrs.append(b)
                if b:
                    block_rows.append(b)
                q = _quintile_record(
                    block_df, signal, signal_id, pos, block_name,
                    "played_next_gw", QUINTILE_GAP_THRESHOLD,
                )
                if q:
                    quint_rows.append(q)

            # Classify on primary target
            primary_full = next(
                (r for r in corr_rows if r["signal"] == signal and r["position"] == pos
                 and r["block"] == "full" and r["target"] == "played_next_gw"), None
            )
            primary_quint = next(
                (r for r in quint_rows if r["signal"] == signal and r["position"] == pos
                 and r["block"] == "full" and r["target"] == "played_next_gw"), None
            )
            cls = _classify(primary_full, primary_quint, block_corrs, signal, signal_id, pos)
            classify_rows.append(cls)
            evidence_rows.append(build_evidence_row(signal, pos, primary_full, block_corrs, cls))

    pd.DataFrame(corr_rows).to_csv(out_dir / "correlation_results.csv", index=False)
    pd.DataFrame(block_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(quint_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(classify_rows).to_csv(out_dir / "classification_summary.csv", index=False)

    meta = {
        "timestamp": ts, "db_path": str(db_path),
        "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED,
        "ci_level": CI_LEVEL, "minutes_threshold": MINUTES_THRESHOLD,
        "gw_max": GW_MAX, "gw_blocks": {k: list(v) for k, v in GW_BLOCKS.items()},
        "quintile_gap_threshold_primary": QUINTILE_GAP_THRESHOLD,
        "quintile_gap_threshold_secondary": 1.0,
        "primary_target": "played_next_gw",
        "signals": {s: {**cfg, "signal_id": SIGNAL_IDS[s]} for s, cfg in SIGNALS.items()},
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2))

    write_evidence(
        VALIDATE_DIR, LENS, TARGET_TOKEN, evidence_rows,
        evidence_run={"source": f"LENS-AVAIL-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<16} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 75)
    full_primary = {(r["signal"], r["position"]): r for r in corr_rows
                    if r["block"] == "full" and r["target"] == "played_next_gw"}
    for cls in classify_rows:
        corr = full_primary.get((cls["signal"], cls["position"]))
        if corr:
            print(
                f"{cls['signal']:<16} {cls['position']:<5} "
                f"{corr['rho']:>7.4f}  [{corr['ci_lower']:>6.3f},{corr['ci_upper']:>6.3f}]  "
                f"{'Yes' if corr['ci_excludes_zero'] else 'No':>8}  {cls['lens_status']}"
            )

    return out_dir


if __name__ == "__main__":
    run()
