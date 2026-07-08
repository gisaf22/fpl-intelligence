"""Phase 2.1 - count models for the point components.

First deliverable: the **over-dispersion diagnosis** (Phase 2 gate 1). Before fitting
any component model we test the *shape* of each count component per position - is it
over-dispersed and/or zero-inflated relative to Poisson? The diagnosis picks the family
by evidence, not habit (Poisson vs Negative Binomial vs zero-inflated / hurdle).

Method (per position x count component, e.g. goals_scored / assists):
  * index of dispersion = Var/Mean (for an intercept-only Poisson this *is* the Pearson
    dispersion statistic; > 1 signals over-dispersion),
  * NB vs Poisson likelihood-ratio test on the dispersion parameter alpha (H0: alpha = 0 is on
    the boundary -> the LR statistic is a 50:50 chi-sq(0)/chi-sq(1) mixture, so the one-sided
    p-value is half the naive chi-sq(1) tail),
  * zero-inflation check: observed P(y=0) vs the Poisson-implied exp(-mean) - a large
    positive excess beyond what NB explains points to ZIP/hurdle.

This is the **marginal** shape (intercept-only). Dispersion is re-checked conditional on
covariates when the mean model is fitted (features add explanation that can absorb some
apparent over-dispersion). Clean sheets are **binary** (Bernoulli) - not a count - and
are excluded from this diagnosis by construction.

Population matches Phase 0/1: ``minutes > 0``, DGW excluded, per position.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.discrete.discrete_model import NegativeBinomial

# Count components modelled with a Poisson/NB family (clean sheets are Bernoulli - separate).
COUNT_COMPONENTS = ("goals_scored", "assists")
POSITIONS = ("GK", "DEF", "MID", "FWD")

# Dispersion index above this flags over-dispersion (Poisson assumes Var == Mean, index 1).
DISPERSION_FLAG = 1.5
# Minimum rows before a diagnosis is reported (thin count slices are unstable).
MIN_ROWS = 50


def diagnose_overdispersion(y: pd.Series | np.ndarray) -> dict[str, float | str]:
    """Marginal count-shape diagnosis for one component slice.

    Returns a dict with: n, mean, var, dispersion_index (Var/Mean), nb_alpha,
    lrt_stat, lrt_p (NB vs Poisson, boundary-corrected), obs_zero, poisson_zero,
    excess_zero, and a ``family`` recommendation in {poisson, negative_binomial,
    zero_inflated}. Returns NaNs / ``insufficient`` when the slice is too thin or degenerate.
    """
    y = np.asarray(pd.Series(y).dropna(), dtype=float)
    n = y.size
    nan = {
        "n": n, "mean": float("nan"), "var": float("nan"), "dispersion_index": float("nan"),
        "nb_alpha": float("nan"), "lrt_stat": float("nan"), "lrt_p": float("nan"),
        "obs_zero": float("nan"), "poisson_zero": float("nan"), "excess_zero": float("nan"),
        "family": "insufficient",
    }
    if n < MIN_ROWS or y.max() == y.min():
        return nan

    mean = float(y.mean())
    var = float(y.var(ddof=1))
    dispersion = var / mean if mean > 0 else float("nan")
    obs_zero = float((y == 0).mean())
    poisson_zero = float(np.exp(-mean)) if mean > 0 else float("nan")
    excess_zero = obs_zero - poisson_zero

    # NB vs Poisson LRT on the dispersion parameter (intercept-only).
    exog = np.ones((n, 1))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            poisson = sm.GLM(y, exog, family=sm.families.Poisson()).fit()
            nb = NegativeBinomial(y, exog).fit(disp=0, maxiter=200)
            nb_alpha = float(np.asarray(nb.params)[-1])  # last param is the dispersion alpha
            stat = max(0.0, 2.0 * (float(nb.llf) - float(poisson.llf)))
            lrt_p = 0.5 * float(stats.chi2.sf(stat, df=1))  # boundary-corrected
        except Exception:
            nb_alpha, stat, lrt_p = float("nan"), float("nan"), float("nan")

    # Family recommendation by evidence. Distinguish *statistical* over-dispersion (LRT,
    # sensitive to n) from *material* over-dispersion (dispersion index): with thousands of
    # rows the LRT flags even a ~1.1 index, so NB is technically justified but ~ Poisson.
    lrt_significant = not np.isnan(lrt_p) and lrt_p < 0.05
    material = dispersion > DISPERSION_FLAG
    if lrt_significant or material:
        family = "negative_binomial"
        # Only flag ZIP/hurdle if zeros exceed what an NB with this mean/dispersion implies.
        if excess_zero > 0.10 and obs_zero > 0.6:
            family = "zero_inflated"
    else:
        family = "poisson"

    return {
        "n": n, "mean": round(mean, 4), "var": round(var, 4),
        "dispersion_index": round(dispersion, 3), "material_overdispersion": bool(material),
        "nb_alpha": round(nb_alpha, 4), "lrt_stat": round(stat, 3), "lrt_p": lrt_p,
        "obs_zero": round(obs_zero, 4), "poisson_zero": round(poisson_zero, 4),
        "excess_zero": round(excess_zero, 4), "family": family,
    }


# Minutes bands for the exposure structure read (lo exclusive, hi inclusive).
MINUTES_BANDS = ((1, 30), (30, 60), (60, 90))


def analyze_minutes_exposure(
    mart: pd.DataFrame, component: str = "goals_scored"
) -> pd.DataFrame:
    """Does the component rate scale proportionally with minutes played? (Exposure test.)

    Contemporaneous structural read (same-week minutes and component), per position:
      * per-90 component rate within minutes bands (is the rate flat across bands?),
      * pooled Poisson coefficient beta on log(minutes) with CI. beta ~ 1 => proportional
        exposure (a fixed log-minutes offset is justified); beta < 1 (CI excludes 1) =>
        sub-proportional (offset invalid - minutes must enter as a free covariate / bands).

    Caveat: pooled contemporaneous minutes-vs-component mixes mechanical exposure with
    player selection (starters are better players than subs) and small-minute denominators
    inflate per-90 rates. So this measures the *effective* minutes-rate relationship a model
    must respect, not a clean causal exposure. Either way it decides the offset question.

    Returns a frame indexed by position with per-band per-90 rates, beta + CI, and a
    ``proportional`` flag (CI includes 1) / ``verdict``.
    """
    pop = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))]
    rows = []
    for pos in ("DEF", "MID", "FWD"):
        sub = pop[pop["position"] == pos]
        if len(sub) < MIN_ROWS:
            continue
        rec: dict[str, float | str | bool] = {"position": pos, "n": len(sub)}
        for lo, hi in MINUTES_BANDS:
            b = sub[(sub["minutes"] > lo) & (sub["minutes"] <= hi)]
            rec[f"rate90_{lo}_{hi}"] = (
                round(90 * b[component].sum() / b["minutes"].sum(), 3) if len(b) else float("nan")
            )
        x = sm.add_constant(np.log(sub["minutes"].to_numpy()))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = sm.GLM(sub[component].to_numpy(), x, family=sm.families.Poisson()).fit()
        beta = float(r.params[1])
        lo_ci, hi_ci = (float(v) for v in r.conf_int()[1])
        proportional = lo_ci <= 1.0 <= hi_ci
        rec.update({
            "beta_logmin": round(beta, 3), "beta_lo": round(lo_ci, 3), "beta_hi": round(hi_ci, 3),
            "proportional": proportional,
            "verdict": "proportional (offset ok)" if proportional else "sub-proportional (offset invalid)",
        })
        rows.append(rec)
    return pd.DataFrame(rows).set_index("position")


def diagnose_by_position(
    mart: pd.DataFrame, components: tuple[str, ...] = COUNT_COMPONENTS
) -> pd.DataFrame:
    """Over-dispersion diagnosis per (position, count component) on the Phase-0/1 population.

    Returns a frame indexed by (position, component) with the diagnosis columns, positions
    ordered GK->DEF->MID->FWD. GK is skipped for attacking components (no support by design).
    """
    pop = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))]
    rows = []
    for pos in POSITIONS:
        sub = pop[pop["position"] == pos]
        for comp in components:
            # GK goals/assists are structurally absent - skip rather than report noise.
            if pos == "GK":
                continue
            d = diagnose_overdispersion(sub[comp])
            rows.append({"position": pos, "component": comp, **d})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values(["position", "component"]).set_index(["position", "component"])
