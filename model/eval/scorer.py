"""The single reusable ranking gate - within-position Spearman WITH a block-bootstrap CI + coverage.

Every phase's model-vs-baseline comparison routes through :func:`score_gate` instead of hand-rolling a
``for pos in POSITIONS: grouped_spearman(...)`` loop. This bakes in three things the hand-rolled gates
lacked: a **confidence interval** on every estimate (block bootstrap over the per-gameweek series -
one season is thin, so error bars are mandatory), a **coverage** figure (share of candidate rows the
prediction is even defined on - abstention made visible), and a consistent typed result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from model.eval.metrics import spearman_with_ci
from model.eval.walkforward import MIN_ROWS_PER_POS, POSITIONS


@dataclass(frozen=True)
class GateResult:
    """One within-position gate cell: the ranking estimate, its CI, coverage, and support."""

    position: str
    model: str
    spearman: float
    ci_lo: float
    ci_hi: float
    n_gw: int
    coverage: float


def score_gate(candidates: pd.DataFrame, pred_col: str, model: str,
               target_col: str = "total_points", *, min_n: int = MIN_ROWS_PER_POS,
               positions: tuple[str, ...] = POSITIONS, seed: int = 0) -> pd.DataFrame:
    """Within-position Spearman + block-bootstrap CI + coverage for one prediction column.

    ``candidates`` is the common evaluation set (the rows a fair comparison scores on); ``coverage`` is
    the share of a position's candidate rows on which ``pred_col`` is defined (abstention = 1 - coverage).
    The Spearman is computed on the defined rows only, so it matches a hand-rolled ``grouped_spearman``
    on the same set - the CI and coverage are purely additive. Returns a frame of :class:`GateResult`.
    """
    rows = []
    for pos in positions:
        sub = candidates[candidates["position"] == pos]
        if sub.empty:
            continue
        scored = sub.dropna(subset=[pred_col, target_col])
        if scored.empty:
            continue
        est, (lo, hi) = spearman_with_ci(scored, pred_col, target_col, ["gw"], min_n, seed=seed)
        rows.append(GateResult(
            position=pos, model=model, spearman=round(est, 4),
            ci_lo=round(lo, 4), ci_hi=round(hi, 4),
            n_gw=int(scored["gw"].nunique()), coverage=round(len(scored) / len(sub), 3),
        ))
    out = pd.DataFrame([asdict(r) for r in rows])
    if not out.empty:
        out["position"] = pd.Categorical(out["position"], categories=positions, ordered=True)
    return out


def score_gates(candidates: pd.DataFrame, models: dict[str, str], **kwargs) -> pd.DataFrame:
    """Score several prediction columns on the same candidate set. ``models`` = {pred_col: label}.

    Returns the stacked per-(position, model) gate table, sorted by position then Spearman desc -
    the drop-in replacement for a phase's hand-rolled multi-bar gate loop.
    """
    parts = [score_gate(candidates, col, label, **kwargs) for col, label in models.items()]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=["position", "model", "spearman", "ci_lo", "ci_hi", "n_gw", "coverage"])
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["position", "spearman"], ascending=[True, False]).reset_index(drop=True)
