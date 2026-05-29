"""Feature DAL datasets — rolling windows and derived state variables at (player_id, gw) grain."""

from dal.feat.feat_player_gameweek import build_player_gameweek_state

__all__ = [
    "build_player_gameweek_state",
]
