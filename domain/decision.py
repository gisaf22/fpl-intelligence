"""DecisionSpec — the contract a per-player ranking decision declares (ADR-012).

A decision (captain, value, transfers, …) is not a hand-written function; it *declares* its slots —
which forecast columns it needs, who is eligible, the objective to rank by, how ties break, and the
output projection — and defers the shared lifecycle (validation, gameweek slicing, eligibility,
within-position ranking, top-n projection) to :func:`serve.decision_engine.run_decision`.

This is the ontology half of ADR-012 (meaning → ``domain``); the engine and the concrete specs are
execution (→ ``serve``). ``domain`` imports nothing project-internal, so the spec is a pure contract —
its callables are supplied by the ``serve`` layer that constructs each spec.

Reserved, not yet fields (ADR-012 §3): forecast ``horizon`` (v1 is single-step / ``target_gw`` only,
per ADR-011's leak boundary), an ``evaluation`` binding, and squad-level objective/constraints (a
separate decision family, deliberately out of scope — ADR-012 §4).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DecisionSpec:
    """A per-player ranking decision, declared as data. The frozen field set is ADR-012 §2.

    Attributes
    ----------
    name:
        Stable identity; used as the caller label in input-contract errors.
    required_forecast_cols:
        The ``model.predictions.assemble_forecast`` columns the runner must have merged on before
        ranking. Missing any of them is a fail-closed input error.
    eligibility:
        ``(frame, **params) -> boolean Series`` — who is a candidate. ``params`` are the decision's
        optional filters (e.g. ``max_price``, ``position``).
    objective:
        ``(frame) -> Series`` — the score to rank by, descending. The decision's objective made
        explicit (ceiling vs mean vs per-cost).
    score_col / rank_col:
        Names under which the objective and the within-position rank are written.
    output_cols:
        The projection each recommendation carries (always includes the forecast reads it ranked by,
        for explainability).
    tie_break:
        Secondary sort keys, descending. Empty for single-key decisions.
    """

    name: str
    required_forecast_cols: tuple[str, ...]
    eligibility: Callable[..., pd.Series]
    objective: Callable[[pd.DataFrame], pd.Series]
    score_col: str
    rank_col: str
    output_cols: tuple[str, ...]
    tie_break: tuple[str, ...] = ()
