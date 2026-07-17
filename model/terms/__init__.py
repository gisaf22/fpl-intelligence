"""One self-contained model per scoring term (spec §2, §3).

A ``Model`` is the fittable unit (one folder); a ``Term`` is a scored view it emits. Usually one
model emits one term, but joint models fit once and emit several (``team_goals_against`` →
``clean_sheet`` + ``conceded``). ``compose``/``simulate`` iterate the term registry and pull each
term's model output — adding a term is adding a folder, never editing a god-file.
"""

from __future__ import annotations

from model.terms._base import (
    AssumptionReport,
    Diagnostics,
    Fitted,
    GateResult,
    Hypothesis,
    Model,
    Term,
)

__all__ = [
    "AssumptionReport",
    "Diagnostics",
    "Fitted",
    "GateResult",
    "Hypothesis",
    "Model",
    "Term",
]
