# BGW team_id semantics

**Status:** Active  
**Date:** May 2026  
**Risk addressed:** SC-2  
**Implemented in:** `dal/curated/player_gameweek_spine.py` — `_apply_bgw_defaults`

---

## Context

When a player has a blank gameweek (no fixture), the curated layer inserts a BGW row with NULL performance values. One non-null column that must still be populated is `team_id` — downstream joins (team context, opponent context) need to know which club the player represented in that period.

The question is: which team_id should a BGW row carry?

The original implementation used `sort_values("gw", ascending=False).drop_duplicates("player_id", keep="first")` to build player info — this returned the player's team as of their **latest** GW, regardless of when the BGW occurred.

For a player who transfers clubs mid-season, this is wrong. If a player is at Team A in GWs 1–2, has a BGW in GW 3, and then transfers to Team B for GW 4 onwards, the pre-fix code assigns Team B's `team_id` to the GW 3 BGW row. That is temporally incorrect — the player was at Team A at the time of the BGW.

---

## Decision

BGW rows carry the player's team as of the **most recent non-BGW GW strictly before the BGW**.

This is the only temporally causal option. It uses only information that would have been available at the time of the BGW.

---

## Rationale

**Temporal causality is the core constraint.** The spine's temporal causality invariant requires that every value at `(player_id, gw)` is derivable from information available at or before that GW. A BGW in GW 3 occurs before the player transfers — the GW 3 row must not know about the transfer.

**The alternative (latest-known team) violates this.** Using the player's eventual team_id at the end of the season would mean a BGW row early in the season knows the player's future team. This is future leakage in team context joins. Any analysis using BGW rows to establish team context (e.g., opponent defensive strength) would be contaminated.

**The BGW row reflects the player's club at the time of the omission.** This is also the most analytically meaningful interpretation. The BGW happened while the player was at Team A — the analytical context (club's training schedule, fixture omission cause) is Team A's context.

---

## Alternatives considered

**Option 1 — Latest-known team (rejected):** Simple to implement (`drop_duplicates(keep="last")` equivalent). Wrong — violates temporal causality for transferred players. Prior implementation; replaced in Wave 1.

**Option 2 — NULL team_id for BGW rows (rejected):** Avoids the lookup complexity. Breaks every downstream join that references team_id on BGW rows. Not acceptable.

**Option 3 — team_id from the next non-BGW GW after the BGW (rejected):** Also temporally incorrect — uses future information (which team the player appeared for after the BGW). Discarded.

---

## Analytical consequences

- BGW rows for players who never transferred have identical behavior to before — no change.
- BGW rows for players who transferred clubs will carry a different `team_id` than the latest-GW approach when the BGW falls before the transfer GW.
- **Invalidated outputs:** All prior BGW `team_id` values for transferred players. Any analysis using BGW rows for team-context joins must be regenerated.

---

## Downstream implications

- `_build_player_info` must be called on non-BGW rows only. For each BGW row, `team_id` is resolved via a backward merge on the aggregated fixture data (most recent non-BGW GW at or before the BGW's GW).
- Any test asserting a specific `team_id` on a BGW row for a transferred player must use the pre-BGW team, not the post-BGW team.
- Lens studies that use team context for BGW analysis (e.g., "which club was the player at during their blank?") now get the temporally correct answer.
