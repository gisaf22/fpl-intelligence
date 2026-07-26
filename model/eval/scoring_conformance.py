"""Scoring-rule conformance: does ``compose``'s point estimate equal ``E[rule(X)]``, not ``rule(E[X])``?

FPL has three **nonlinear** scoring rules — ``floor(S/3)`` (saves), ``-floor(GA/2)`` (conceded), and the
bonus ``clip(·, 0, 3)`` — for which the point value of the payout is *not* the payout of the point value
(a Jensen gap). ``compose`` computes each term's expectation analytically; the **simulator** draws each
component then applies the rule per draw, so its per-term mean is the ground-truth ``E[rule(X)]``. This
check diffs the two, term by term, per position.

It is a **regression guard**: every exactly-computed term must conform to within Monte-Carlo error, so a
future refactor cannot silently reintroduce a ``rule(E)`` bug (the class the saves gap belonged to — and
which the old ``simulator_consistency`` could not see, comparing only aggregate ``e_points`` and excluding
GK). The one term that does **not** conform is ``bonus``: ``compose`` applies ``clip(E[returns])`` where
the honest value is ``E[clip(returns)]``. That residual is small (~0.02-0.04 pt/GW) and is **reported,
not asserted to zero** — the accepted approximation (fixing it would couple ``compose_points`` to a
stochastic draw for <0.05 pt; the simulator already carries the honest value for the *distribution*).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from model.compose import DECOMP_COLUMNS, compose_parameters, compose_points
from model.eval.walkforward import POSITIONS
from model.simulate import DECOMP_TERMS, iter_component_blocks

# The one term whose analytic point value is a known Jensen approximation, not an exact expectation.
NONCONFORMING_TERMS = ("bonus",)
# Assert gaps are within this many Monte-Carlo standard errors (4-sigma: a conforming term flakes ~1/16000).
MC_SIGMA = 4.0


def scoring_conformance(mart: pd.DataFrame, n_sims: int = 4000, seed: int = 0,
                        batch_rows: int = 400) -> pd.DataFrame:
    """Per (position, term): ``compose`` point mean vs the simulator's ``E[rule]`` mean, with an MC band.

    Ground truth is the simulator's per-component draw mean (:func:`model.simulate.iter_component_blocks`,
    the same draw stream ``simulate_points`` sums). One row per (position, term) with: ``compose`` (the
    analytic point mean over the scored rows), ``sim`` (the draw mean), ``gap`` (compose - sim), ``mc_se``
    (the standard error of ``sim`` under the null that compose is exact), ``asserted`` (False for the
    known-nonconforming ``bonus``), and ``conforms`` (``|gap| <= MC_SIGMA * mc_se``, or NaN where not
    asserted). Aggregating over the same rows both sides share means the comparison needs no row join.
    """
    params = compose_parameters(mart)
    decomp = compose_points(mart)[["player_id", "gw", *DECOMP_COLUMNS]]

    # accumulate per (position, term): row count, sum of compose point values, sum of sim per-row means,
    # sum of sim per-row draw-variances (for the MC standard error). Streamed over batches (memory-bounded).
    acc: dict[tuple[str, str], list[float]] = {
        (pos, term): [0.0, 0.0, 0.0, 0.0] for pos in POSITIONS for term in DECOMP_TERMS
    }
    for block, comps in iter_component_blocks(params, n_sims=n_sims, seed=seed, batch_rows=batch_rows):
        keyed = block[["player_id", "gw", "position"]].merge(decomp, on=["player_id", "gw"], how="left")
        pos = keyed["position"].to_numpy()
        for term in DECOMP_TERMS:
            comp = comps[term]                      # (n_block_rows, n_sims)
            row_mean = comp.mean(axis=1)
            row_var = comp.var(axis=1)
            cval = keyed[term].to_numpy(dtype=float)
            for p in POSITIONS:
                m = pos == p
                if not m.any():
                    continue
                a = acc[(p, term)]
                a[0] += int(m.sum())
                a[1] += float(np.nansum(cval[m]))
                a[2] += float(row_mean[m].sum())
                a[3] += float(row_var[m].sum())

    rows = []
    for pos in POSITIONS:
        for term in DECOMP_TERMS:
            n, csum, ssum, vsum = acc[(pos, term)]
            if n == 0:
                continue
            compose_mean = csum / n
            sim_mean = ssum / n
            # SE of the mean-over-rows of the per-row draw mean: Var = (1/n^2) * sum_row(var_row / n_sims).
            mc_se = float(np.sqrt((vsum / n_sims) / (n * n)))
            asserted = term not in NONCONFORMING_TERMS
            gap = compose_mean - sim_mean
            rows.append({
                "position": pos, "term": term, "n": int(n),
                "compose": round(compose_mean, 4), "sim": round(sim_mean, 4),
                "gap": round(gap, 4), "mc_se": round(mc_se, 5),
                "asserted": asserted,
                "conforms": (abs(gap) <= MC_SIGMA * mc_se) if asserted else np.nan,
            })
    return pd.DataFrame(rows)


def assert_conformance(mart: pd.DataFrame, n_sims: int = 4000, seed: int = 0) -> pd.DataFrame:
    """Raise ``AssertionError`` if any **asserted** term fails to conform; return the full table.

    The regression guard: goals/assists/clean_sheet/conceded/saves/DC/appearance must equal the
    simulator's ``E[rule]`` to within Monte-Carlo error. ``bonus`` is exempt (reported, not asserted).
    """
    table = scoring_conformance(mart, n_sims=n_sims, seed=seed)
    failed = table[(table["asserted"]) & (~table["conforms"].astype(bool))]
    if not failed.empty:
        detail = failed[["position", "term", "compose", "sim", "gap", "mc_se"]].to_string(index=False)
        raise AssertionError(
            f"scoring rule non-conformance (compose applies rule(E) where E[rule] is required):\n{detail}"
        )
    return table
