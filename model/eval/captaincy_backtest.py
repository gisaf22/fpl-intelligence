"""Phase 5 - decision evaluation: does the calibrated model help you pick a CAPTAIN?

The ultimate test of the stack: not "is the model accurate" but "does it lead to better decisions,
with honest error bars." Evaluates captaincy (one pick per GW) - the clean single-player decision
where the distribution should matter (ceiling, not just mean).

Strategies (each picks argmax per GW over the candidate universe, scored by realized points, blanks=0
so rotation is priced): template (ownership), base_season (expanding mean incl blanks), model_mean
(compose ``e_points``, the conditional mean), model_mean x P(play) (compose ``e_points_uncond``,
rotation-adjusted), ceiling (``p90`` and recalibrated ``p_haul``).

Universe (two views): **pool-free** = a model-agnostic lagged-minutes availability gate (primary, no
arbitrary pool); **ownership top-N** (secondary). Reads per strategy: mean pts/GW + **block-bootstrap CI**
(A5.1 - one season is thin and GWs autocorrelate), head-to-head win rate vs template, and regret vs the
oracle best captain.

Ex-ante scoring needs predictions for potential blanks, so this consumes the blank-inclusive compose
surface: ``compose_points(mart, keep_all=True)`` (E[points | played], ``base_season``, ``p_play``, and the
unconditional ``e_points_uncond`` = P(play) x E[points | played]) plus the conditional Monte-Carlo ceiling
from ``simulate_points(compose_parameters(mart, keep_all=True))``. The per-position P(play) term (X1) lives
in ``model.terms.p_play`` (lagged minutes/starts, no injury news - a limitation vs real managers).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.compose import compose_parameters, compose_points
from model.eval.metrics import BLOCK_GWS, block_bootstrap_ci, block_bootstrap_draws
from model.eval.walkforward import WARMUP_GW
from model.simulate import simulate_points

AVAILABILITY_MIN_ROLL = 45.0  # pool-free gate: averaged >= 45 min over the last 3 (lagged)
# Raw mart signals carried onto the compose panel for the strategies (ownership/availability/realized) AND
# the Door-1 discrimination diagnostic (fdr/home/form/price). Present-subset: a thin fixture may lack some.
_RAW_CARRY_COLS = [
    "ownership_count",
    "total_points",
    "minutes_roll3",
    "fdr_avg",
    "was_home",
    "xgi_roll5",
    "purchase_price",
]
_STRATEGIES = {
    "template": "ownership_count",
    "base_season": "base_season",
    "model_mean": "e_points",
    "model_mean_x_pplay": "e_points_uncond",
    "ceiling_p90": "p90",
    "ceiling_phaul": "p_haul",
}


def lagged_ownership(mart: pd.DataFrame) -> pd.DataFrame:
    """Pre-deadline ownership: the most recent snapshot **strictly before** the scored GW.

    Pool construction must not select on the outcome. The mart's ``ownership_count`` for GW N measures
    managers holding the player *for* GW N — deadline-locked, so it is arguably already ex-ante — but
    it is the value recorded against the GW being scored, so the conservative choice is the GW-(N-1)
    snapshot, which is pre-deadline under any reading. (Measured on this mart: the GW-N ownership
    *change* correlates +0.368 with GW-(N-1) points but only +0.116 with GW-N points, and that +0.116
    falls to +0.033 partialling out GW-(N-1) points — i.e. mediated by points autocorrelation, not a
    direct same-GW leak. Small, but the lag costs nothing.)

    BGW rows carry a contract-imposed ``ownership_count = 0`` (``dal.fct.fct_player_gameweek``), which
    is an absence-of-fixture marker, not an ownership reading — masked to NaN before the shift so the
    lag carries the last *genuine* snapshot across a blank rather than a spurious zero.
    """
    cols = ["player_id", "gw", "ownership_count"]
    df = mart[~mart["is_dgw"].astype(bool)][cols].drop_duplicates(["player_id", "gw"]).copy()
    df["ownership_count"] = pd.to_numeric(df["ownership_count"], errors="coerce")
    if "is_bgw" in mart.columns:  # absent on thin synthetic fixtures, which carry no blanks
        bgw = mart.drop_duplicates(["player_id", "gw"]).set_index(["player_id", "gw"])["is_bgw"]
        is_bgw = df.set_index(["player_id", "gw"]).index.map(bgw).to_numpy()
        df.loc[pd.Series(is_bgw, index=df.index).fillna(False).astype(bool), "ownership_count"] = np.nan
    df = df.sort_values(["player_id", "gw"])
    # shift THEN ffill, both within player, so a blank gameweek does not reset the pool to zero.
    df["ownership_lag"] = df.groupby("player_id")["ownership_count"].transform(lambda s: s.shift(1).ffill())
    return df[["player_id", "gw", "ownership_lag"]]


def build_captaincy_panel(mart: pd.DataFrame, n_sims: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Per player-GW captaincy inputs: strategy scores + realized points, on the full ex-ante universe.

    Consumes compose directly (spec X1): ``compose_points(keep_all=True)`` gives the conditional mean
    ``e_points``, ``base_season``, ``p_play``, and the unconditional ``e_points_uncond``; the ceiling
    (``p90``/``p_haul``) comes from the conditional Monte-Carlo simulator. The mart's raw decision inputs
    (ownership, realized points, the availability-gate roll) are merged back on by (player_id, gw)."""
    pts = compose_points(mart, keep_all=True)
    params = compose_parameters(mart, keep_all=True)
    sim = simulate_points(params, n_sims=n_sims, seed=seed)[["player_id", "gw", "p90", "p_haul"]]
    df = pts.merge(sim, on=["player_id", "gw"], how="left")
    present = [c for c in _RAW_CARRY_COLS if c in mart.columns]
    raw = mart[~mart["is_dgw"].astype(bool)][["player_id", "gw", *present]].copy()
    for c in present:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    df = df.merge(raw.drop_duplicates(["player_id", "gw"]), on=["player_id", "gw"], how="left")
    return df.merge(lagged_ownership(mart), on=["player_id", "gw"], how="left")


