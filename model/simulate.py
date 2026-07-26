"""Monte-Carlo the points **distribution** from the term registry (spec §1 item 5).

Where :func:`model.compose.compose_points` gives the mean, this samples each player-GW's components
through the real FPL scoring rules to produce the full distribution — P(haul), captaincy ceiling (p90),
downside (p10). It draws from the shared raw-parameter panel :func:`model.compose.compose_parameters`
(no re-fit): ``e_goals``/``e_assists``/``e_saves`` are Poisson means, ``p_cs`` gives the team
goals-against mean via ``lambda_ga = -log(p_cs)``, ``p_dc``/``p60`` are Bernoulli probabilities, and
``bonus_intercept``/``bonus_slope`` map drawn returns to bonus.

Sampling assumptions (kept LOCAL to this file — the Term contract emits point values, not distributions;
declaring a per-term sampling law is a deferred §2 change). Ported faithfully from the strangled
``model.forecast.simulator`` (since deleted); most are still un-revalidated here, with the one exception
marked **MEASURED** below:
  * **team goals-against is drawn ONCE per team-fixture and shared** across the team's players, so
    ``clean_sheet = 1{GA=0} & played>=60`` and ``conceded = -floor(GA/2)`` co-move (D-D). Exact for
    full-90 players, approximate for subs.
  * **DC is drawn independently** (D-A: DC _|_ GA given minutes).
  * **goals _|_ assists** within a player — **MEASURED, holds** (2026-07-21, real mart, n=10,110,
    conditional population). The claim is about the RESIDUAL: marginally the two do correlate (+0.038),
    but that is only good attackers having high rates for both, which the per-player ``e_goals`` /
    ``e_assists`` already carry. Net of those, ``corr(g - e_goals, a - e_assists)`` is DEF **-0.008**,
    MID **+0.019**, FWD **+0.038** — every 95% CI contains 0. Independence understates the variance of
    attacking points by <=4% (obs/independence-implied: GK 1.00, DEF 1.00, MID 1.03, FWD 1.04), i.e. ~2%
    on interval width. Mechanistically two effects cancel: shared team attacking form pulls positive,
    while a goal has one scorer and at most one (different) assister, which pulls negative.
    Do NOT "fix" this by correlating the draws — see the Phase-4 results correction for the simulated
    version of the same negative result.
  * **bonus co-varies via the drawn returns** (per draw); its competitive residual is not sampled — this
    is why ``sim_mean`` differs from compose's expected-returns bonus (bonus clip is a Jensen nonlinearity).

Reproduction (this is a STOCHASTIC step — no bit-identical golden exists): the gate is a **seed-pinned
regression vector** (fixed seed -> summaries reproduce to 4dp) plus a **tolerance consistency check** that
``sim_mean`` tracks compose ``e_points`` on non-GK rows (MC error + bonus-clip + saves-floor gap). GK rows
diverge from the legacy simulator BY DESIGN (compose's robust GK ``p60`` vs the flat-0.98 shortcut).

Scope limits: conditional on appearance (no ``P(play)`` blank / 0-minute tail); DGW player-fixtures are
absent (compose drops ``is_dgw`` — cleaner than the legacy same-GW team-key collapse); single-player
marginals (no team goals-for co-movement); rare events excluded.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd

from domain.fpl_scoring import BPS_BONUS_FIRST, GK_SAVES_PER_POINT
from model.compose import _CS_MULT, _GOAL_MULT, compose_parameters, compose_points
from model.eval.walkforward import WARMUP_GW

HAUL_THRESHOLD = 10
# ``p_dc`` is intentionally NOT required: GK have no DC term (NaN), handled as 0 downstream via the
# position gate - requiring it would drop every GK row from the simulation.
_REQUIRED = ["e_goals", "e_assists", "p_cs", "p60", "bonus_intercept", "bonus_slope"]
_SUMMARY_COLUMNS = ["player_id", "gw", "position", "sim_mean", "sim_sd", "p10", "p50", "p90", "p_haul"]


def _draw_team_ga(params: pd.DataFrame, n_sims: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Draw team goals-against ONCE per team-fixture (shared across the team's players).

    Returns ``(tf_index, ga_by_tf)`` where ``ga_by_tf`` is ``(n_team_fixtures, n_sims)`` and ``tf_index``
    maps each row to its team-fixture. ``lambda_ga = -log(p_cs)`` (p_cs = P(GA=0)).
    """
    tf_key = params["team_id"].astype(str) + "_" + params["gw"].astype(str)
    tf_index, tf_uniques = pd.factorize(tf_key)
    # p_cs is constant within a team-fixture (broadcast); take the first per tf.
    first = params.groupby(tf_index)["p_cs"].first().reindex(range(len(tf_uniques)))
    lam = np.clip(-np.log(np.clip(first.to_numpy(dtype=float), 1e-6, 1.0)), 0.0, None)
    ga_by_tf = rng.poisson(lam[:, None], size=(len(tf_uniques), n_sims))
    return tf_index, ga_by_tf


