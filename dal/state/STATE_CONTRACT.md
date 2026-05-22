# STATE Layer Contract

**File:** `dal/state/player_gameweek_state.py`
**Input:** `player_gameweek_spine` — `(player_id, gw)` grain, 52 columns
**Output:** `player_gameweek_state` — same grain, same row count, +30 derived columns

---

## Purpose

The STATE layer derives analytical features from the curated spine. It does not change grain, add rows, remove rows, or join external data. Every output column is a function of prior GWs only (or current GW metadata for `fixture_context`).

---

## Ordering requirement

`build_player_gameweek_state` sorts by `(player_id, gw)` as its first operation. Callers are not required to pre-sort. Passing unsorted data is safe and produces identical output.

---

## Lagging convention

All rolling/trend features use a **lag-1 shift** before the rolling window:

```
df.groupby("player_id")[col].transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
```

At GW N, roll values reflect GWs 1..N-1 only. GW N performance is never included.

`minutes_trend` uses `shift(1)` for `last3` and `shift(3)` for `prior3` — both lag-1 by construction.

`fixture_context` is the one **contemporaneous** column: it labels the current GW's fixture structure (BGW/SGW/DGW) and is not a predictive feature.

---

## Deterministic guarantees

- Input row order does not affect output: sort is applied unconditionally.
- Grouped rolling is stable within each player because data is sorted before groupby.
- Same input → byte-identical output across repeated calls.

---

## Output schema

30 derived columns appended to the 52 spine columns:

| Column pattern | Count | Causality | Warmup GWs |
|---|---|---|---|
| `{metric}_roll3` | 14 | lagged | 1 |
| `{metric}_roll5` | 14 | lagged | 1 |
| `minutes_trend` | 1 | lagged | 4 |
| `fixture_context` | 1 | contemporaneous | 0 |

Metrics: `points`, `minutes`, `xg`, `xa`, `xgi`, `xgc`, `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `saves`, `penalties_saved`, `bonus`, `bps`

`fixture_context` values: `"BGW"` | `"SGW"` | `"DGW"` — always non-null.
`minutes_trend` values: `"rising"` | `"stable"` | `"falling"` | null — null for first 4+ GWs.

Full column-level metadata (causality, warmup, min_obs_for_reliability) is in `dal/state/contracts.py`.

---

## Runtime guards

`build_player_gameweek_state` raises on:
- **Schema leak:** any column in the output beyond `spine.columns ∪ expected_derived` → `RuntimeError`
- **Grain duplicate:** duplicate `(player_id, gw)` in output → `DALContractViolation`

BGW rows (NULL performance) are not zeroed — rolling windows skip NULLs via pandas default `skipna=True`. BGW rows contribute no performance signal to any rolling window.
