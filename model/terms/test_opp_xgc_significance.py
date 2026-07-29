"""Mean-features step-2 acceptance protocol, encoded as a test (goals + assists x opp_xgc_forward vs fdr).

`opp_xgc_forward` — the specific upcoming opponent's strictly-prior rolling conceded-xG (the dynamic,
defence-side candidate replacement for FPL's static one-number-per-team `fdr_avg`) — was BUILT
(model.features.build.add_opponent_xgc_forward + dal.pipeline.load_opponent_map) and measured against
`fdr_avg` on the real mart, walk-forward, and **REFUTED** (docs/model-redesign-mean-features-plan.md
step-2):

    BEATS gate (the shipping unit): the paired per-(gw, position) within-cell Spearman delta
      rho(selected + opp_xgc, fdr REMOVED) - rho(selected + fdr), pooled over the model's fit cells,
      block-bootstrapped. To beat the crude tier the CI must EXCLUDE 0 on the POSITIVE side.

Measured (recorded in the specs): goals opp_xgc - fdr = -0.0126, CI[-0.0206,-0.0031]; assists -0.0183,
CI[-0.0351,-0.0032] — both SIGNIFICANTLY NEGATIVE (opp_xgc ranks *below* fdr, and below the no-opponent
base). So `opp_xgc_forward` is NOT in the goals/assists pools; `fdr_avg` is kept.

That measurement needs the private mart, so here the *protocol machinery* is pinned on synthetic panels:
it must (a) REJECT opp_xgc as beating fdr when `fdr_avg` is the cleaner low-variance difficulty tier and
the realized conceded-xG roll is noisy (the real-world case that refuted it), and (b) ACCEPT opp_xgc
when it genuinely *is* the sharper signal — proving the machinery discriminates rather than being rigged
to reject. The build path (opponent broadcast + coverage fill) is exercised end to end by both.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.metrics import block_bootstrap_ci, cell_spearman, has_rank_signal
from model.eval.walkforward import MIN_ROWS_PER_POS, WARMUP_GW
from model.features.build import add_opponent_xgc_forward
from model.terms._poisson_component import PoissonPlayerComponentModel
from model.terms.assists import AssistsModel
from model.terms.assists.spec import ASSISTS_POOL
from model.terms.goals import GoalsModel
from model.terms.goals.spec import GOALS_POOL

pytestmark = pytest.mark.unit

# The `selected` base carried by the synthetic panels (as in test_fdr_significance); opp_xgc_forward and
# fdr_avg are the two rival opponent-difficulty additions compared head to head.
_BASE = ["xgi_roll3", "minutes_roll3", "xgi_roll5"]


def _panel(*, fdr_noise: float, xgc_noise: float, signal: float = 0.9,
           seed: int = 0, n_teams: int = 20, n_gw: int = 22) -> pd.DataFrame:
    """A player-GW panel with a coherent opponent schedule and a stable per-team defensive leakiness.

    Each team has a latent leakiness ``leak`` (stable across the season). A team's realized conceded-xG
    ``xgc`` is ``leak`` plus noise scaled by ``xgc_noise`` (so the opponent's rolling ``xgc`` estimates
    ``leak`` — well when ``xgc_noise`` is small, poorly when large). ``fdr_avg`` is a 2..5 tier of the
    opponent's ``leak`` plus noise scaled by ``fdr_noise`` (a clean tier when small). The attacker's rate
    rises with the *true* opponent leak, so both rivals predict the target through ``leak`` and the winner
    is whichever estimates it with less noise — exactly the fdr-tier-vs-noisy-roll trade-off at issue.
    """
    rng = np.random.default_rng(seed)
    leak = {t: rng.uniform(0.4, 1.8) for t in range(n_teams)}
    players, pid = [], 0
    for team in range(n_teams):
        for pos, k in (("GK", 1), ("DEF", 4), ("MID", 4), ("FWD", 2)):
            for _ in range(k):
                players.append((pid, team, pos, rng.uniform(0.05, 0.55)))
                pid += 1
    rows = []
    for gw in range(1, n_gw + 1):
        order = rng.permutation(n_teams)
        opp = {}
        for i in range(0, n_teams, 2):
            a, b = int(order[i]), int(order[i + 1])
            opp[a], opp[b] = b, a
        for pl, team, pos, skill in players:
            o = opp[team]
            xgc = max(0.0, leak[team] + rng.normal(0, xgc_noise))           # team's OWN conceded-xG
            fdr = float(np.clip(round(2 + 2 * (leak[o] - 0.4) / 1.4 + rng.normal(0, fdr_noise)), 2, 5))
            mult = max(0.05, 0.4 + signal * (leak[o] - 0.4))               # leaky opponent -> higher rate
            a_lam = skill * 0.6 * mult
            rows.append({
                "player_id": pl, "team_id": team, "opponent_team_id": o, "gw": gw,
                "position": pos, "minutes": 90, "is_dgw": False,
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.04),
                "minutes_roll3": 90.0, "fdr_avg": fdr, "xgc": xgc,
                "goals_scored": 0 if pos == "GK" else rng.poisson(skill * mult),
                "assists": rng.poisson(a_lam),
            })
    panel = pd.DataFrame(rows)
    # Materialize the opponent-forward roll (the build path under test); models draw it via feature_override.
    return add_opponent_xgc_forward(panel, window=5)


def _beats_fdr_deltas(model_cls: type[PoissonPlayerComponentModel], panel: pd.DataFrame) -> np.ndarray:
    """Paired rho(selected + opp_xgc, no fdr) - rho(selected + fdr) per (gw, position) cell, walk-forward.

    Positive => opp_xgc out-ranks the crude fdr tier; the block-bootstrap CI of the mean is the shipping
    unit. Mirrors test_fdr_significance's ``_paired_delta_series`` but compares the two rival features."""
    target = model_cls.target
    pop = model_cls.population(panel)
    r_fdr = model_cls(variant="selected", feature_override=[*_BASE, "fdr_avg"]).fit(panel).predictions
    r_opp = model_cls(variant="selected", feature_override=[*_BASE, "opp_xgc_forward"]).fit(panel).predictions
    df = pop.copy()
    df["fdr"], df["opp"] = r_fdr.to_numpy(), r_opp.to_numpy()
    df = df[df["gw"] > WARMUP_GW].dropna(subset=["fdr", "opp", target])
    df = df[df["position"].isin(model_cls.fit_positions)]
    deltas = []
    for _, g in df.groupby(["gw", "position"]):
        if has_rank_signal(g, "opp", target, MIN_ROWS_PER_POS) and has_rank_signal(g, "fdr", target, MIN_ROWS_PER_POS):
            deltas.append(cell_spearman(g["opp"].to_numpy(), g[target].to_numpy())
                          - cell_spearman(g["fdr"].to_numpy(), g[target].to_numpy()))
    return np.asarray(deltas, dtype=float)


