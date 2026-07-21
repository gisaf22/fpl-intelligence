"""Phase 4 - trust the probabilities: calibration + proper scoring of the simulator distributions.

A distribution is only useful if calibrated, and ranking (Spearman) cannot reveal miscalibration.
This validates the Phase-3.1 simulator's predictive distributions against realized ``total_points``
(same population as the sim: ``minutes>0``, DGW-excluded, GW>3 - so the missing-blank tail, X1, does
not create spurious miscalibration since sim and target share the population).

Instruments: **randomized PIT** (discreteness-correct), **reliability / ECE** for the haul (>=10) and a
less-rare return (>=6) events, 80% **interval coverage**, and **CRPS** vs three comparators
(point-forecast-degenerate, Poisson(mean), climatology-per-position). **Recalibration** (walk-forward
isotonic + Platt, no leakage) is applied to the event probabilities and the better one reported.

Two coverage numbers are reported, and they answer different questions (coverage-metric slice, Fork A):
  * ``cover`` - the **operational** hit rate of the shipped ``[p10, p90]`` interval (what a consumer
    reading the captaincy-ceiling / downside outputs actually experiences).
  * ``cover_pit`` - the **calibration gate**. FPL points are lumpy (a player who plays and returns
    nothing scores exactly 1 or 2), so the simulated distribution has large atoms and ``np.percentile``
    lands *inside* one: on the real mart the sim puts ~47% of its FWD mass at or below its own ``p10``,
    so ``[p10, p90]`` is not an 80% interval at all. Worse, bonus adds a *continuous* sliver to a
    *discrete* score, pushing ``p10`` to ~1.02 so the **modal** outcome ``y=1`` scores as a miss. The
    randomized PIT is discreteness-correct by construction, so ``0.10 <= u <= 0.90`` is an exact 80%
    interval under a correct model. It reuses the ``pit`` column - **no extra randomness** (Fork B).

Pre-registered tolerance (A4.1, stated before looking): haul **ECE <= 0.02**; 80% coverage in
**[0.75, 0.85]** per position. The band is **unmoved**; it now applies to the discreteness-correct
``cover_pit`` (the quantity changed, not the goalposts). Gate = within tolerance after at most one
recalibration pass, else documented residual miscalibration. This is an internal-honesty gate on
trustworthiness, not a ranking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson as _poisson
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from model.compose import compose_parameters, compose_points
from model.eval.walkforward import POSITIONS
from model.simulate import HAUL_THRESHOLD, iter_sample_blocks

RETURN_THRESHOLD = 6
HAUL_ECE_TOL = 0.02
COVERAGE_BAND = (0.75, 0.85)
MIN_RECAL_TRAIN = 200
COVERAGE_ALPHA = 0.10          # 80% central interval: PIT in [alpha, 1-alpha]
_EVAL_COLUMNS = ("position", "gw", "y", "e_points", "pit", "p_haul", "haul",
                 "p_return", "return_", "cover", "cover_pit", "crps_sim", "crps_point")


def _crps_empirical(draws: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Vectorized empirical CRPS per row: E|X-y| - 0.5 E|X-X'| via the sorted-sample formula."""
    n = draws.shape[1]
    xs = np.sort(draws, axis=1)
    idx = np.arange(1, n + 1)
    term1 = np.abs(draws - y[:, None]).mean(axis=1)
    term2 = ((2 * idx - n - 1) * xs).sum(axis=1) / (n * n)
    return term1 - term2