def _ci3(values: np.ndarray) -> tuple[float, float]:
    """Block-bootstrap CI (shared ``metrics.block_bootstrap_ci``) rounded to 3dp - preserves the prior
    displayed precision now that the raw helper returns unrounded floats."""
    lo, hi = block_bootstrap_ci(values)
    return (round(lo, 3), round(hi, 3))


def _pick_series(pool: pd.DataFrame, min_candidates: int = 3) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Per-GW realized points of each strategy's captain pick, and the oracle best, over a candidate pool.

    ``min_candidates`` is the smallest choice set a gameweek must offer to count. The default 3 is the
    pooled-universe convention; per-position cells relax it to 2 (see :func:`captaincy_by_position`) —
    a pick between two players is a real decision, whereas a one-candidate GW forces every strategy
    onto the same player and would inject structural zeros into the paired deltas.
    """
    per_gw: dict[str, list[float]] = {s: [] for s in _STRATEGIES}
    oracle = []
    for _, g in pool.groupby("gw"):
        if len(g) < min_candidates:
            continue
        oracle.append(float(g["total_points"].max()))
        for s, col in _STRATEGIES.items():
            gg = g.dropna(subset=[col])
            per_gw[s].append(float(gg.loc[gg[col].idxmax(), "total_points"]) if len(gg) else np.nan)
    return {s: np.array(v, dtype=float) for s, v in per_gw.items()}, np.array(oracle, dtype=float)


def captaincy_paired_deltas(
    mart: pd.DataFrame,
    pool: str = "free",
    n_top: int = 50,
    benchmark: str = "base_season",
    n_sims: int = 2000,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-strategy PAIRED delta vs ``benchmark`` with a block-bootstrap CI on the difference.

    The unpaired per-strategy CIs in :func:`captaincy_backtest` overlap heavily because they carry the
    common GW-to-GW variance (a big haul week lifts every strategy). Differencing within gameweek
    removes that shared component, so this is the test with any power to separate strategies — and the
    pre-registered win condition (*beat the benchmark with a CI excluding zero*) is stated on it.

    ``benchmark`` is ``base_season`` by design, not ``template``: template ranks by ownership, the same
    variable that defines a top-N pool, so its difficulty is confounded with pool size and it is not
    comparable across pools.
    """
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    ev = df[(df["gw"] > WARMUP_GW)].dropna(
        subset=["e_points", "p90", "p_haul", "ownership_count", "base_season", "total_points"]
    )
    gate = ev[ev["minutes_roll3"] >= AVAILABILITY_MIN_ROLL]
    if pool == "ownership":
        gate = gate.dropna(subset=["ownership_lag"])
        gate = gate.sort_values("ownership_lag", ascending=False).groupby("gw").head(n_top)
    series, _ = _pick_series(gate)
    base = series[benchmark]
    rows = []
    for s, v in series.items():
        if s == benchmark:
            continue
        d = v - base  # paired within gameweek
        finite = d[~np.isnan(d)]
        lo, hi = _ci3(finite)
        rows.append(
            {
                "strategy": s,
                "mean_delta": round(float(finite.mean()), 3) if len(finite) else float("nan"),
                "ci_lo": lo,
                "ci_hi": hi,
                "beats_benchmark": bool(len(finite) and lo > 0),
                "n_gw": len(finite),
            }
        )
    out = pd.DataFrame(rows).set_index("strategy")
    out.attrs["benchmark"] = benchmark
    return out