@pytest.mark.parametrize("model_cls", [GoalsModel, AssistsModel])
def test_protocol_rejects_opp_xgc_when_fdr_is_the_cleaner_tier(
    model_cls: type[PoissonPlayerComponentModel],
) -> None:
    """The refutation, reproduced: a clean fdr tier + a noisy conceded-xG roll -> opp_xgc does NOT beat
    fdr, so the beats-fdr CI does not exclude 0 on the positive side (the real-mart outcome)."""
    panel = _panel(fdr_noise=0.15, xgc_noise=1.2)
    deltas = _beats_fdr_deltas(model_cls, panel)
    assert len(deltas) >= 4, "need >=4 paired cells for a meaningful bootstrap"
    lo, _ = block_bootstrap_ci(deltas, seed=0)
    assert lo <= 0, f"opp_xgc must not clear the beats-fdr bar here (a positive-significant CI), got lo={lo:.4f}"


@pytest.mark.parametrize("model_cls", [GoalsModel, AssistsModel])
def test_protocol_accepts_opp_xgc_when_it_is_genuinely_sharper(
    model_cls: type[PoissonPlayerComponentModel],
) -> None:
    """The discriminating control: a noisy fdr tier + a sharp conceded-xG roll -> opp_xgc genuinely beats
    fdr and the CI excludes 0 on the positive side — the machinery is not rigged to always reject."""
    panel = _panel(fdr_noise=1.6, xgc_noise=0.05)
    deltas = _beats_fdr_deltas(model_cls, panel)
    assert len(deltas) >= 4
    lo, hi = block_bootstrap_ci(deltas, seed=0)
    assert deltas.mean() > 0 and lo > 0, f"expected a significant positive delta, got mean={deltas.mean():.4f} CI=[{lo:.4f},{hi:.4f}]"  # noqa: E501


@pytest.mark.parametrize("pool", [GOALS_POOL, ASSISTS_POOL])
def test_opp_xgc_forward_not_in_pool_after_refutation(pool) -> None:
    """The shipping decision, pinned: opp_xgc_forward is NOT a candidate the selected model draws (it was
    measured and refuted), while the crude fdr_avg it lost to remains in the pool."""
    assert "opp_xgc_forward" not in pool.names
    assert "fdr_avg" in pool.names