def simulate_eval(mart: pd.DataFrame, n_sims: int = 3000, seed: int = 0,
                  batch_rows: int = 400) -> pd.DataFrame:
    """Per player-GW predictive-vs-realized metrics over the shared draw primitive.

    Draws come from :func:`model.simulate.iter_sample_blocks` (the single home of the Monte-Carlo loop —
    no private-internal reach or duplicated loop); this layer only *scores* each block's raw draws against
    realized ``y``. Returns one row per scored player-GW: ``pit`` (randomized, discreteness-correct),
    ``p_haul``/``haul``, ``p_return``/``return_``, ``cover`` (operational: in ``[p10,p90]``),
    ``cover_pit`` (the discreteness-correct gate: ``pit`` in ``[0.1, 0.9]``), ``crps_sim``, ``crps_point``,
    plus ``position``, ``gw``, ``y`` (realized), ``e_points`` (the compose point forecast). The realized
    ``y``/``e_points`` ride along on each yielded block (extra ``params`` columns pass through).

    The PIT tie-jitter draws from a **separate** seeded rng (``seed+1``) — scoring owns its own randomness,
    so the draw primitive stays pure (Phase-4 Fork B: draw/score separation).
    """
    params = compose_parameters(mart)
    ep = compose_points(mart)[["player_id", "gw", "e_points"]]
    y_src = mart[["player_id", "gw", "total_points"]]
    df = params.merge(ep, on=["player_id", "gw"]).merge(y_src, on=["player_id", "gw"], how="left")
    # keep rows with a realized target + point forecast; iter_sample_blocks applies the _REQUIRED filter.
    df = df.dropna(subset=["total_points", "e_points"]).copy()
    df["y"] = pd.to_numeric(df["total_points"], errors="coerce")
    pit_rng = np.random.default_rng(seed + 1)

    out = []
    for block, d in iter_sample_blocks(df, n_sims=n_sims, seed=seed, batch_rows=batch_rows):
        y = block["y"].to_numpy(dtype=float)
        below = (d < y[:, None]).mean(axis=1)
        eq = (d == y[:, None]).mean(axis=1)
        pit = below + pit_rng.random(len(block)) * eq
        p10, p90 = np.percentile(d, [10, 90], axis=1)
        out.append(pd.DataFrame({
            "position": block["position"].to_numpy(), "gw": block["gw"].to_numpy(),
            "y": y, "e_points": block["e_points"].to_numpy(),
            "pit": pit,
            "p_haul": (d >= HAUL_THRESHOLD).mean(axis=1), "haul": (y >= HAUL_THRESHOLD).astype(int),
            "p_return": (d >= RETURN_THRESHOLD).mean(axis=1), "return_": (y >= RETURN_THRESHOLD).astype(int),
            "cover": ((p10 <= y) & (y <= p90)).astype(int),
            # discreteness-correct: derived from pit, so it adds no randomness of its own.
            "cover_pit": ((pit >= COVERAGE_ALPHA) & (pit <= 1 - COVERAGE_ALPHA)).astype(int),
            "crps_sim": _crps_empirical(d, y), "crps_point": np.abs(block["e_points"].to_numpy() - y),
        }))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=list(_EVAL_COLUMNS))


def expected_calibration_error(prob: np.ndarray, event: np.ndarray, bins: int = 10) -> float:
    """ECE: sum over probability bins of (bin share) x |observed rate - mean predicted|."""
    prob = np.asarray(prob, dtype=float)
    event = np.asarray(event, dtype=float)
    n = len(prob)
    e = 0.0
    for lo in np.linspace(0, 1, bins, endpoint=False):
        m = (prob >= lo) & (prob < lo + 1.0 / bins)
        if m.sum():
            e += m.sum() / n * abs(event[m].mean() - prob[m].mean())
    return float(e)


def _walk_forward_recalibrate(df: pd.DataFrame, prob: str, event: str, method: str) -> np.ndarray:
    """Out-of-sample recalibration: fit on ``gw<t``, apply to ``gw==t``. NaN where too-thin train."""
    out = np.full(len(df), np.nan)
    for t in sorted(df["gw"].unique()):
        tr = df[df["gw"] < t]
        te = (df["gw"] == t).to_numpy()
        if len(tr) < MIN_RECAL_TRAIN or tr[event].nunique() < 2:
            continue
        if method == "isotonic":
            m = IsotonicRegression(out_of_bounds="clip").fit(tr[prob].to_numpy(), tr[event].to_numpy())
            out[te] = m.predict(df.loc[te, prob].to_numpy())
        else:  # platt
            m = LogisticRegression().fit(tr[[prob]].to_numpy(), tr[event].to_numpy())
            out[te] = m.predict_proba(df.loc[te, [prob]].to_numpy())[:, 1]
    return out


