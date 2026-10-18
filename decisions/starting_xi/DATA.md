# Starting XI — Stage 3 data mapping

Status and decisions: [`CARD.md`](CARD.md). This file is the Gate 2 (Data) answer for Stage 3.
It supersedes, for the warehouse path, the local-mart column assumptions in
[`archive/INVENTORY.md`](archive/INVENTORY.md) §2.1, §2.2, §2.5 and §2.7, and the measurements in
[`archive/METRIC.md`](archive/METRIC.md) Appendix A.

**Season:** 2025-26. Every read filters on `season`; no query relies on a table holding one season.

## Source

fpl-warehouse served parquet, read from a path recorded in the run manifest together with its
sha256. A run whose input hash differs from its manifest is a different run.

## Mapping

| Need | Warehouse source | Rule |
|---|---|---|
| Points, minutes, starts per match | `fct_player_fixture` (`total_points`, `minutes`, `starts`) | Per-fixture rows; gameweek totals are their sum (aggregation audited on [fpl-warehouse#164](https://github.com/gisaf22/fpl-warehouse/issues/164)). |
| Fixtures in the coming gameweek | `fct_player_gameweek.fixture_count` | 0 = blank, 2 = double. |
| Entry gameweek | `fct_player_gameweek` | The player's first gameweek with a non-null row. |
| Position | `dim_player.position_id` | |
| Club per gameweek | `fct_player_fixture.team_fpl_id` | That gameweek's own rows. Club membership is fixed before the deadline, so this leaks no outcome. On a blank, carry the last known club forward. |
| Price (squad cost) | `fct_player_gameweek.value` at gw − 1, ÷ 10 | Lag 1: the deadline price is not served for 2025-26. |
| Budget | — | £100.0m every gameweek. |
| Ownership weight | `fct_player_gameweek.selected` at gw − 1 | Lag 1; GW1 is uniform. A realism assumption, read only alongside the uniform view. |

## Naming

Warehouse → harness: `fpl_id` → `player_id`, `gameweek` / `round` → `gw`, `team_fpl_id` → `team_id`.

## Verified

- **Club per gameweek:** for the 27 players who changed club in 2025-26, all 1,025 of their
  `fct_player_fixture` rows match the fixture's home/away teams and opponent — 0 mismatches.
- **Status history:** `dim_player_status_history` cannot be backfilled for 2025-26 (only an
  end-of-season snapshot exists), so it is not a source for this season.
