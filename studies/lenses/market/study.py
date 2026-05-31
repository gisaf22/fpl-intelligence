from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from dal.config import DB_PATH
from dal.pipeline import load as load_mart
RUNS_DIR = Path("studies/runs")

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
GW_MAX = 33
GW_BLOCKS: dict[str, tuple[int, int]] = {
    "early": (3, 12), "mid": (13, 26), "late": (27, 33),
}
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
QUINTILE_GAP_THRESHOLD = 1.0


def _bootstrap_spearman_ci(x, y, n_samples, seed):
    rho_obs = float(spearmanr(x, y).statistic)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_samples)
    for i in range(n_samples):
        idx = rng.integers(0, len(x), size=len(x))
        boot[i] = spearmanr(x[idx], y[idx]).statistic
    alpha = 1.0 - CI_LEVEL
    return rho_obs, float(np.percentile(boot, 100 * alpha / 2)), float(np.percentile(boot, 100 * (1 - alpha / 2)))


def _correlation_record(df, signal, signal_id, position, block):
    valid = df[[signal, "total_points_next_gw"]].dropna()
    if len(valid) < 10:
        return None
    x, y = valid[signal].to_numpy(), valid["total_points_next_gw"].to_numpy()
    rho, ci_lo, ci_hi = _bootstrap_spearman_ci(x, y, N_BOOTSTRAP, BOOTSTRAP_SEED)
    return {
        "signal_id": signal_id, "signal": signal, "position": position, "block": block,
        "rho": round(rho, 4), "ci_lower": round(ci_lo, 4), "ci_upper": round(ci_hi, 4),
        "n": len(valid), "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0),
    }


def _quintile_record(df, signal, signal_id, position, block):
    valid = df[[signal, "total_points_next_gw"]].dropna()
    if len(valid) < 25:
        return None
    try:
        ranked = valid.copy()
        ranked["quintile"] = pd.qcut(ranked[signal].rank(method="first"), 5, labels=["Q1","Q2","Q3","Q4","Q5"])
        means_s = ranked.groupby("quintile", observed=True)["total_points_next_gw"].mean()
        if not all(f"Q{i}" in means_s.index for i in range(1, 6)):
            return None
        means = [float(means_s[f"Q{i}"]) for i in range(1, 6)]
        gap = means[4] - means[0]
        is_monotonic = all(means[i] <= means[i + 1] for i in range(4))
        return {
            "signal_id": signal_id, "signal": signal, "position": position, "block": block,
            "q1_mean": round(means[0], 3), "q2_mean": round(means[1], 3),
            "q3_mean": round(means[2], 3), "q4_mean": round(means[3], 3),
            "q5_mean": round(means[4], 3), "q5_q1_gap": round(gap, 3),
            "is_monotonic": is_monotonic,
            "decision_relevant": bool(gap >= QUINTILE_GAP_THRESHOLD and is_monotonic),
        }
    except Exception:
        return None


def _classify(full_corr, full_quint, block_corrs, signal, signal_id, position):
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

            classify_rows.append(_classify(full_corr, full_quint, block_corrs, signal, signal_id, pos))

    pd.DataFrame(corr_rows).to_csv(out_dir / "correlation_results.csv", index=False)
    pd.DataFrame(block_rows).to_csv(out_dir / "block_results.csv", index=False)
    pd.DataFrame(quint_rows).to_csv(out_dir / "quintile_results.csv", index=False)
    pd.DataFrame(classify_rows).to_csv(out_dir / "classification_summary.csv", index=False)
    (out_dir / "run_metadata.json").write_text(json.dumps({
        "timestamp": ts, "db_path": str(db_path), "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": BOOTSTRAP_SEED, "ci_level": CI_LEVEL,
        "minutes_threshold": MINUTES_THRESHOLD, "gw_max": GW_MAX,
        "gw_blocks": {k: list(v) for k, v in GW_BLOCKS.items()},
        "quintile_gap_threshold": QUINTILE_GAP_THRESHOLD,
    }, indent=2))

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
