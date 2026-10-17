"""Decision backtesting — the operational binding of the serve ranker to the model/eval driver (ADR-012 §6).

The composition-root counterpart of ``recommend.py``: it injects the real ``serve`` ranker into the
serve-agnostic ``model/eval`` backtest driver. This is the one place that reaches both ``serve`` (the
rankers) and ``model`` (the driver + its ``kernels`` CI), so — like ``recommend`` — the binding lives
here, above the layer graph.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from model.eval.decision import (
    CAPTAIN_EVAL,
    TRANSFERS_EVAL,
    VALUE_EVAL,
    BacktestResult,
    EvalSpec,
    run_backtest,
)
from serve.captain import rank_captain_candidates
from serve.transfers import rank_transfer_targets
from serve.value import rank_value_players

# Spec name -> the serve ranker that produces its picks.
_RANKERS: dict[str, Callable[..., pd.DataFrame]] = {
    "captain": rank_captain_candidates,
    "value": rank_value_players,
    "transfers": rank_transfer_targets,
}

# The registered decisions available to backtest.
EVAL_SPECS: dict[str, EvalSpec] = {
    "captain": CAPTAIN_EVAL,
    "value": VALUE_EVAL,
    "transfers": TRANSFERS_EVAL,
}


def backtest_decision(spec: EvalSpec, features: pd.DataFrame, eval_gws: list[int]) -> BacktestResult:
    """Backtest ``spec`` over ``eval_gws``, injecting the matching serve ranker as the ``pick_fn``.

    ``features`` is the DAL mart enriched with the model forecast columns (as for recommendation), plus
    the actual ``total_points`` outcomes the backtest scores against.
    """
    ranker = _RANKERS[spec.name]

    def pick_fn(frame: pd.DataFrame, gw: int) -> pd.DataFrame:
        return ranker(frame, target_gw=gw, n=spec.n)

    return run_backtest(spec, features, eval_gws, pick_fn=pick_fn)
