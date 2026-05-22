# Decision 004 — Team identity resolution via fixture_id join

Status: PINNED

Date: 2026-04-26

---

## Context

The FPL API `players.team` field is a current-state snapshot.
It reflects the player's club at ingest time, not at each
historical GW. 65 players were found with wrong `team_id` in
at least one GW — 14 summer transfers (GW1–3), 13 January
transfers (GW19–24), 32 false positives from a diagnostic
artifact (GW26 duplicate away fixture). Loan moves (Igor,
West Ham GW4–23) are invisible to `team_join_date`.

---

## Decision

Overwrite `team_id` in place during `get_player_gw_analytics()`.
Derive true team from `fixture_id` join to fixtures table.
`was_home=True` → `home_team_id`. `was_home=False` → `away_team_id`.
Log discrepancies — one line per player, not per row.
Preserve original value where `fixture_id` join fails.
Drop intermediate columns before returning.
Output column contract unchanged — `team_id` remains, now correct.

---

## Alternatives considered

1. Resolve in `staging.py` — rejected. `stage()` is pure select,
   rename, cast, transform. Derivation requiring a cross-entity
   join does not belong in the staging engine.
2. New utils module — rejected. Logic is specific to
   `get_player_gw_analytics()`. No other consumer needs it
   independently.
3. Separate `true_team_id` column — rejected. Silent in-place
   correction is cleaner. Consumers should get the right value
   without needing to know a correction happened.

---

## Consequences

All downstream team-level groupings are now correct for
transferred and loaned players. `get_opponent_context()` groupings
fixed automatically — no changes required there. SC results
stable on corrected data (zero top-signal rho shift > 0.005).
75 tests passing. `team_join_date` and `code` added to players schema
as part of the same investigation.
