# Starting XI — Stage 3 data mapping

Status and decisions: [`CARD.md`](CARD.md). This file is the Gate 2 (Data) answer for Stage 3,
for the warehouse path.

**Season:** 2025-26. Every read filters on `season`; no query relies on a table holding one season.

## Source

A pinned snapshot of one fpl-warehouse served publish, read by `warehouse.served` (#29). The pin
(`warehouse/pin.json`) names the publish's manifest `run_id` and each file's sha256, and the run
manifest records both. A run whose input hashes differ from its pin is refused.

## Mapping

| Need | Warehouse source | Rule |
|---|---|---|
| Points, minutes, starts per gameweek | `fct_player_gameweek` (`total_points`, `minutes`, `starts`) | The gameweek's sums over its fixtures (aggregation audited on [fpl-warehouse#164](https://github.com/gisaf22/fpl-warehouse/issues/164)); null on a blank, read as 0. |
| Appearances per gameweek | `fct_player_fixture` (`minutes`) | Fixtures with minutes > 0. Read only for this count, which summed minutes cannot give in a double; dropped when [fpl-warehouse#215](https://github.com/gisaf22/fpl-warehouse/issues/215) adds it to `fct_player_gameweek`. |
| Fixtures played in a gameweek | `fct_player_gameweek.fixture_count` | The realised count: 0 = blank, 2 = double. A unit of the past gameweeks a rate sums over; never the coming gameweek's multiplier. |
| Fixtures in the coming gameweek | `fct_player_gameweek.fixture_count_at_deadline` ([fpl-warehouse#221](https://github.com/gisaf22/fpl-warehouse/issues/221)), served as `deadline_fixture_count` | The club's fixtures as scheduled at the gameweek's deadline ([#59](https://github.com/gisaf22/fpl-intelligence/issues/59)). It is the rules' multiplier and the harness's no-fixture test. A gameweek with no count at the deadline for any player had no capture before its deadline: it takes the realised count and is flagged `deadline_count_is_realised` (today 2026-27 GW1–2 and all of 2025-26). A NULL in a gameweek that has counts is legitimate for a player not registered at the deadline; for a squad player the harness refuses it. |
| Entry gameweek | `fct_player_fixture` | The player's first gameweek with a fixture row. Earlier `fct_player_gameweek` rows are pre-entry (null, `fixture_count` 0), not blanks, and are dropped. |
| Position | `dim_player.position_id` | |
| Club per gameweek | `fct_player_fixture.team_fpl_id` | That gameweek's own rows. Club membership is fixed before the deadline, so this leaks no outcome. On a blank, carry the last known club forward. |
| Price (squad cost) | Per season — **2025-26:** `fct_player_gameweek.value` ÷ 10, the most recent non-null value strictly before gw; with none (GW1, a player's entry week), that gameweek's own value. **2026-27 onward:** the value as of each gameweek's deadline, from served `fct_player_market_snapshot` (exact). | The 2025-26 rule is a season-specific workaround, not the target rule: no pre-deadline snapshots exist for 2025-26. The as-of-deadline rule is the target; the loader does not implement it yet ([#49](https://github.com/gisaf22/fpl-intelligence/issues/49)). A blank's row is null, so the gameweek after a blank carries the last known price and the player stays pickable. The listing price is set before the deadline, so the own-week fallback leaks no outcome. NULL only when the player has no value at all. |
| Budget | — | £100.0m every gameweek. |
| Ownership weight | `selected`, by the same per-season rule as price: 2025-26 from `fct_player_gameweek` (workaround), 2026-27 onward as of the deadline from `fct_player_market_snapshot` | A realism assumption, read only alongside the uniform view. |
| Manager picks (Stage 5, #69) | `fct_manager_pick` (`entry_id`, `gameweek`, `slot`, `fpl_id`, `is_auto_sub_in`, `is_auto_sub_out`) | `warehouse.served.load_managers`: `entry_id` kept, `fpl_id` and `gameweek` renamed as elsewhere. `slot` is the lineup after FPL's automatic substitutions. |
| Manager chip per gameweek (Stage 5, #69) | `fct_manager_gameweek.active_chip` | Null means no chip. |

## Naming

Warehouse → harness: `fpl_id` → `player_id`, `gameweek` / `round` → `gw`, `team_fpl_id` → `team_id`.

## Verified

- **Club per gameweek:** for the 27 players who changed club in 2025-26, all 1,025 of their
  `fct_player_fixture` rows match the fixture's home/away teams and opponent — 0 mismatches.
- **Status history:** `dim_player_status_history` cannot be backfilled for 2025-26 (only an
  end-of-season snapshot exists), so it is not a source for this season.
