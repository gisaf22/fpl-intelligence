"""Mean-features step-3 acceptance protocol, encoded as a test (goals + assists x team_xg_roll3).

`team_xg_roll3` — own-team attacking form (the sum of the team's xG, rolled over 3 games, broadcast to
the team's players) — was measured against the shipped `selected` design (own xG/xA rolls + fdr_avg) on
the real mart, walk-forward, and **REFUTED as a NULL** (docs/model-redesign-mean-features-plan.md step-3):

    goals   ADD team_xg on top of selected(+fdr): +0.0003, CI[-0.0013,+0.0021] (ns)
    assists                                     : -0.0008, CI[-0.0025,+0.0013] (ns)
    ... and ~0 even on a THIN base without the own xG/xA rolls (goals -0.0007 ns) — so it is not merely
    subsumed by own form; own-team recent attacking form carries no usable within-position ranking signal
    for attacking returns, at any position (per-position CIs all span 0). Removed from both pools.

The reason is structural: within a (gw, position) ranking cell `team_xg_roll3` is the SAME value for every
player on a team, so it can only separate players by which team they are on — and a player's own
involvement roll + `fdr` already carry that. (Defensive-side asymmetry — fixture context is ~10x more
valuable for clean sheets, but `fdr_avg` already holds it — is recorded in the plan doc, not here.)

The numeric verdict needs the private mart; here we pin (a) the shipping DECISION and (b) that the protocol
correctly returns "inconclusive" (CI spans 0) when a team-form feature is uninformative for the target —
the guard against shipping a null on a positive point estimate. The machinery's ability to ACCEPT a
genuinely predictive feature is already pinned in test_fdr_significance / test_opp_xgc_significance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.metrics import block_bootstrap_ci, cell_spearman, has_rank_signal
from model.eval.walkforward import MIN_ROWS_PER_POS, WARMUP_GW
from model.features.build import broadcast
from model.terms._poisson_component import PoissonPlayerComponentModel
from model.terms.assists import AssistsModel
from model.terms.assists.spec import ASSISTS_POOL
from model.terms.goals import GoalsModel
from model.terms.goals.spec import GOALS_POOL

pytestmark = pytest.mark.unit

_BASE = ["xgi_roll3", "minutes_roll3", "xgi_roll5"]


def _panel_team_form_is_noise(seed: int = 0, n_teams: int = 20, n_gw: int = 22) -> pd.DataFrame:
    """A panel where returns are driven by each player's OWN skill and team attacking form is uninformative.

    Each player has an independent skill; goals/assists ~ Poisson(skill). ``team_xg_roll3`` (the strictly-
    prior roll of the team's summed xG) is then a team-level variable with no relationship to an
    individual's within-cell rank — the null case the protocol must call inconclusive."""
    rng = np.random.default_rng(seed)
    players, pid = [], 0
    for team in range(n_teams):
        for pos, k in (("GK", 1), ("DEF", 4), ("MID", 4), ("FWD", 2)):
            for _ in range(k):
                players.append((pid, team, pos, rng.uniform(0.05, 0.55)))
                pid += 1
    rows = []
    for gw in range(1, n_gw + 1):
        for pl, team, pos, skill in players:
            rows.append({
                "player_id": pl, "team_id": team, "gw": gw, "position": pos, "minutes": 90,
                "is_dgw": False, "xg": max(0.0, skill + rng.normal(0, 0.1)),
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.04),
                "minutes_roll3": 90.0,
                "goals_scored": 0 if pos == "GK" else rng.poisson(skill),
                "assists": rng.poisson(skill * 0.6),
            })
    panel = pd.DataFrame(rows)
    # Materialize team_xg_roll3: sum of team xG per fixture, strictly-prior roll(3), broadcast on OWN team.
    team = (panel.groupby(["team_id", "gw"], as_index=False)["xg"].sum()
            .rename(columns={"xg": "txg"}).sort_values(["team_id", "gw"]))
    team["team_xg_roll3"] = team.groupby("team_id")["txg"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    bc = broadcast(panel[["team_id", "gw"]], team[["team_id", "gw", "team_xg_roll3"]], ["team_xg_roll3"])
    panel["team_xg_roll3"] = bc["team_xg_roll3"].to_numpy()
    lp = team.groupby("gw")["txg"].agg(["sum", "count"]).sort_index()
    panel["team_xg_roll3"] = panel["team_xg_roll3"].fillna(
        panel["gw"].map(lp["sum"].cumsum().shift(1) / lp["count"].cumsum().shift(1)))
    return panel


def _add_deltas(model_cls: type[PoissonPlayerComponentModel], panel: pd.DataFrame) -> np.ndarray:
    """Paired rho(base + team_xg) - rho(base) per (gw, position) cell, walk-forward (the shipping unit)."""
    target = model_cls.target
    pop = model_cls.population(panel)
    r_hi = model_cls(variant="selected", feature_override=[*_BASE, "team_xg_roll3"]).fit(panel).predictions
    r_lo = model_cls(variant="selected", feature_override=_BASE).fit(panel).predictions
    df = pop.copy()
    df["hi"], df["lo"] = r_hi.to_numpy(), r_lo.to_numpy()
    df = df[df["gw"] > WARMUP_GW].dropna(subset=["hi", "lo", target])
    df = df[df["position"].isin(model_cls.fit_positions)]
    deltas = []
    for _, g in df.groupby(["gw", "position"]):
        if has_rank_signal(g, "hi", target, MIN_ROWS_PER_POS) and has_rank_signal(g, "lo", target, MIN_ROWS_PER_POS):
            deltas.append(cell_spearman(g["hi"].to_numpy(), g[target].to_numpy())
                          - cell_spearman(g["lo"].to_numpy(), g[target].to_numpy()))
    return np.asarray(deltas, dtype=float)


@pytest.mark.parametrize("model_cls", [GoalsModel, AssistsModel])
def test_protocol_calls_uninformative_team_form_inconclusive(
    model_cls: type[PoissonPlayerComponentModel],
) -> None:
    """When own-team attacking form is uninformative for the target, adding team_xg_roll3 yields a
    delta CI that includes 0 — the protocol does not ship a null (the step-3 real-mart outcome)."""
    deltas = _add_deltas(model_cls, _panel_team_form_is_noise())
    assert len(deltas) >= 4, "need >=4 paired cells for a meaningful bootstrap"
    lo, hi = block_bootstrap_ci(deltas, seed=0)
    assert lo <= 0 <= hi, f"a null team-form feature must be inconclusive, got CI=[{lo:.4f},{hi:.4f}]"


@pytest.mark.parametrize("pool", [GOALS_POOL, ASSISTS_POOL])
def test_team_xg_roll3_not_in_pool_after_refutation(pool) -> None:
    """The shipping decision, pinned: team_xg_roll3 is NOT a candidate the selected model draws (measured
    null); the crude fdr_avg it could not beat remains in the pool."""
    assert "team_xg_roll3" not in pool.names
    assert "fdr_avg" in pool.names