def captaincy_by_position(
    mart: pd.DataFrame,
    n_tops: tuple[int, ...] = (10, 20, 50),
    positions: tuple[str, ...] = ("FWD", "MID", "DEF"),
    benchmark: str = "base_season",
    min_candidates: int = 2,
    n_sims: int = 2000,
    seed: int = 0,
) -> pd.DataFrame:
    """Strategy comparison stratified by (ownership pool x position) — the never-tested cut.

    Every captaincy comparison to date is a pooled average across positions, which can mask offsetting
    per-position effects (a ceiling bet plausibly pays at FWD, where hauls *are* the decision, while
    losing at DEF). Each cell is the sub-decision *"best captain at position Q, shopping in the top-N
    most-owned"*: candidates are the pool members at that position, the oracle is the best of them.

    Returns one row per (pool, position, strategy) carrying mean pts/GW, hit@1 against that cell's own
    ``mean(1/n_candidates)`` chance baseline, and the paired delta vs ``benchmark`` with a
    block-bootstrap CI **and** a bootstrap two-sided p-value off the same draws — the p-value is what a
    multiplicity correction is applied to, since this cut runs many cells at once.

    ``n_gw`` and ``median_n_candidates`` are returned per cell and are load-bearing, not decoration: a
    top-10 pool splits into ~2-3 candidates per position, so thin cells are expected and their
    intervals are not interpretable. Read the sizes before the estimates.
    """
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    ev = df[(df["gw"] > WARMUP_GW)].dropna(
        subset=["e_points", "p90", "p_haul", "ownership_count", "base_season", "total_points"]
    )
    gate = ev[ev["minutes_roll3"] >= AVAILABILITY_MIN_ROLL].dropna(subset=["ownership_lag"])
    rows = []
    for n_top in n_tops:
        pool = gate.sort_values("ownership_lag", ascending=False).groupby("gw").head(n_top)
        for pos in positions:
            cell = pool[pool["position"] == pos]
            sizes = cell.groupby("gw").size()
            keep = sizes[sizes >= min_candidates].index
            cell = cell[cell["gw"].isin(keep)]
            if cell.empty:
                continue
            series, oracle = _pick_series(cell, min_candidates=min_candidates)
            gws = sorted(cell["gw"].unique())
            chance = float(np.mean(1.0 / cell.groupby("gw").size()))
            base = series[benchmark]
            for s, col in _STRATEGIES.items():
                v = series[s]
                finite = v[~np.isnan(v)]
                # hit@1: does this strategy's top-ranked candidate happen to BE the cell's oracle?
                hits = 0
                for gw in gws:
                    g = cell[cell["gw"] == gw].dropna(subset=[col])
                    if g.empty:
                        continue
                    hits += int(g.loc[g[col].idxmax(), "total_points"] == g["total_points"].max())
                d = v - base
                dfin = d[~np.isnan(d)]
                lo, hi = _ci3(dfin) if len(dfin) >= BLOCK_GWS else (float("nan"), float("nan"))
                draws = block_bootstrap_draws(dfin) if len(dfin) >= BLOCK_GWS else np.empty(0)
                # two-sided bootstrap p: how much of the sampling distribution sits across zero.
                p = float(2 * min((draws <= 0).mean(), (draws >= 0).mean())) if len(draws) else float("nan")
                rows.append(
                    {
                        "pool": f"top-{n_top}",
                        "position": pos,
                        "strategy": s,
                        "n_gw": len(oracle),
                        "median_n_candidates": float(sizes[sizes >= min_candidates].median()),
                        "mean_pts_gw": round(float(finite.mean()), 3) if len(finite) else float("nan"),
                        "oracle_pts_gw": round(float(np.nanmean(oracle)), 3) if len(oracle) else float("nan"),
                        "hit_at_1": round(hits / len(gws), 3) if gws else float("nan"),
                        "chance_at_1": round(chance, 3),
                        "delta_vs_benchmark": round(float(dfin.mean()), 3) if len(dfin) else float("nan"),
                        "ci_lo": lo,
                        "ci_hi": hi,
                        "boot_p": round(p, 4) if p == p else float("nan"),
                        "excludes_zero": bool(len(dfin) >= BLOCK_GWS and (lo > 0 or hi < 0)),
                    }
                )
    return pd.DataFrame(rows)


