from __future__ import annotations

import math

from fpl_intelligence.context import GameweekContext

# PRE-TASK ELIGIBILITY AUDIT — findings recorded here as required:
#
# Occurrences of eligibility logic found in codebase:
#
# 1. steps.py — apply_minutes_filter (lines 222-239)
#    Condition : r.start_rate >= 0.75 → nailed
#                r.start_rate >= 0.40 → rotation
#                else                 → doubt
#    Field type: DERIVED (start_rate = starts_last_n / MINUTES_FILTER_LOOKBACK)
#    Raw field : starts_last_n  (SQL: SUM(ph.starts) over lookback window)
#
# 2. steps.py — compute_signals_base (lines 253, 257)
#    Condition : eligible = set(pool.nailed) | set(pool.rotation)
#                if r.entity_id not in eligible: continue
#    Field type: DERIVED (FilteredPool produced by apply_minutes_filter)
#    Effective  : start_rate >= 0.40  (rotation threshold = eligibility lower bound)
#
# Fields NOT found anywhere in the codebase:
#   - player["status"] checks (a, d, i, s, u) : NOT PRESENT
#   - chance_of_playing_next_round thresholds  : NOT PRESENT
#   - gw_context.is_bgw as an eligibility gate : NOT PRESENT
#
# CONFLICTS DETECTED:
#
# CONFLICT 1 — gw_context.is_bgw
#   Task spec mandates: if gw_context.is_bgw: return False
#   Current codebase  : no such check exists anywhere.
#   BGW players with start_rate >= 0.40 currently pass the eligibility gate.
#   Resolution        : strictest condition selected (task spec takes precedence).
#   Consequence       : for a BGW, new_eligible != old_eligible for any player
#   whose team has no fixture but whose historical start_rate >= 0.40.
#   The validation assertion in compute_features_batch skips BGW players
#   because this divergence is expected and documented here.
#
# No threshold mismatches between the two existing locations: both reduce to
# start_rate >= 0.40, confirmed by tracing apply_minutes_filter output into
# compute_signals_base.


def is_player_eligible(
    player: dict,
    gw_context: GameweekContext,
    min_minutes_lookback: int,
) -> bool:
    """
    Single authoritative eligibility function.
    Must replicate ALL existing eligibility logic exactly.
    No additions, no removals.

    Parameters
    ----------
    player:
        Dict with key ``minutes_lookback`` (float) — starts accumulated over the
        lookback window. Maps to PlayerMetrics.starts_last_n (SQL aggregate of
        ph.starts). Caller is responsible for populating this key.
    gw_context:
        Per-player GameweekContext from build_gameweek_context.
    min_minutes_lookback:
        Minimum starts in the lookback window for a player to be eligible.
        Caller derives this from the rotation threshold:
            math.ceil(ROTATION_THRESHOLD * MINUTES_FILTER_LOOKBACK)
        For ROTATION_THRESHOLD=0.40 and MINUTES_FILTER_LOOKBACK=6 this is 3.
    """
    # CONFLICT 1 (documented above): gw_context.is_bgw was not an existing rule.
    # Task spec mandates strictest condition: BGW players are always ineligible.
    if gw_context.is_bgw:
        return False

    # Replicates the start_rate >= 0.40 gate from apply_minutes_filter /
    # compute_signals_base, expressed in raw counts:
    #   starts_last_n / MINUTES_FILTER_LOOKBACK >= 0.40
    #   ⟺ starts_last_n >= 0.40 * MINUTES_FILTER_LOOKBACK  (= 2.4 for lookback=6)
    #   ⟺ starts_last_n >= min_minutes_lookback             (= 3, starts are integers)
    if player["minutes_lookback"] < min_minutes_lookback:
        return False

    return True
