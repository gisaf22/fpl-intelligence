# Decision 006 — EDA-2 Signal Exclusions — Structural Zero and Constant Pairs

**Status:** LOCKED  
**Source:** EDA-2 (signal characterisation), GW6–33 primary population (minutes >= 60)  
**Applies to:** Signal registry, governed signal columns, registry build signal lists

---

## Summary

15 signal-position pairs are permanently excluded from association analysis. These are not
data quality issues — they are structural: either the signal cannot vary for that position
by construction, or the event is so rare that no meaningful distribution exists.

The registry encodes these as `relationship_geometry = "unassessable"` with
`downstream_status = "blocked"`. This document records *why* each pair is excluded,
which is not recoverable from the registry alone.

---

## Excluded pairs (15)

### Structural zeros — position-role mismatch

These signals are defined by role. The metric does not apply to the position.

| Signal | Position | Reason |
|---|---|---|
| `goals_scored` | GK | Structural zero. Goalkeepers do not score. std=0, CONSTANT. |
| `saves` | DEF | Structural zero. Only GKs make saves. std=0, CONSTANT. |
| `saves` | MID | Structural zero. Only GKs make saves. std=0, CONSTANT. |
| `saves` | FWD | Structural zero. Only GKs make saves. std=0, CONSTANT. |
| `penalties_saved` | DEF | Structural zero. GK-only stat. std=0, CONSTANT. |
| `penalties_saved` | MID | Structural zero. GK-only stat. std=0, CONSTANT. |
| `penalties_saved` | FWD | Structural zero. GK-only stat. std=0, CONSTANT. |

### Rarity zeros — event too rare to form a usable distribution

These signals exist for the position in principle but fire so infrequently that the
distribution is degenerate in the primary population (minutes >= 60).

| Signal | Position | Zero mass | Reason |
|---|---|---|---|
| `red_cards` | GK | ~100% | Red cards are rare across all positions; GKs almost never receive them in the filtered population. |
| `red_cards` | FWD | 99.6–100% | Same rarity issue. |
| `penalties_missed` | GK | ~100% | Goalkeepers rarely take penalties. std=0, CONSTANT. |
| `penalties_missed` | DEF | 98.8–100% | Event too rare. std=0, CONSTANT. |
| `in_dreamteam` | GK | 100% | Boolean flag; no variance in primary population. std=0, CONSTANT. |
| `in_dreamteam` | DEF | 100% | Same. |
| `in_dreamteam` | MID | 100% | Same. |
| `in_dreamteam` | FWD | 100% | Same. |

---

## Signals that survive with caveats

The following were flagged (not excluded) in EDA-2. They appear in the registry as
assessable but with `support_type` annotations where relevant.

- `red_cards × MID`, `red_cards × DEF` — extreme zero mass but not constant; included as
  discipline layer in `SIGNAL_LAYER_MAPPING`. The registry will classify these as
  `unassessable` or `blocked` based on actual support at build time.
- `xg × GK`, `assists × GK`, `threat × GK` — structural near-zeros (99.5–99.6%). Included
  in signal list but expected to be `blocked` in the registry for GK position.
- `fdr_min`, `fdr_max` — high redundancy with `fdr_avg` (rho 0.986–0.994 across all
  positions). Included but flagged; algebraic decomposition relationship documented in
  `core/signals/redundancy.py::ALGEBRAIC_DECOMPOSITIONS`.

---

## EDA-2 population summary

Candidate signals entering EDA-2: 34  
Surviving to registry (at least one position): all 34  
Pairs by constraint status:
  - KEEP (no structural constraint): 57 signal-position pairs
  - FLAG (structural caveat, not excluded): 64 signal-position pairs
  - EXCLUDE (constant or structural zero): 15 signal-position pairs
