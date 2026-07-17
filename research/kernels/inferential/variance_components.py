"""Variance-components inference — Rung I.

The descriptive companion ``research.kernels.descriptive.variance_components.decompose_variance``
partitions the *observed* sum of squares into between/within shares. This module
gives the **inferential** read of the same split: a random-intercept model whose
parameters carry standard errors, so we can say whether between-player variance is
*real* (beyond sampling noise) and how big it is with uncertainty.

Model (per population, e.g. one position):

    y_{i,t} = beta0 + u_i + eps_{i,t}
    u_i     ~ N(0, sigma2_between)     # player random intercept (durable level)
    eps_{i,t} ~ N(0, sigma2_within)    # week-to-week residual
    ICC = sigma2_between / (sigma2_between + sigma2_within)

ICC is Q1's between-share as a *model parameter with a confidence interval*, not a
bootstrap percentile of an SS ratio. For a balanced panel ICC equals the SS-share
``pct_between``; our panel is unbalanced, so the two agree in magnitude and ordering
but not exactly (reconcile to tolerance — see the Phase 1 design doc).

Estimates come from a REML MixedLM fit. The between-variance CI is obtained by a
player-clustered (block) bootstrap of the MixedLM refit — consistent with the
project's resampling idiom and robust to the boundary problem that makes the naive
Wald CI on a variance component unreliable near zero. The LRT p-value tests the
random intercept against a pooled OLS null (ML refits, boundary-corrected).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

# Reuse the descriptive contract so the ICC population matches Q1 exactly.
from research.kernels.descriptive.variance_components import DEFAULT_MIN_APPEARANCES

# Default replicates for the clustered ICC bootstrap. The ICC fit is a one-shot per-position
# fit, so a few hundred refits is affordable; raise for tighter intervals.
DEFAULT_N_BOOTSTRAP = 300
DEFAULT_CI_LEVEL = 0.95
DEFAULT_SEED = 12345


def _fit_mixedlm(data: pd.DataFrame, value_col: str, group_col: str, reml: bool):
    """Fit y ~ 1 with a per-group random intercept. Returns the fitted result or None."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence / boundary chatter is expected on thin groups
        try:
            model = smf.mixedlm(f"{value_col} ~ 1", data, groups=data[group_col])
            return model.fit(reml=reml, method="lbfgs")
        except Exception:
            return None


def _components(result) -> tuple[float, float]:
    """(sigma2_between, sigma2_within) from a fitted MixedLM result."""
    # cov_re is the random-effect covariance (1x1 here); scale is the residual variance.
    sigma2_between = float(np.asarray(result.cov_re)[0, 0])
    sigma2_within = float(result.scale)
    return sigma2_between, sigma2_within


def _icc(sigma2_between: float, sigma2_within: float) -> float:
    total = sigma2_between + sigma2_within
    return sigma2_between / total if total > 0 else float("nan")


