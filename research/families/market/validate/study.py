"""Do market signals (transfers, ownership, price) predict returns?

Mode: predictive · Stage: validate · Status: PARTIAL — transfers_in (DEF, MID), purchase_price (DEF, FWD†), ownership_count (MID) approved
Population: minutes>=60; lag-1 respected; GW 3-38 (full season — holdout folded in, ADR-010)

ADLC §4 audit (unlettered fixture/market lens row).
† FWD purchase_price weakens to uninformative once GW34-38 fold in (ENG-02 regime reversal, full-season).
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
from research.kernels.stratification import quintile_stratification

RUNS_DIR = Path(__file__).resolve().parents[4] / "research" / "runs"
VALIDATE_DIR = Path(__file__).parent
LENS = "market"
TARGET_TOKEN = "total_points"

SIGNALS: dict[str, dict] = {
    "transfers_in":      {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "ownership_count":   {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
    "purchase_price":    {"positions": ["GKP", "DEF", "MID", "FWD"], "gw_min": 3},
}

SIGNAL_IDS: dict[str, str] = {
    "transfers_in":      "MARKET-001",
    "ownership_count":   "MARKET-003",
    "purchase_price":    "MARKET-004",
}

MINUTES_THRESHOLD = 60
GW_MAX = 38
GW_BLOCKS: dict[str, tuple[int, int]] = {
    "early": (3, 12), "mid": (13, 26), "late": (27, 38),
}
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
QUINTILE_GAP_THRESHOLD = 1.0


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
        "signal_id": signal_id, "signal": signal, "position": position, "block": block,
        "rho": ci["rho"], "ci_lower": ci["ci_lower"], "ci_upper": ci["ci_upper"],
        "n": ci["n"], "ci_excludes_zero": ci["excludes_zero"],
    }


def _quintile_record(
    df: pd.DataFrame, signal: str, signal_id: str, position: str, block: str
) -> dict | None:
    return quintile_stratification(
        df, signal, signal_id, position, block,
        target="total_points_next_gw", gap_threshold=QUINTILE_GAP_THRESHOLD, bidirectional=False,
    )



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
    out_dir = RUNS_DIR / f"LENS-MARKET-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading DAL data from {db_path}...")
    state = load_mart(db_path=db_path).mart

    state = state.sort_values(["player_id", "gw"]).copy()
    state["total_points_next_gw"] = state.groupby("player_id")["total_points"].shift(-1)

    pop = state[(state["minutes"] >= MINUTES_THRESHOLD) & (state["gw"] <= GW_MAX)].copy()

    corr_rows, block_rows, quint_rows, classify_rows = [], [], [], []
    evidence_rows: list[dict] = []

    for signal, cfg in SIGNALS.items():
        signal_id = SIGNAL_IDS[signal]
        for pos in cfg["positions"]:
            pos_pop = pop[(pop["position_label"] == pos) & (pop["gw"] >= cfg["gw_min"])]

            full_corr = _correlation_record(pos_pop, signal, signal_id, pos, "full")
            if full_corr:
                corr_rows.append(full_corr)
            full_quint = _quintile_record(pos_pop, signal, signal_id, pos, "full")
            if full_quint:
                quint_rows.append(full_quint)

            if full_corr and "is_dgw" in pos_pop.columns:
                dgw_rec = _correlation_record(pos_pop[~pos_pop["is_dgw"]], signal, signal_id, pos, "full_no_dgw")
                if dgw_rec:
                    corr_rows.append(dgw_rec)

            block_corrs = []
            for block_name, (blo, bhi) in GW_BLOCKS.items():
                block_df = pos_pop[pos_pop["gw"].between(max(cfg["gw_min"], blo), bhi)]
                b = _correlation_record(block_df, signal, signal_id, pos, block_name)
                block_corrs.append(b)
                if b:
                    block_rows.append(b)
                q = _quintile_record(block_df, signal, signal_id, pos, block_name)
                if q:
                    quint_rows.append(q)

            cls = _classify(full_corr, full_quint, block_corrs, signal, signal_id, pos)
            classify_rows.append(cls)
            evidence_rows.append(build_evidence_row(signal, pos, full_corr, block_corrs, cls))

    pd.DataFrame(corr_rows).to_csv(out_dir / "correlation_results.csv", index=False)
    pd.DataFrame(block_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(quint_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(classify_rows).to_csv(out_dir / "classification_summary.csv", index=False)
    (out_dir / "run_metadata.json").write_text(json.dumps({
        "timestamp": ts, "db_path": str(db_path), "db_row_count": len(state),
        "n_bootstrap": N_BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED, "ci_level": CI_LEVEL,
        "minutes_threshold": MINUTES_THRESHOLD, "gw_max": GW_MAX,
        "gw_blocks": {k: list(v) for k, v in GW_BLOCKS.items()},
        "quintile_gap_threshold": QUINTILE_GAP_THRESHOLD,
    }, indent=2))

    write_evidence(
        VALIDATE_DIR, LENS, TARGET_TOKEN, evidence_rows,
        evidence_run={"source": f"LENS-MARKET-{ts}", "produced": ts, "db_path": str(db_path)},
    )

    print(f"\nRun complete: {out_dir}")
    print(f"\n{'Signal':<20} {'Pos':<5} {'rho':>7}  {'95% CI':^17}  {'CI_excl0':>8}  {'Status'}")
    print("-" * 78)
    full_corrs = {(r["signal"], r["position"]): r for r in corr_rows if r["block"] == "full"}
    for cls in classify_rows:
        corr = full_corrs.get((cls["signal"], cls["position"]))
        if corr:
            print(f"{cls['signal']:<20} {cls['position']:<5} {corr['rho']:>7.4f}  "
                  f"[{corr['ci_lower']:>6.3f},{corr['ci_upper']:>6.3f}]  "
                  f"{'Yes' if corr['ci_excludes_zero'] else 'No':>8}  {cls['lens_status']}")
    return out_dir


if __name__ == "__main__":
    run()
