"""The mean-features step-1 acceptance protocol, encoded as a test (goals + assists x fdr_avg).

`fdr_avg` was added to the goals/assists `selected` designs only because it cleared this protocol
out of sample on the real mart (docs/model-redesign-mean-features-plan.md, step 1):

    RANKING (significant, not eyeball): fit `selected` with and without the feature walk-forward;
      form the *paired* per-(gw, position) within-cell Spearman delta (rho_with - rho_without) over the
      cells the shared coefficient is estimated on, and block-bootstrap its mean. Accept iff the 95%
      CI EXCLUDES 0 on the positive side. A positive-but-insignificant delta is INCONCLUSIVE → drop.
    LEVEL (no regression): `position_bias` on the with-feature predictions shows no new material
      per-position mean bias.

Measured on the shipped mart (recorded in the specs): goals pooled Δρ +0.0106, CI [+0.0039, +0.0186];
assists pooled Δρ +0.0151, CI [+0.0010, +0.0296]. `was_home` failed the same protocol (CI spans 0)
and was dropped. That measurement needs the private mart, so here the *protocol machinery* is pinned
on synthetic panels: it must ACCEPT a genuinely predictive fdr and REJECT a noise fdr — the guard that
keeps a positive-but-insignificant point estimate from shipping as if it were a result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.metrics import block_bootstrap_ci, cell_spearman, has_rank_signal, position_bias
from model.eval.walkforward import MIN_ROWS_PER_POS, WARMUP_GW
from model.terms._poisson_component import PoissonPlayerComponentModel
from model.terms.assists import AssistsModel
from model.terms.assists.spec import ASSISTS_POOL
from model.terms.goals import GoalsModel
from model.terms.goals.spec import GOALS_POOL

pytestmark = pytest.mark.unit

# The `selected` base on the real mart today (xg/xa rolls are materialized there); the synthetic panels
# below carry the mechanistic columns, so the base reduces to these three and fdr_avg is the one addition.
_BASE = ["xgi_roll3", "minutes_roll3", "xgi_roll5"]


def _panel(fdr_effect: float, seed: int = 0, n_teams: int = 24, n_gw: int = 22) -> pd.DataFrame:
    """A player-GW panel. ``fdr_effect`` scales how much the (known-future) fixture difficulty depresses
    the scoring/creation rate: >0 makes fdr_avg genuinely predictive, 0 makes it pure noise. goals and
    assists share the fixture so a single panel exercises both terms."""
    rng = np.random.default_rng(seed)
    players, pid = [], 0
    for team in range(n_teams):
        for pos, k in (("GK", 1), ("DEF", 4), ("MID", 4), ("FWD", 2)):
            for _ in range(k):
                players.append((pid, team, pos, rng.uniform(0.05, 0.55)))
                pid += 1
    rows = []
    for gw in range(1, n_gw + 1):
        fdr_by_team = {t: float(rng.integers(2, 6)) for t in range(n_teams)}  # known-future, per fixture
        for pl, team, pos, skill in players:
            fdr = fdr_by_team[team]
            mult = max(0.001, 1.5 - fdr_effect * (fdr - 2))
            a_lam = skill * 0.6 * mult
            rows.append({
                "player_id": pl, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.04),
                "minutes_roll3": 90.0, "fdr_avg": fdr,
                # keepers do not score (goals is structurally degenerate at GK — it emits 0 there),
                # so leave GK goals at 0; otherwise a spurious GK goal would read as a level-gate bias.
                "goals_scored": 0 if pos == "GK" else rng.poisson(skill * mult),
                "assists": rng.poisson(a_lam),
            })
    return pd.DataFrame(rows)


def _paired_delta_series(model_cls: type[PoissonPlayerComponentModel], panel: pd.DataFrame) -> np.ndarray:
    """rho_with - rho_without per (gw, position) cell, walk-forward — the significance unit for the shared
    fdr_avg coefficient (matches ``diagnose()``'s by=[gw, position] scoring)."""
    target = model_cls.target
    pop = model_cls.population(panel)
    p_wo = model_cls(variant="selected", feature_override=_BASE).fit(panel).predictions
    p_wi = model_cls(variant="selected", feature_override=[*_BASE, "fdr_avg"]).fit(panel).predictions
    df = pop.copy()
    df["wo"], df["wi"] = p_wo.to_numpy(), p_wi.to_numpy()
    df = df[(df["gw"] > WARMUP_GW)].dropna(subset=["wo", "wi", target])
    df = df[df["position"].isin(model_cls.fit_positions)]
    deltas = []
    for _, g in df.groupby(["gw", "position"]):
        if has_rank_signal(g, "wo", target, MIN_ROWS_PER_POS) and has_rank_signal(g, "wi", target, MIN_ROWS_PER_POS):
            deltas.append(cell_spearman(g["wi"].to_numpy(), g[target].to_numpy())
                          - cell_spearman(g["wo"].to_numpy(), g[target].to_numpy()))
    return np.asarray(deltas, dtype=float)


def _level_ok(model_cls: type[PoissonPlayerComponentModel], panel: pd.DataFrame) -> bool:
    """No new material per-position bias from the with-fdr predictions (the level gate)."""
    target = model_cls.target
    pop = model_cls.population(panel)
    pop["wi"] = model_cls(variant="selected", feature_override=[*_BASE, "fdr_avg"]).fit(panel).predictions.to_numpy()
    ev = pop[(pop["gw"] > WARMUP_GW)].dropna(subset=["wi", target])
    return bool(position_bias(ev, "wi", target)["ok"].all())


@pytest.mark.parametrize("model_cls", [GoalsModel, AssistsModel])
def test_protocol_accepts_a_genuinely_predictive_fdr(model_cls: type[PoissonPlayerComponentModel]) -> None:
    """When fdr_avg truly depresses the rate, the paired block-bootstrap CI excludes 0 (ACCEPT) and the
    level gate holds — the signal that justified shipping fdr_avg into `selected`."""
    panel = _panel(fdr_effect=0.18)
    deltas = _paired_delta_series(model_cls, panel)
    assert len(deltas) >= 4, "need >=4 paired cells for a meaningful bootstrap (else inconclusive)"
    lo, hi = block_bootstrap_ci(deltas, seed=0)
    assert deltas.mean() > 0 and lo > 0, f"expected a significant positive delta, got mean={deltas.mean():.4f} CI=[{lo:.4f},{hi:.4f}]"  # noqa: E501
    assert _level_ok(model_cls, panel)


@pytest.mark.parametrize("model_cls", [GoalsModel, AssistsModel])
def test_protocol_rejects_a_noise_fdr(model_cls: type[PoissonPlayerComponentModel]) -> None:
    """The anti-noise guard: when fdr_avg is uncorrelated with the target, the CI must INCLUDE 0 — the
    protocol does not ship a positive-but-insignificant point estimate as a result (the was_home case)."""
    deltas = _paired_delta_series(model_cls, _panel(fdr_effect=0.0))
    lo, hi = block_bootstrap_ci(deltas, seed=0)
    assert lo <= 0 <= hi, f"a noise feature must be inconclusive, got CI=[{lo:.4f},{hi:.4f}]"


@pytest.mark.parametrize("pool", [GOALS_POOL, ASSISTS_POOL])
def test_fdr_avg_shipped_in_selected_pool_as_known_future(pool) -> None:
    """The shipping decision, pinned: fdr_avg is a candidate the selected model draws, declared as a
    known-future (not leaked) fixture feature — the same footing as team_goals_against's fdr_avg."""
    spec = pool.spec("fdr_avg")
    assert spec.known_future is True and spec.lag_safe is True
    assert "fdr_avg" not in pool.minimal  # context enters `selected` only; the mechanistic bar is untouched
