"""Serve-agnostic decision evaluation (ADR-012 §5; §6 amended).

The decision backtest lives here (beside the forecast walk-forward) and draws its CI from
``research.kernels``. It is handed the ranker as an injected ``pick_fn`` — it never imports ``serve`` —
so the ``operational`` composition root binds the real ranker in.
"""

from model.eval.decision.backtest import BacktestResult, run_backtest
from model.eval.decision.spec import CAPTAIN_EVAL, TRANSFERS_EVAL, VALUE_EVAL, EvalSpec

__all__ = [
    "CAPTAIN_EVAL",
    "TRANSFERS_EVAL",
    "VALUE_EVAL",
    "BacktestResult",
    "EvalSpec",
    "run_backtest",
]
