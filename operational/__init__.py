"""Operational composition root — the entry point above the layered libraries (ADR-012 §6).

This package holds the one component permitted to depend on **both** ``model`` (the forecast) and
``serve`` (the decision engine): it wires ``dal.load → assemble_forecast → merge → run_decision`` into a
runnable weekly recommendation. It sits **outside** the import-linter layer graph by design — the
layered packages cannot cross the ``model``↔``serve`` boundary (``serve↛model``, and ``model`` is below
``serve``), so the composition happens here, above them.

Public API
----------
run                    -- build the mart, forecast it, and write ranked recommendations for a GW
recommend_from_mart    -- the DB-free core: enrich a mart + run every decision + write outputs
enrich_with_forecast   -- merge the model forecast columns onto a mart (serve reads them as data)
"""

from operational.recommend import (
    DecisionRecommendations,
    enrich_with_forecast,
    recommend_from_mart,
    run,
)

__all__ = [
    "DecisionRecommendations",
    "enrich_with_forecast",
    "recommend_from_mart",
    "run",
]