# The per-component point decomposition a draw produces — same names/order as compose's DECOMP_COLUMNS,
# so the two are directly comparable term-by-term (the scoring-conformance check).
DECOMP_TERMS = ("appearance", "goals", "assists", "clean_sheets", "goals_conceded",
                "saves", "defensive_contribution", "bonus")


def _simulate_components(block: pd.DataFrame, ga: np.ndarray, n_sims: int,
                         rng: np.random.Generator) -> dict[str, np.ndarray]:
    """The per-component POINT matrices for a block — each ``(n_rows, n_sims)``, keyed by DECOMP_TERMS.

    This is the single home of the draw+score logic; :func:`_simulate_rows` sums these, and the
    conformance check means them per term. The rng draw order (play60, goals, assists, saves, dc) is the
    contract that keeps every downstream golden bit-identical — do not reorder it.
    """
    n = len(block)
    pos = block["position"].to_numpy()
    gmult = block["position"].map(_GOAL_MULT).to_numpy(dtype=float)[:, None]
    cmult = block["position"].map(_CS_MULT).to_numpy(dtype=float)[:, None]
    is_gk = (pos == "GK")[:, None]
    has_conceded = np.isin(pos, ["GK", "DEF"])[:, None]
    has_dc = np.isin(pos, ["DEF", "MID", "FWD"])[:, None]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(block[name].to_numpy(dtype=float))[:, None]

    play60 = rng.random((n, n_sims)) < col("p60")
    goals = rng.poisson(col("e_goals"), size=(n, n_sims))     # GK e_goals is 0.0 => draws 0
    assists = rng.poisson(col("e_assists"), size=(n, n_sims))
    saves = np.where(is_gk, rng.poisson(np.clip(col("e_saves"), 0, None), size=(n, n_sims)), 0)
    dc = (rng.random((n, n_sims)) < col("p_dc")) & has_dc

    goal_pts = gmult * goals                                  # no position gate: the model emits 0 for GK
    assist_pts = 3 * assists
    cs_pts = cmult * ((ga == 0) & play60)                     # clean sheet needs GA=0 AND >=60'
    conceded = np.where(has_conceded, -(ga // 2), 0)
    saves_pts = np.where(is_gk, saves // GK_SAVES_PER_POINT, 0)
    dc_pts = np.where(dc, 2, 0)
    appearance = 1 + play60                                   # 1 (played) + 1 (>=60')

    returns_pts = goal_pts + assist_pts + cs_pts + saves_pts
    bonus = np.clip(col("bonus_intercept") + col("bonus_slope") * returns_pts, 0.0, BPS_BONUS_FIRST)

    return {"appearance": appearance, "goals": goal_pts, "assists": assist_pts,
            "clean_sheets": cs_pts, "goals_conceded": conceded, "saves": saves_pts,
            "defensive_contribution": dc_pts, "bonus": bonus}


def _simulate_rows(block: pd.DataFrame, ga: np.ndarray, n_sims: int,
                   rng: np.random.Generator) -> np.ndarray:
    """Sampled points ``(n_rows, n_sims)`` for a block — the sum of :func:`_simulate_components`.

    The addition order is fixed to the pre-decomposition expression (appearance, goals, assists, CS,
    conceded, DC, saves, bonus) so the float result is **bit-identical** to the seed-pinned golden.
    """
    c = _simulate_components(block, ga, n_sims, rng)
    return (c["appearance"] + c["goals"] + c["assists"] + c["clean_sheets"]
            + c["goals_conceded"] + c["defensive_contribution"] + c["saves"] + c["bonus"])


def _iter_draw_batches(params: pd.DataFrame, n_sims: int, seed: int, batch_rows: int
                       ) -> Iterator[tuple[pd.DataFrame, np.ndarray, np.random.Generator]]:
    """Shared setup for the draw primitives: filter to the scored population, seed one rng, draw team-GA
    once, then yield ``(block, ga, rng)`` per memory-bounded batch. The single home of the batch loop —
    both :func:`iter_sample_blocks` and :func:`iter_component_blocks` consume it, so the rng stream and
    batching are identical across the summed and decomposed views (no duplicated loop, spec Phase-4 §1)."""
    df = params[params["gw"] > WARMUP_GW].dropna(subset=_REQUIRED).copy().reset_index(drop=True)
    if df.empty:
        return
    rng = np.random.default_rng(seed)
    tf_index, ga_by_tf = _draw_team_ga(df, n_sims, rng)
    for start in range(0, len(df), batch_rows):
        block = df.iloc[start:start + batch_rows]
        ga = ga_by_tf[tf_index[start:start + batch_rows]]
        yield block, ga, rng


def iter_sample_blocks(params: pd.DataFrame, n_sims: int = 10000, seed: int = 0,
                       batch_rows: int = 400) -> Iterator[tuple[pd.DataFrame, np.ndarray]]:
    """Yield ``(block, draws)`` per memory-bounded batch — the shared raw-draw primitive (spec Phase-4 §1).

    ``params`` is a :func:`model.compose.compose_parameters` output (any extra columns — e.g. a realized
    ``y`` — ride along on each yielded ``block``). Team goals-against is drawn **once** per team-fixture and
    shared (drawn up front from a single seeded rng), then each block's other components are drawn per row;
    ``draws`` is the ``(n_block_rows, n_sims)`` sampled-points matrix. :func:`simulate_points` reduces it to
    summaries, ``calibration`` scores it against realized points — so the rng stream is identical across both.
    """
    for block, ga, rng in _iter_draw_batches(params, n_sims, seed, batch_rows):
        yield block, _simulate_rows(block, ga, n_sims, rng)


def iter_component_blocks(params: pd.DataFrame, n_sims: int = 10000, seed: int = 0,
                          batch_rows: int = 400) -> Iterator[tuple[pd.DataFrame, dict[str, np.ndarray]]]:
    """Yield ``(block, components)`` per batch — the per-term decomposition of the same draws.

    ``components`` maps each :data:`DECOMP_TERMS` name to its ``(n_block_rows, n_sims)`` point matrix.
    Shares :func:`_iter_draw_batches` with :func:`iter_sample_blocks`, so the draws are the same stream;
    this is the ground-truth ``E[rule(X)]`` the scoring-conformance check compares compose against."""
    for block, ga, rng in _iter_draw_batches(params, n_sims, seed, batch_rows):
        yield block, _simulate_components(block, ga, n_sims, rng)


def simulate_points(params: pd.DataFrame, n_sims: int = 10000, seed: int = 0,
                    batch_rows: int = 400) -> pd.DataFrame:
    """Monte-Carlo the points distribution for each scored player-GW row of a parameter panel.

    ``params`` is a :func:`model.compose.compose_parameters` output. Draws come from the shared
    :func:`iter_sample_blocks` primitive (team-GA shared per team-fixture, components per row); this only
    reduces each block to per-row summaries: ``sim_mean, sim_sd, p10, p50, p90, p_haul`` (P(points>=10)).
    """
    out = []
    for block, pts in iter_sample_blocks(params, n_sims=n_sims, seed=seed, batch_rows=batch_rows):
        q10, q50, q90 = np.percentile(pts, [10, 50, 90], axis=1)
        out.append(pd.DataFrame({
            "player_id": block["player_id"].to_numpy(), "gw": block["gw"].to_numpy(),
            "position": block["position"].to_numpy(),
            "sim_mean": pts.mean(axis=1), "sim_sd": pts.std(axis=1),
            "p10": q10, "p50": q50, "p90": q90,
            "p_haul": (pts >= HAUL_THRESHOLD).mean(axis=1),
        }))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=_SUMMARY_COLUMNS)


def simulate_from_mart(mart: pd.DataFrame, n_sims: int = 10000, seed: int = 0) -> pd.DataFrame:
    """Convenience: build the parameter panel from the registry then simulate its distribution."""
    return simulate_points(compose_parameters(mart), n_sims=n_sims, seed=seed)


def simulator_consistency(mart: pd.DataFrame, n_sims: int = 4000, seed: int = 0) -> dict:
    """Aggregate consistency smoke-test: sim mean vs compose ``e_points`` (NOT a predictive gate).

    A fast corr / mean-abs-diff on the non-GK aggregate. Superseded for diagnosis by
    :func:`model.eval.scoring_conformance.scoring_conformance`, which is **per term and includes GK** —
    this aggregate view, and its GK exclusion, is exactly what hid the saves ``rule(E)`` gap. Kept as a
    cheap top-line check. The only residual nonconformity is now the bonus clip (saves/conceded are exact
    since the scoring-conformance slice); ``mean_abs_diff`` should be tiny. Returns ``{corr, mean_abs_diff, n}``.
    """
    sim = simulate_points(compose_parameters(mart), n_sims=n_sims, seed=seed)
    ep = compose_points(mart)[["player_id", "gw", "e_points"]]
    merged = sim.merge(ep, on=["player_id", "gw"], how="inner")
    merged = merged[merged["position"] != "GK"].dropna(subset=["e_points", "sim_mean"])
    return {
        "corr": round(float(np.corrcoef(merged["sim_mean"], merged["e_points"])[0, 1]), 4),
        "mean_abs_diff": round(float(np.abs(merged["sim_mean"] - merged["e_points"]).mean()), 4),
        "n": len(merged),
    }