def mixed_effects_icc(
    df: pd.DataFrame,
    value_col: str = "total_points",
    group_col: str = "player_id",
    min_appearances: int = DEFAULT_MIN_APPEARANCES,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    ci_level: float = DEFAULT_CI_LEVEL,
    seed: int = DEFAULT_SEED,
) -> dict[str, float]:
    """Random-intercept variance-components inference for a single population.

    Same population contract as ``decompose_variance`` (drop NaN, keep groups with
    ``>= min_appearances`` rows). Fits a REML MixedLM for the point estimates, a
    player-clustered bootstrap for the ICC / sigma2_between confidence intervals,
    and an ML likelihood-ratio test against a pooled-OLS null for the random
    intercept.

    Returns a dict with keys:
        n_players, n_obs, grand_mean,
        sigma2_between, sigma2_within, icc,
        icc_ci_lo, icc_ci_hi, sigma2_between_ci_lo, sigma2_between_ci_hi,
        lrt_stat, lrt_p.
    All estimate keys are NaN if the model cannot be fit (too few groups/rows).
    """
    if group_col not in df.columns:
        raise ValueError(f"df missing required column: '{group_col}'")
    if value_col not in df.columns:
        raise ValueError(f"df missing required column: '{value_col}'")

    data = df[[group_col, value_col]].dropna()
    counts = data.groupby(group_col)[value_col].transform("count")
    data = data[counts >= min_appearances].reset_index(drop=True)

    n_obs = len(data)
    n_players = int(data[group_col].nunique())
    nan_result = {
        "n_players": n_players,
        "n_obs": n_obs,
        "grand_mean": float("nan"),
        "sigma2_between": float("nan"),
        "sigma2_within": float("nan"),
        "icc": float("nan"),
        "icc_ci_lo": float("nan"),
        "icc_ci_hi": float("nan"),
        "sigma2_between_ci_lo": float("nan"),
        "sigma2_between_ci_hi": float("nan"),
        "lrt_stat": float("nan"),
        "lrt_p": float("nan"),
    }
    # Need at least a couple of groups with repetition for a random intercept to be identified.
    if n_players < 2 or n_obs < 2 * min_appearances:
        return nan_result

    result = _fit_mixedlm(data, value_col, group_col, reml=True)
    if result is None:
        return nan_result

    sigma2_between, sigma2_within = _components(result)
    icc = _icc(sigma2_between, sigma2_within)
    grand_mean = float(data[value_col].mean())

    # --- ICC / between-variance CI via player-clustered bootstrap ---
    icc_reps: list[float] = []
    between_reps: list[float] = []
    rng = np.random.default_rng(seed)
    players = data[group_col].unique()
    groups = {g: sub for g, sub in data.groupby(group_col)}
    for _ in range(n_bootstrap):
        drawn = rng.choice(players, size=len(players), replace=True)
        # Relabel resampled players so repeated draws are distinct groups.
        parts = []
        for new_id, g in enumerate(drawn):
            block = groups[g].copy()
            block[group_col] = new_id
            parts.append(block)
        boot = pd.concat(parts, ignore_index=True)
        r = _fit_mixedlm(boot, value_col, group_col, reml=True)
        if r is None:
            continue
        b, w = _components(r)
        icc_reps.append(_icc(b, w))
        between_reps.append(b)

    alpha = 1.0 - ci_level
    lo_pct, hi_pct = 100 * alpha / 2, 100 * (1 - alpha / 2)
    if icc_reps:
        icc_ci_lo, icc_ci_hi = (float(x) for x in np.percentile(icc_reps, [lo_pct, hi_pct]))
        between_ci_lo, between_ci_hi = (float(x) for x in np.percentile(between_reps, [lo_pct, hi_pct]))
    else:
        icc_ci_lo = icc_ci_hi = between_ci_lo = between_ci_hi = float("nan")

    # --- LRT: random intercept vs pooled OLS (ML refits; boundary-corrected) ---
    lrt_stat, lrt_p = _random_intercept_lrt(data, value_col, group_col)

    return {
        "n_players": n_players,
        "n_obs": n_obs,
        "grand_mean": grand_mean,
        "sigma2_between": sigma2_between,
        "sigma2_within": sigma2_within,
        "icc": icc,
        "icc_ci_lo": icc_ci_lo,
        "icc_ci_hi": icc_ci_hi,
        "sigma2_between_ci_lo": between_ci_lo,
        "sigma2_between_ci_hi": between_ci_hi,
        "lrt_stat": lrt_stat,
        "lrt_p": lrt_p,
    }


def _random_intercept_lrt(data: pd.DataFrame, value_col: str, group_col: str) -> tuple[float, float]:
    """LRT for the random intercept vs a pooled-OLS null (ML fits).

    The null (no random intercept) sits on the boundary of the parameter space
    (sigma2_between = 0), so the LR statistic follows a 50:50 mixture of chi2(0) and
    chi2(1). The correct one-sided p-value is therefore half the naive chi2(1) tail.
    """
    mixed = _fit_mixedlm(data, value_col, group_col, reml=False)
    if mixed is None:
        return float("nan"), float("nan")
    ll_mixed = float(mixed.llf)
    # Pooled OLS null: intercept-only, no grouping.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ll_null = float(smf.ols(f"{value_col} ~ 1", data).fit().llf)
    stat = max(0.0, 2.0 * (ll_mixed - ll_null))
    p = 0.5 * float(stats.chi2.sf(stat, df=1))
    return stat, p


def between_share_bootstrap(
    sub: pd.DataFrame,
    value_col: str = "total_points",
    group_col: str = "player_id",
    n_boot: int = 3000,
    seed: int = 7,
    min_appearances: int = DEFAULT_MIN_APPEARANCES,
) -> np.ndarray:
    """Distribution-free player-clustered bootstrap of the between-player SS share (no normality).

    The normality-free companion to :func:`mixed_effects_icc`: because the between/within
    sum-of-squares partition needs no distributional assumption, this bootstraps it directly to
    check whether the Gaussian-LMM ICC's ordering and magnitude survive dropping normality. Returns
    the ``[2.5, 50, 97.5]`` percentiles of the between-share over ``n_boot`` player-clustered
    resamples. Vectorised via per-player sufficient stats: n_i, s_i=sum(x), q_i=sum(x^2);
    SS_within_i = q_i - s_i^2/n_i.
    """
    g = sub.groupby(group_col)[value_col]
    n = g.size().to_numpy(float)
    s = g.sum().to_numpy(float)
    q = g.apply(lambda x: float((x * x).sum())).to_numpy(float)
    keep = n >= min_appearances
    n, s, q = n[keep], s[keep], q[keep]
    p = len(n)
    rng = np.random.default_rng(seed)
    reps = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, p, p)
        big_n, big_s, big_q = n[idx].sum(), s[idx].sum(), q[idx].sum()
        grand = big_s / big_n
        sst = big_q - big_n * grand * grand
        ssw = (q[idx] - s[idx] ** 2 / n[idx]).sum()
        reps[b] = (sst - ssw) / sst if sst > 0 else np.nan
    return np.nanpercentile(reps, [2.5, 50, 97.5])
