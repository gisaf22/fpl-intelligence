"""
SYNTH-01 Execution — Phase 7, Operational Convergence Plan.

Computes partial Spearman rho for each candidate controlling for all other
same-position × same-lens candidates. Resolves redundancy pairs and
within-window families via marginal gain test. Derives composition weights
with bootstrap CIs. Runs FDR moderation sensitivity check.

Output: signals/evaluation/synth01_decisions.yaml
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr
from numpy.linalg import lstsq

from dal import (
    build_player_gameweek_spine,
    build_player_gameweek_state,
    get_player_fixture_base,
    load_staged_entities,
)

from dal.config import DB_PATH
OUT_PATH = Path("signals/evaluation/synth01_decisions.yaml")
RUNS_DIR = Path("studies/runs")

N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95
MINUTES_THRESHOLD = 60
GW_MAX = 33
MARGINAL_GAIN_THRESHOLD = 0.02
MAX_WEIGHT = 0.60
EQUAL_WEIGHT_IMPROVEMENT_THRESHOLD = 0.02
FDR_MODERATION_THRESHOLD = 0.15

# ---------------------------------------------------------------------------
# Evaluation groups — position × lens, ordered by gw_min (most restrictive)
# ---------------------------------------------------------------------------

GROUPS: list[dict] = [
    dict(position="DEF", lens="FORM",
         signals=["xgi_roll3", "xgi_roll5"],
         target="total_points_next_gw", gw_min=6),
    dict(position="DEF", lens="AVAIL",
         signals=["minutes_roll8"],
         target="played_next_gw", gw_min=9),
    dict(position="DEF", lens="MARKET",
         signals=["transfers_in", "ownership_count", "purchase_price"],
         target="total_points_next_gw", gw_min=1),
    dict(position="MID", lens="FORM",
         signals=["xgi_roll3", "xgi_roll5"],
         target="total_points_next_gw", gw_min=6),
    dict(position="MID", lens="AVAIL",
         signals=["minutes_roll3", "minutes_roll5", "minutes_roll8"],
         target="played_next_gw", gw_min=9),
    dict(position="MID", lens="MARKET",
         signals=["transfers_in", "ownership_count"],
         target="total_points_next_gw", gw_min=1),
]

# MID naive baseline (points_roll5 MID) — excluded from composition, used for validation only
MID_NAIVE_BASELINE_RHO = 0.158

HIGH_REDUNDANCY_PAIRS = {("DEF", "ownership_count", "transfers_in"),
                         ("MID", "ownership_count", "transfers_in")}


# ---------------------------------------------------------------------------
# Partial Spearman rho
# ---------------------------------------------------------------------------

def _partial_spearman(X: np.ndarray, y: np.ndarray, signal_idx: int) -> float:
    """Partial Spearman rho of X[:, signal_idx] controlling for all other columns.

    Uses the rank-OLS residual method: rank all variables, residualize the signal
    and target on all other signals via OLS, then compute Pearson correlation of
    the two residual series.

    For a singleton group (p=1), returns bivariate Spearman rho.
    """
    from scipy.stats import rankdata

    n, p = X.shape
    X_r = np.apply_along_axis(rankdata, 0, X).astype(float)
    y_r = rankdata(y).astype(float)

    if p == 1:
        return float(spearmanr(X_r[:, 0], y_r).statistic)

    others = np.delete(X_r, signal_idx, axis=1)
    A = np.column_stack([np.ones(n), others])

    coef_x = lstsq(A, X_r[:, signal_idx], rcond=None)[0]
    coef_y = lstsq(A, y_r, rcond=None)[0]
    resid_x = X_r[:, signal_idx] - A @ coef_x
    resid_y = y_r - A @ coef_y

    if not (np.isfinite(resid_x).all() and np.isfinite(resid_y).all()):
        return 0.0
    denom = np.std(resid_x) * np.std(resid_y)
    if denom < 1e-12:
        return 0.0
    return float(np.corrcoef(resid_x, resid_y)[0, 1])


def _bootstrap_partial_rho(
    X: np.ndarray, y: np.ndarray, signal_idx: int
) -> tuple[float, float, float]:
    """Return (partial_rho, ci_lower, ci_upper) via bootstrap resampling."""
    rho_obs = _partial_spearman(X, y, signal_idx)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.empty(N_BOOTSTRAP)
    for i in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(y), size=len(y))
        boot[i] = _partial_spearman(X[idx], y[idx], signal_idx)
    alpha = 1.0 - CI_LEVEL
    return (rho_obs,
            float(np.percentile(boot, 100 * alpha / 2)),
            float(np.percentile(boot, 100 * (1.0 - alpha / 2))))


# ---------------------------------------------------------------------------
# Weight derivation with bootstrap CIs
# ---------------------------------------------------------------------------

def _normalize_weights(partial_rhos: dict[str, float]) -> dict[str, float]:
    """Normalize |partial_rho| → weights summing to 1.0, cap each at MAX_WEIGHT."""
    raw = {s: abs(r) for s, r in partial_rhos.items()}
    total = sum(raw.values())
    if total == 0.0:
        n = len(raw)
        return {s: round(1.0 / n, 4) for s in raw}

    weights = {s: v / total for s, v in raw.items()}

    for _ in range(20):
        if max(weights.values()) <= MAX_WEIGHT + 1e-9:
            break
        excess = sum(max(0.0, w - MAX_WEIGHT) for w in weights.values())
        capped = {s: min(w, MAX_WEIGHT) for s, w in weights.items()}
        uncapped = {s for s, w in weights.items() if w < MAX_WEIGHT - 1e-9}
        if not uncapped:
            break
        uncapped_sum = sum(capped[s] for s in uncapped)
        for s in uncapped:
            capped[s] += excess * (capped[s] / uncapped_sum)
        weights = capped

    return weights


def _bootstrap_weights(
    X: np.ndarray, y: np.ndarray, retained_indices: list[int], retained_signals: list[str]
) -> dict[str, tuple[float, float]]:
    """Bootstrap CIs for composition weights. Returns {signal: (ci_lower, ci_upper)}."""
    rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
    boot_weights: dict[str, list[float]] = {s: [] for s in retained_signals}

    X_ret = X[:, retained_indices]

    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(y), size=len(y))
        p_rhos = {}
        for j, sig in enumerate(retained_signals):
            p_rhos[sig] = _partial_spearman(X_ret[idx], y[idx], j)
        w = _normalize_weights(p_rhos)
        for s, wv in w.items():
            boot_weights[s].append(wv)

    alpha = 1.0 - CI_LEVEL
    return {
        s: (float(np.percentile(vs, 100 * alpha / 2)),
            float(np.percentile(vs, 100 * (1.0 - alpha / 2))))
        for s, vs in boot_weights.items()
    }


# ---------------------------------------------------------------------------
# Composite rho (for equal-weight sanity check and baseline comparison)
# ---------------------------------------------------------------------------

def _composite_rho(
    data: pd.DataFrame, signals: list[str], weights: dict[str, float], target: str
) -> float:
    """Spearman rho of weighted composite against target."""
    valid = data[signals + [target]].dropna()
    if len(valid) < 10:
        return float("nan")
    composite = sum(weights[s] * valid[s] for s in signals)
    return float(spearmanr(composite, valid[target]).statistic)


def _permutation_baseline(
    data: pd.DataFrame, signal: str, target: str, n_perm: int = 500, seed: int = 99
) -> float:
    """Mean absolute Spearman rho under H0 (permuted target). Used as DEF baseline."""
    valid = data[[signal, target]].dropna()
    if len(valid) < 10:
        return 0.0
    rng = np.random.default_rng(seed)
    rhos = [abs(float(spearmanr(valid[signal], rng.permutation(valid[target].to_numpy())).statistic))
            for _ in range(n_perm)]
    return float(np.mean(rhos))


# ---------------------------------------------------------------------------
# FDR moderation sensitivity check
# ---------------------------------------------------------------------------

def _fdr_moderation_check(
    pop: pd.DataFrame, retained: list[tuple[str, str, str]]
) -> dict:
    """
    For each (position, target) group of retained signals, split population by
    FDR quartile and check whether signal rank ordering (by rho) changes across
    quartiles in > FDR_MODERATION_THRESHOLD fraction of quartile comparisons.

    Returns summary dict with material verdict.
    """
    pop = pop.copy()
    valid_fdr = pop["fdr_avg"].dropna()
    if valid_fdr.empty:
        return {"material": False, "verdict": "SKIPPED — fdr_avg not available", "detail": []}

    pop["fdr_quartile"] = pd.qcut(
        pop["fdr_avg"].rank(method="first", na_option="keep"), 4,
        labels=["Q1", "Q2", "Q3", "Q4"]
    )

    groups: dict[tuple[str, str], list[str]] = {}
    for sig, pos, tgt in retained:
        groups.setdefault((pos, tgt), []).append(sig)

    detail = []
    n_material = 0

    for (pos, tgt), signals in groups.items():
        if len(signals) < 2:
            continue
        pos_data = pop[pop["position_label"] == pos]

        quartile_orders: list[list[str]] = []
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            q_data = pos_data[pos_data["fdr_quartile"] == q]
            rhos: dict[str, float] = {}
            for sig in signals:
                valid = q_data[[sig, tgt]].dropna()
                if len(valid) < 20:
                    continue
                rhos[sig] = float(spearmanr(valid[sig], valid[tgt]).statistic)
            if len(rhos) == len(signals):
                quartile_orders.append(sorted(rhos.keys(), key=lambda s: -rhos[s]))

        if len(quartile_orders) < 2:
            continue

        baseline = quartile_orders[0]
        n_changed = sum(1 for o in quartile_orders[1:] if o != baseline)
        fraction = n_changed / (len(quartile_orders) - 1)
        is_material = fraction > FDR_MODERATION_THRESHOLD

        detail.append({
            "position": pos,
            "target": tgt,
            "signals": signals,
            "fraction_rank_changed": round(fraction, 3),
            "material": is_material,
        })
        if is_material:
            n_material += 1

    overall = n_material > 0
    return {
        "material": overall,
        "n_material_groups": n_material,
        "n_groups_checked": len(detail),
        "verdict": ("MATERIAL — flag for Phase 8 moderator implementation"
                    if overall else "NOT MATERIAL — no FDR moderation required"),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(db_path: Path = DB_PATH) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"SYNTH-01-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading DAL data from {db_path} ...")
    staged = load_staged_entities(db_path)
    spine = build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)
    state = build_player_gameweek_state(spine)

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

    decision_counter = 0
    all_decisions: list[dict] = []
    retained_for_moderation: list[tuple[str, str, str]] = []
    group_summaries: list[dict] = []

    for group in GROUPS:
        position = group["position"]
        lens = group["lens"]
        signals: list[str] = group["signals"]
        target: str = group["target"]
        gw_min: int = group["gw_min"]

        pos_pop = pop[(pop["position_label"] == position) & (pop["gw"] >= gw_min)]
        valid = pos_pop[signals + [target]].dropna()
        n = len(valid)

        print(f"\n{position} × {lens}  (n={n}, gw>={gw_min})")

        X = valid[signals].to_numpy()
        y = valid[target].to_numpy()

        # --- Partial rho with bootstrap CIs ---
        partial_results: dict[str, tuple[float, float, float]] = {}
        for i, sig in enumerate(signals):
            rho, ci_lo, ci_hi = _bootstrap_partial_rho(X, y, i)
            partial_results[sig] = (rho, ci_lo, ci_hi)
            print(f"  {sig:20s} partial_rho={rho:+.4f}  CI=[{ci_lo:.4f}, {ci_hi:.4f}]")

        # --- Marginal gain classification ---
        retained_sigs = [s for s, (r, _, _) in partial_results.items()
                         if abs(r) >= MARGINAL_GAIN_THRESHOLD]
        excluded_sigs = [s for s in signals if s not in retained_sigs]

        # --- Weight derivation ---
        retained_partial_rhos = {s: partial_results[s][0] for s in retained_sigs}
        weights = _normalize_weights(retained_partial_rhos) if retained_sigs else {}

        # Bootstrap weight CIs (only if > 1 retained signal)
        weight_cis: dict[str, tuple[float, float]] = {}
        if len(retained_sigs) > 1:
            retained_indices = [signals.index(s) for s in retained_sigs]
            weight_cis = _bootstrap_weights(X, y, retained_indices, retained_sigs)

        # --- Equal-weight sanity check ---
        weight_constrained = False
        equal_weight_preferred = False
        if len(retained_sigs) > 1:
            eq_w = {s: 1.0 / len(retained_sigs) for s in retained_sigs}
            rho_ev = _composite_rho(valid, retained_sigs, weights, target)
            rho_eq = _composite_rho(valid, retained_sigs, eq_w, target)
            improvement = rho_ev - rho_eq
            if improvement < EQUAL_WEIGHT_IMPROVEMENT_THRESHOLD:
                equal_weight_preferred = True
                weights = eq_w
                print(f"  Equal-weight preferred: evidence composite rho={rho_ev:.4f} vs equal-weight rho={rho_eq:.4f} (improvement={improvement:.4f} < {EQUAL_WEIGHT_IMPROVEMENT_THRESHOLD})")
            else:
                print(f"  Evidence weights preferred: composite rho={rho_ev:.4f} vs equal-weight rho={rho_eq:.4f} (improvement={improvement:.4f})")

        # --- Baseline comparison ---
        baseline_note = ""
        if retained_sigs and target == "total_points_next_gw":
            if position == "MID":
                comp_rho = _composite_rho(valid, retained_sigs, weights, target)
                clears = comp_rho > MID_NAIVE_BASELINE_RHO
                baseline_note = (
                    f"MID composite rho={comp_rho:.4f} vs naive baseline rho={MID_NAIVE_BASELINE_RHO} — "
                    + ("CLEARS baseline" if clears else "DOES NOT CLEAR baseline")
                )
                print(f"  {baseline_note}")
            elif position == "DEF" and retained_sigs:
                perm_rho = _permutation_baseline(valid, retained_sigs[0], target)
                comp_rho = _composite_rho(valid, retained_sigs, weights, target)
                baseline_note = (
                    f"DEF composite rho={comp_rho:.4f} vs permutation baseline rho≈{perm_rho:.4f}"
                )
                print(f"  {baseline_note}")

        # --- Rank retained for primary/secondary ---
        retained_ranked = sorted(retained_sigs, key=lambda s: -abs(partial_results[s][0]))

        # --- Issue G-SYNTH1-* decisions ---
        for sig in signals:
            decision_counter += 1
            d_id = f"G-SYNTH1-{decision_counter:02d}"
            rho, ci_lo, ci_hi = partial_results[sig]

            if sig in excluded_sigs:
                absorbing = [s for s in retained_sigs]
                is_hr = (position, sig, absorbing[0] if absorbing else "") in HIGH_REDUNDANCY_PAIRS or \
                        any((position, sig, a) in HIGH_REDUNDANCY_PAIRS for a in absorbing)
                decision_str = "EXCLUDED-REDUNDANT"
                weight_val = 0.0
                contrib = "redundant"
                notes = (
                    f"|partial_rho|={abs(rho):.4f} < {MARGINAL_GAIN_THRESHOLD} threshold. "
                    f"Absorbed by: {absorbing or 'all signals excluded'}."
                )
                if is_hr:
                    notes += " Confirms HIGH REDUNDANCY SUBSTITUTE resolution from synth01_candidates.yaml."
            else:
                rank = retained_ranked.index(sig)
                contrib = "primary" if rank == 0 else "secondary"
                decision_str = "APPROVED-PRIMARY" if contrib == "primary" else "APPROVED-SECONDARY"
                weight_val = weights.get(sig, 0.0)
                w_ci = weight_cis.get(sig, (None, None))
                notes = (
                    f"|partial_rho|={abs(rho):.4f} >= {MARGINAL_GAIN_THRESHOLD} threshold. "
                    f"Weight={weight_val:.4f}"
                )
                if equal_weight_preferred:
                    notes += " (equal-weight: evidence composite did not improve by >=0.02 rho units)."
                if w_ci[0] is not None:
                    notes += f" Weight CI=[{w_ci[0]:.4f}, {w_ci[1]:.4f}]."
                retained_for_moderation.append((sig, position, target))

            controlling_for = [s for s in signals if s != sig]
            evidence = (
                f"partial_rho={rho:.4f}; CI=[{ci_lo:.4f}, {ci_hi:.4f}]; "
                f"controlling for {controlling_for if controlling_for else 'none (singleton)'}; "
                f"n={n}"
            )

            entry: dict = {
                "decision_id": d_id,
                "signal": sig,
                "position": position,
                "lens": lens,
                "decision": decision_str,
                "partial_rho": round(rho, 4),
                "partial_ci_lower": round(ci_lo, 4),
                "partial_ci_upper": round(ci_hi, 4),
                "composition_weight": round(weight_val, 4),
                "contribution_class": contrib,
                "marginal_gain": round(abs(rho), 4),
                "evidence": evidence,
                "notes": notes,
            }

            w_ci = weight_cis.get(sig)
            if w_ci and w_ci[0] is not None:
                entry["weight_ci_lower"] = round(w_ci[0], 4)
                entry["weight_ci_upper"] = round(w_ci[1], 4)

            all_decisions.append(entry)

        group_summaries.append({
            "group": f"{position} × {lens}",
            "n": n,
            "retained": retained_sigs,
            "excluded": excluded_sigs,
            "weights": {s: round(weights.get(s, 0.0), 4) for s in retained_sigs},
            "equal_weight_preferred": equal_weight_preferred,
            "baseline_note": baseline_note,
        })

    # --- FWD single-signal decision ---
    decision_counter += 1
    all_decisions.append({
        "decision_id": f"G-SYNTH1-{decision_counter:02d}",
        "signal": "purchase_price",
        "position": "FWD",
        "lens": "MARKET",
        "decision": "FWD-SINGLE-SIGNAL",
        "partial_rho": 0.155,
        "partial_ci_lower": 0.077,
        "partial_ci_upper": 0.237,
        "composition_weight": 1.0,
        "contribution_class": "primary",
        "marginal_gain": 0.155,
        "evidence": "Sole FWD candidate. No composite synthesis — single-signal qualified score. bivariate rho=0.155 from LENS-MARKET evaluation_metadata.yaml.",
        "notes": "G3-WEAK: 2/3 temporal blocks. Intelligence consumers must acknowledge caveat. Not evaluated by partial rho (no other FWD candidates to control for).",
    })

    # --- FDR moderation check ---
    print("\nFDR moderation sensitivity check ...")
    moderation = _fdr_moderation_check(pop, retained_for_moderation)
    print(f"  {moderation['verdict']}")

    # --- Assemble output ---
    approved = [d for d in all_decisions if d["decision"].startswith("APPROVED")]
    excluded = [d for d in all_decisions if "EXCLUDED" in d["decision"]]

    output = {
        "version": "synth01",
        "produced": datetime.now().strftime("%Y-%m-%d"),
        "authority": "Operational Convergence Plan Phase 7",
        "candidate_registry": "signals/registry/synth01_candidates.yaml",
        "design_doc": "docs/governance/synth01-design.md",
        "total_decisions": len(all_decisions),
        "approved_count": len(approved),
        "excluded_count": len(excluded),
        "fdr_moderation_check": moderation,
        "group_summary": group_summaries,
        "decisions": all_decisions,
    }

    with open(OUT_PATH, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\nDecisions written to {OUT_PATH}")
    print(f"Run artifacts: {run_dir}")
    print(f"\nSummary: {len(approved)} approved, {len(excluded)} excluded")
    for g in group_summaries:
        print(f"  {g['group']}: retained={g['retained']}, excluded={g['excluded']}, weights={g['weights']}")

    return OUT_PATH


if __name__ == "__main__":
    run()
