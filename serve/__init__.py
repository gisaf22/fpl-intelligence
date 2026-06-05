"""Operational intelligence layer — FPL decision-support outputs.

Produces deterministic, explainable decision-support artifacts from trusted
DAL state features. All outputs consume governed operational inputs only.

Public API
----------
rank_captain_candidates   -- ranked captain options for a target gameweek
rank_transfer_targets     -- strong incoming transfer candidates
rank_value_players        -- high return-per-cost players
flag_availability_risk    -- minutes stability and availability warnings
rank_fixture_opportunities -- favorable near-term fixture windows

All functions accept a features DataFrame produced by:
    from dal.pipeline import load as load_mart
    features = load_mart().mart

See docs/operational-intelligence.md for design rationale and limitations.
"""

from serve.availability import flag_availability_risk
from serve.captain import rank_captain_candidates
from serve.fixtures import rank_fixture_opportunities
from serve.transfers import rank_transfer_targets
from serve.value import rank_value_players

__all__ = [
    "flag_availability_risk",
    "rank_captain_candidates",
    "rank_fixture_opportunities",
    "rank_transfer_targets",
    "rank_value_players",
]