def captaincy_backtest(
    mart: pd.DataFrame, pool: str = "free", n_top: int = 50, n_sims: int = 2000, seed: int = 0
) -> pd.DataFrame:
    """Captaincy strategy comparison over the chosen universe, with block-bootstrap CIs.

    ``pool='free'`` = lagged-minutes availability gate (model-agnostic, primary); ``pool='ownership'``
    = top-``n_top`` owned within that gate (secondary), ranked by **pre-deadline** ownership
    (:func:`lagged_ownership`) so pool membership cannot be selected on the scored GW's own reading.
    Returns per-strategy mean pts/GW, block CI, head-to-head win rate vs template, and regret vs the
    oracle; ``.attrs`` carries the oracle mean + its block CI and the realized within-GW spread.
    """
    df = build_captaincy_panel(mart, n_sims=n_sims, seed=seed)
    ev = df[(df["gw"] > WARMUP_GW)].dropna(
        subset=["e_points", "p90", "p_haul", "ownership_count", "base_season", "total_points"]
    )
    gate = ev[ev["minutes_roll3"] >= AVAILABILITY_MIN_ROLL]
    if pool == "ownership":
        gate = gate.dropna(subset=["ownership_lag"])
        gate = gate.sort_values("ownership_lag", ascending=False).groupby("gw").head(n_top)

    series, oracle = _pick_series(gate)
    templ = series["template"]
    oracle_mean = float(np.nanmean(oracle))
    rows = []
    for s, v in series.items():
        finite = v[~np.isnan(v)]
        lo, hi = _ci3(finite)
        mean_v = round(float(finite.mean()), 3) if len(finite) else float("nan")
        rows.append(
            {
                "strategy": s,
                "mean_pts_gw": mean_v,
                "ci_lo": lo,
                "ci_hi": hi,
                "winrate_vs_template": round(float(np.nanmean(v > templ)), 3),
                "regret": round(oracle_mean - finite.mean(), 3) if len(finite) else float("nan"),
            }
        )
    out = pd.DataFrame(rows).set_index("strategy")
    out.attrs["oracle_mean"] = round(float(np.nanmean(oracle)), 3)
    out.attrs["oracle_ci"] = _ci3(oracle[~np.isnan(oracle)])
    out.attrs["n_gw"] = len(oracle)
    # Headroom is only meaningful beside the realized SPREAD inside the pool: if the candidates all
    # score alike, ranking them well cannot pay, however accurate the ranker.
    spread = gate.groupby("gw")["total_points"].agg(
        pool_n="size",
        rng=lambda s: s.max() - s.min(),
        iqr=lambda s: s.quantile(0.75) - s.quantile(0.25),
    )
    out.attrs["pool_n_median"] = float(spread["pool_n"].median())
    out.attrs["spread_range_mean"] = round(float(spread["rng"].mean()), 3)
    out.attrs["spread_iqr_mean"] = round(float(spread["iqr"].mean()), 3)
    out.attrs["headroom"] = round(oracle_mean - max(r["mean_pts_gw"] for r in rows), 3)
    out.attrs["position_mix"] = gate["position"].value_counts(normalize=True).round(3).to_dict()
    oracle_rows = gate.loc[gate.groupby("gw")["total_points"].idxmax()]
    out.attrs["oracle_position_mix"] = oracle_rows["position"].value_counts().to_dict()
    return out
