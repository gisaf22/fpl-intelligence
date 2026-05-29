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
    staged   = load_staged_entities(db_path)
    spine    = build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)
    features = build_player_gameweek_state(spine)

See docs/operational-intelligence.md for design rationale and limitations.
"""

from intelligence.availability import flag_availability_risk
from intelligence.captain import rank_captain_candidates
from intelligence.fixtures import rank_fixture_opportunities
from intelligence.transfers import rank_transfer_targets
from intelligence.value import rank_value_players

__all__ = [
    "rank_captain_candidates",
    "rank_transfer_targets",
    "rank_value_players",
    "flag_availability_risk",
    "rank_fixture_opportunities",
]