def recalibration_table(ev: pd.DataFrame, prob: str, event: str) -> pd.DataFrame:
    """ECE of raw vs isotonic vs Platt on the common recalibratable set (fair comparison)."""
    iso = _walk_forward_recalibrate(ev, prob, event, "isotonic")
    platt = _walk_forward_recalibrate(ev, prob, event, "platt")
    common = ~np.isnan(iso) & ~np.isnan(platt)
    sub = ev[common]
    rows = [
        {"method": "raw", "ece": round(expected_calibration_error(sub[prob], sub[event]), 4)},
        {"method": "isotonic", "ece": round(expected_calibration_error(iso[common], sub[event]), 4)},
        {"method": "platt", "ece": round(expected_calibration_error(platt[common], sub[event]), 4)},
    ]
    return pd.DataFrame(rows).set_index("method")


def crps_table(ev: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Per-position mean CRPS: simulator vs point-forecast vs Poisson(mean) vs climatology (lower better)."""
    rng = np.random.default_rng(seed)
    y = ev["y"].to_numpy(dtype=float)
    pois_draws = _poisson.rvs(np.clip(ev["e_points"].to_numpy(), 1e-3, None)[:, None] * np.ones((1, 2000)),
                              random_state=rng)
    ev = ev.assign(crps_pois=_crps_empirical(pois_draws, y))
    ev = ev.assign(crps_clim=np.nan)
    for pos in POSITIONS:
        mask = (ev["position"] == pos).to_numpy()
        if mask.sum() < 2:
            continue
        clim = np.broadcast_to(y[mask], (mask.sum(), mask.sum()))
        ev.loc[mask, "crps_clim"] = _crps_empirical(clim, y[mask])
    tbl = ev.groupby("position")[["crps_sim", "crps_point", "crps_pois", "crps_clim"]].mean().round(3)
    return tbl.reindex(POSITIONS)


def event_counts(ev: pd.DataFrame) -> pd.DataFrame:
    """Per-position realized event counts — the **power** surface: haul (>=10) and return (>=6) are rare on
    one season, so a per-position ECE is only interpretable where the events are not a handful. Read
    alongside the ECE tables: few events => 'inconclusive/underpowered', not 'miscalibrated'."""
    tbl = ev.groupby("position").agg(n=("y", "size"), n_haul=("haul", "sum"), n_return=("return_", "sum"))
    return tbl.reindex(POSITIONS)


def calibration_report(mart: pd.DataFrame, n_sims: int = 3000, seed: int = 0) -> dict:
    """Full Phase-4 report: PIT, haul/return ECE (raw+recal), coverage vs tolerance, CRPS vs comparators,
    and per-position event counts (the power surface for honest interpretation).

    Coverage is reported twice: ``coverage`` is the **operational** ``[p10,p90]`` hit rate, and
    ``coverage_pit`` is the **discreteness-correct gate** the pre-registered band applies to. They differ
    materially because the points distribution is atomic (see the module docstring); reporting both is
    what makes the metric artifact visible rather than hidden.
    """
    ev = simulate_eval(mart, n_sims=n_sims, seed=seed)
    pit_deciles = np.histogram(ev["pit"], bins=10, range=(0, 1))[0] / len(ev)
    coverage = ev.groupby("position")["cover"].mean().round(3).reindex(POSITIONS)
    coverage_pit = ev.groupby("position")["cover_pit"].mean().round(3).reindex(POSITIONS)
    return {
        "n": len(ev),
        "pit_mean": round(float(ev["pit"].mean()), 3),
        "pit_deciles": np.round(pit_deciles, 3),
        "haul_ece": recalibration_table(ev, "p_haul", "haul"),
        "return_ece": recalibration_table(ev, "p_return", "return_"),
        "coverage": coverage,
        "coverage_pit": coverage_pit,
        # the gate is the discreteness-correct number; the band itself is unmoved (pre-registered).
        "coverage_in_band": {p: bool(COVERAGE_BAND[0] <= coverage_pit[p] <= COVERAGE_BAND[1])
                             for p in POSITIONS if not np.isnan(coverage_pit[p])},
        "crps": crps_table(ev, seed=seed),
        "events": event_counts(ev),
    }
