"""Panel-structure correlation kernel — domain-agnostic rank-correlation decomposition.

Spearman (default) or Kendall tau-b (``method="kendall"``) — the latter tie-corrected for
heavily tied (zero-inflated) signals, offered as a sensitivity check on the Spearman read.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from research.kernels.diagnostic._rankcorr import _METHODS
from research.kernels.diagnostic._rankcorr import rank_corr as _rank_corr

# Bootstrap defaults — mirror inferential.resampling so studies quote comparable
# intervals; kept local so this kernel stays a leaf (no cross-kernel import).
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 0
CI_LEVEL = 0.95


def split_between_within_player_rho(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    player_col: str = "player_id",
    min_n_players: int = 20,
    min_n_records: int = 100,
    min_appearances: int = 1,
    method: str = "spearman",
) -> dict[str, Any]:
    """Separate the pooled rank correlation into between-player and within-player contributions.

    ``rho_between`` compares players' season averages (identity structure); ``rho_within``
    compares each player's weeks to their own average (state structure). The **point**
    ``panel_class`` is the sign of the dominance contrast ``|rho_between| - |rho_within|``
    (``dominance``): whichever axis is larger in magnitude. This is a point direction only — it
    has no uncertainty and therefore does not abstain; the CI-gated, abstaining classification
    used for governance lives in ``bootstrap_panel_decomposition``. ``method`` selects the rank
    correlation — ``'spearman'`` (default) or ``'kendall'`` (tau-b, tie-corrected); the Kendall
    read is the notebook's tie-robustness cross-check on the direction.

    ``within_share`` (``|rho_within| / |rho_pooled|``) is retained as a **descriptive** field
    only — it is structurally biased (``rho_between`` never enters) and no longer classifies.
    ``min_appearances`` drops players with fewer than that many games before the split (default
    1 = no filter).

    Output fields:
      panel_class:        identity_dominant | state_sensitive (point dominance direction);
                          mixed only on an exact |rho| tie; indeterminate when rho_within is not
                          estimable. The CI-gated mixed and abstentions live in
                          bootstrap_panel_decomposition.
      dominance:          |rho_between| - |rho_within| (point); NaN when rho_within is not estimable
      decomposition_flag: empty string on success; 'unstable_ratio' when
                          abs(rho_within) > abs(rho_pooled) (descriptive note on within_share).
      support_flag:       'insufficient_support' when n < min_n_records or
                          n_players < min_n_players; empty string otherwise.
    """
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")

    empty = {
        "rho_pooled": np.nan,
        "rho_between": np.nan,
        "rho_within": np.nan,
        "within_share": np.nan,
        "dominance": np.nan,
        "panel_class": "indeterminate",
        "decomposition_flag": "",
        "n_records": 0,
        "n_players": 0,
        "support_flag": "insufficient_support",
    }

    subset = df[df["position"] == position][[player_col, signal, target]].dropna().copy()
    if min_appearances > 1:
        # Share one population with the Step-1 between/within partition: drop players with too few
        # games, whose season mean (between) and own-deviations (within) would otherwise be unreliable.
        appearances = subset.groupby(player_col)[player_col].transform("size")
        subset = subset[appearances >= min_appearances]
    n = len(subset)

    if n < min_n_records:
        return {**empty, "n_records": n}

    # One grouped pass: player means feed both rho_between and the within-player demeaning.
    g = subset.groupby(player_col)
    pmeans = g[[signal, target]].mean()
    n_players = len(pmeans)

    if n_players < min_n_players:
        return {**empty, "n_records": n, "n_players": n_players}

    rho_between = _rank_corr(
        pmeans[signal].astype(float),
        pmeans[target].astype(float),
        method,
    )

    # Within-player deviations (state structure): value minus the player's own mean. After the
    # top-level dropna these are never null, so no re-filter or length re-check is needed.
    sig_dm = subset[signal].astype(float) - subset[player_col].map(pmeans[signal]).astype(float)
    tgt_dm = subset[target].astype(float) - subset[player_col].map(pmeans[target]).astype(float)
    rho_within_val = _rank_corr(sig_dm, tgt_dm, method)

    rho_pooled = _rank_corr(
        subset[signal].astype(float),
        subset[target].astype(float),
        method,
    )

    decomposition_flag = ""
    within_share = np.nan
    panel_class = "indeterminate"
    dominance = np.nan

    # within_share: descriptive only (structurally biased — does not classify).
    if abs(rho_pooled) > 0.01 and not np.isnan(rho_within_val):
        raw_ratio = abs(rho_within_val) / abs(rho_pooled)
        if raw_ratio > 1.0:
            decomposition_flag = "unstable_ratio"
        else:
            within_share = round(float(raw_ratio), 3)

    # panel_class: point dominance of |rho_between| vs |rho_within| (no CI -> no abstention).
    if not np.isnan(rho_within_val) and not np.isnan(rho_between):
        dominance = round(float(abs(rho_between) - abs(rho_within_val)), 4)
        if dominance > 0:
            panel_class = "identity_dominant"
        elif dominance < 0:
            panel_class = "state_sensitive"
        else:
            panel_class = "mixed"

    return {
        "rho_pooled": round(float(rho_pooled), 4),
        "rho_between": round(float(rho_between), 4),
        "rho_within": round(float(rho_within_val), 4) if not np.isnan(rho_within_val) else np.nan,
        "within_share": within_share,
        "dominance": dominance,
        "panel_class": panel_class,
        "decomposition_flag": decomposition_flag,
        "n_records": n,
        "n_players": n_players,
        "support_flag": "",
    }


def _safe_rank_corr(a: np.ndarray, b: np.ndarray, method: str) -> float:
    """Rank correlation, or NaN when either side is constant (avoids scipy's warning/NaN noise)."""
    if np.unique(a).size <= 1 or np.unique(b).size <= 1:
        return np.nan
    return _rank_corr(a, b, method)


def _percentile_ci(values: list[float], ci_level: float) -> tuple[float, float]:
    """Two-sided percentile CI over the non-NaN bootstrap draws, rounded to 4 dp."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (np.nan, np.nan)
    alpha = 1.0 - ci_level
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return (round(lo, 4), round(hi, 4))


def _bootstrap_two_sided_p(values: list[float]) -> float:
    """Two-sided bootstrap p-value for H0: statistic = 0, over the non-NaN draws.

    Uses the ``(1 + k) / (1 + n)`` plug-in so the p-value is never exactly 0 (no finite draw
    count is treated as infinitely significant). Because the draws are player-resampled, this
    p-value respects player clustering — unlike scipy's Spearman p, which assumes independent
    rows and is anticonservative when the same players recur. Feeds the BH-FDR screen.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return np.nan
    tail = min(int(np.sum(arr <= 0.0)), int(np.sum(arr >= 0.0)))
    return round(min(1.0, 2.0 * (1 + tail) / (1 + arr.size)), 4)


def _excludes_zero(ci: tuple[float, float]) -> bool:
    """True when a (lo, hi) CI is finite and does not straddle 0."""
    lo, hi = ci
    return not np.isnan(lo) and not (lo <= 0.0 <= hi)


def _dominance_class(
    pooled_ci: tuple[float, float],
    diff_ci: tuple[float, float],
    between_ci: tuple[float, float],
    within_ci: tuple[float, float],
) -> str:
    """CI-gated dominance label from the bootstrap CIs (first match wins).

    Priority: undecomposable (no association to split) > directional dominance (diff CI excludes 0)
    > mixed (diff CI straddles 0 but both axes real) > indeterminate.
    """
    if not np.isnan(pooled_ci[0]) and pooled_ci[0] <= 0.0 <= pooled_ci[1]:
        return "undecomposable"  # CI for the pooled association includes 0
    if not np.isnan(diff_ci[0]) and diff_ci[0] > 0.0:
        return "identity_dominant"  # dominance CI wholly above 0
    if not np.isnan(diff_ci[1]) and diff_ci[1] < 0.0:
        return "state_sensitive"  # dominance CI wholly below 0
    if _excludes_zero(between_ci) and _excludes_zero(within_ci):
        return "mixed"  # contrast straddles 0 but both axes are real
    return "indeterminate"  # contrast straddles 0 and an axis is not established


def bootstrap_panel_decomposition(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    player_col: str = "player_id",
    n_boot: int = N_BOOTSTRAP,
    ci_level: float = CI_LEVEL,
    seed: int = BOOTSTRAP_SEED,
    min_n_players: int = 20,
    min_n_records: int = 100,
    min_appearances: int = 1,
    method: str = "spearman",
) -> dict[str, Any]:
    """Player-clustered bootstrap CIs for the between/within split, with a CI-gated dominance class.

    ``method`` ('spearman' default, or 'kendall' tau-b for tie-heavy signals) and ``min_appearances``
    (default 1 = no filter) are passed through to the point estimate and every bootstrap draw, so the
    CI is computed on the same metric and the same player population.

    Resamples **players** (clusters) with replacement ``n_boot`` times, recomputing the full
    decomposition each draw, and returns percentile CIs for ``rho_pooled`` / ``rho_between`` /
    ``rho_within`` / ``within_share`` and — the classification object — the **dominance contrast**
    ``dominance = |rho_between| - |rho_within|`` computed per (paired) draw. The point estimate alone
    over-claims on one season; the CI adds uncertainty and only assigns a directional class when the
    evidence is unambiguous.

    Resampling is clustered by **player, not row**: the between/within structure is defined by
    the player grouping, so a row bootstrap would dissolve it. A player drawn twice contributes
    twice (its rows enter the pooled/within draw twice and its mean enters the between draw
    twice), which is what gives the CI its honest, player-driven width.

    ``panel_class`` (CI-gated dominance — assigned only when earned, else abstains):
      * ``identity_dominant`` — the ``dominance`` CI lies wholly above 0 (between decisively larger).
      * ``state_sensitive``   — the ``dominance`` CI lies wholly below 0 (within decisively larger).
      * ``mixed``             — the ``dominance`` CI straddles 0 but **both** axis CIs exclude 0
                                (both structures real, neither dominates).
      * ``indeterminate``     — the ``dominance`` CI straddles 0 and an axis CI includes 0.
      * ``undecomposable``    — the ``rho_pooled`` CI includes 0 (no association to split).
      * ``insufficient_support`` — below the sample floors; no bootstrap is attempted.

    ``within_share`` is retained as a **descriptive** field only (structurally biased; no longer
    classifies). ``undecomposable`` / ``insufficient_support`` are kernel-internal abstentions;
    consumers that persist to the four-value registry schema collapse them to ``indeterminate``.

    Returns:
        ``{rho_pooled, rho_pooled_ci, rho_pooled_p, rho_between, rho_between_ci, rho_within,
        rho_within_ci, within_share, within_share_ci, dominance, dominance_ci, panel_class,
        decomposition_flag, n_records, n_players, n_boot, support_flag}``. Each ``*_ci`` is a
        ``(lower, upper)`` tuple (NaNs when not estimable); ``rho_pooled_p`` is the player-clustered
        bootstrap p-value for pooled != 0 (feeds the BH-FDR screen). Deterministic given ``seed``.
    """
    point = split_between_within_player_rho(
        df,
        signal,
        target,
        position,
        player_col=player_col,
        min_n_players=min_n_players,
        min_n_records=min_n_records,
        min_appearances=min_appearances,
        method=method,
    )
    nan_ci = (np.nan, np.nan)
    base = {
        "rho_pooled": point["rho_pooled"],
        "rho_pooled_ci": nan_ci,
        "rho_pooled_p": np.nan,
        "rho_between": point["rho_between"],
        "rho_between_ci": nan_ci,
        "rho_within": point["rho_within"],
        "rho_within_ci": nan_ci,
        "within_share": point["within_share"],
        "within_share_ci": nan_ci,
        "dominance": point["dominance"],
        "dominance_ci": nan_ci,
        "panel_class": point["panel_class"],
        "decomposition_flag": point["decomposition_flag"],
        "n_records": point["n_records"],
        "n_players": point["n_players"],
        "n_boot": 0,
        "support_flag": point["support_flag"],
    }
    if point["support_flag"] == "insufficient_support":
        return {**base, "panel_class": "insufficient_support"}

    # Precompute the fixed building blocks on the analysis subset. A player's own-mean
    # deviations do not change with which players are resampled, so they are computed once.
    subset = df[df["position"] == position][[player_col, signal, target]].dropna()
    if min_appearances > 1:
        appearances = subset.groupby(player_col)[player_col].transform("size")
        subset = subset[appearances >= min_appearances]
    subset = subset.reset_index(drop=True)
    sig = subset[signal].to_numpy(dtype=float)
    tgt = subset[target].to_numpy(dtype=float)
    sig_dm = sig - subset.groupby(player_col)[signal].transform("mean").to_numpy(dtype=float)
    tgt_dm = tgt - subset.groupby(player_col)[target].transform("mean").to_numpy(dtype=float)

    groups = subset.groupby(player_col, sort=False)
    pmeans = groups.agg(x_mean=(signal, "mean"), y_mean=(target, "mean"))
    mean_sig = pmeans["x_mean"].to_numpy(dtype=float)
    mean_tgt = pmeans["y_mean"].to_numpy(dtype=float)
    row_index_by_player = [groups.indices[p] for p in pmeans.index]
    n_players = len(pmeans)

    rng = np.random.default_rng(seed)
    boot = {"pooled": [], "between": [], "within": [], "share": [], "diff": []}
    for _ in range(n_boot):
        drawn = rng.integers(0, n_players, size=n_players)
        rho_b = _safe_rank_corr(mean_sig[drawn], mean_tgt[drawn], method)
        rows = np.concatenate([row_index_by_player[d] for d in drawn])
        rho_p = _safe_rank_corr(sig[rows], tgt[rows], method)
        rho_w = _safe_rank_corr(sig_dm[rows], tgt_dm[rows], method)
        share = abs(rho_w) / abs(rho_p) if (abs(rho_p) > 0.01 and not np.isnan(rho_w)) else np.nan
        # Paired dominance contrast: same resample for both axes, so its CI reflects their
        # covariance (subtracting the marginal CIs would not).
        diff = abs(rho_b) - abs(rho_w) if not (np.isnan(rho_b) or np.isnan(rho_w)) else np.nan
        boot["pooled"].append(rho_p)
        boot["between"].append(rho_b)
        boot["within"].append(rho_w)
        boot["share"].append(share)
        boot["diff"].append(diff)

    pooled_ci = _percentile_ci(boot["pooled"], ci_level)
    between_ci = _percentile_ci(boot["between"], ci_level)
    within_ci = _percentile_ci(boot["within"], ci_level)
    diff_ci = _percentile_ci(boot["diff"], ci_level)

    # CI-gated dominance classification: abstain unless the evidence is unambiguous.
    panel_class = _dominance_class(pooled_ci, diff_ci, between_ci, within_ci)

    return {
        **base,
        "rho_pooled_ci": pooled_ci,
        "rho_pooled_p": _bootstrap_two_sided_p(boot["pooled"]),
        "rho_between_ci": between_ci,
        "rho_within_ci": within_ci,
        "within_share_ci": _percentile_ci(boot["share"], ci_level),
        "dominance_ci": diff_ci,
        "panel_class": panel_class,
        "n_boot": n_boot,
    }
