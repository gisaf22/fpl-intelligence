# STATE Layer Contract

**File:** `dal/state/player_gameweek_state.py`
**Input:** `player_gameweek_spine` — `(player_id, gw)` grain, 52 columns
**Output:** `player_gameweek_state` — same grain, same row count, +29 derived columns

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

29 derived columns appended to the 52 spine columns:

| Column pattern | Count | Causality | Warmup GWs |
|---|---|---|---|
| `{metric}_roll3` | 13 | lagged | 1 |
| `{metric}_roll5` | 13 | lagged | 1 |
| `minutes_roll8` | 1 | lagged | 1 |
| `minutes_trend` | 1 | lagged | 4 |
| `fixture_context` | 1 | contemporaneous | 0 |

Metrics (13): `points`, `minutes`, `xg`, `xgi`, `xgc`, `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `saves`, `penalties_saved`, `bonus`, `bps`

`xa` excluded: absorbed by `xgi` (G-EDA6-02; partial_rho MID=0.67, GK=0.99). `xa` is retained in the spine as raw FPL data.

`fixture_context` values: `"BGW"` | `"SGW"` | `"DGW"` — always non-null.
`minutes_trend` values: `"rising"` | `"stable"` | `"falling"` | null — null for first 4+ GWs.

Full causality, warmup, and reliability metadata is in `dal/state/contracts.py`.

---

## Column governance table

Every derived column is annotated with its scope (the attribution unit per the signal ontology), a one-sentence behavioral rationale, and a lifecycle state.

**lifecycle_state values:**
- `operational` — approved at one or more positions; no outstanding validation concerns
- `conditional` — approved with constraints (position-gated, pending lens study, or threshold undocumented)
- `rejected` — REJECTED-BEHAVIORAL or REJECTED-SEMANTIC; produced but must not be consumed by scoring or decision modules; removal scheduled in Phase 5 cleanup

---

### Outcome family

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `points_roll3` | Individual | rejected | Rolling mean of the target variable is analytically circular; uninformative or unstable at all positions | LENS-FORM FORM-004 |
| `points_roll5` | Individual | conditional | Informative at MID only (rho=0.157, 3/3 GW blocks); use as position-conditional evaluation baseline only — not an operational feature | LENS-FORM FORM-005 |

---

### Process family

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `xg_roll3` | Individual | rejected | xg is a component of xgi (partial_rho FWD=0.93, MID=0.74); absorbed by xgi at FWD and MID; additionally blocked at DEF, GK (G-EDA2-01) | G-EDA6-03 |
| `xg_roll5` | Individual | rejected | Same basis as xg_roll3 | G-EDA6-03 |
| `xgi_roll3` | Individual | conditional | APPROVED at DEF (rho=0.123, 3/3 blocks) and MID (rho=0.144, 3/3 blocks); CONDITIONAL at FWD — CI excludes zero but fails decision relevance (haul concentration suppresses Q5-Q1 gap) | LENS-FORM FORM-001 |
| `xgi_roll5` | Individual | conditional | APPROVED at DEF (rho=0.113, 3/3 blocks) and MID (rho=0.157, clears naive baseline, 3/3 blocks); CONDITIONAL at FWD — same haul concentration caveat as roll3 | LENS-FORM FORM-002 |
| `xgc_roll3` | Team | rejected | Redundant with goals_conceded + clean_sheets (partial_rho vs goals_conceded: −0.086; vs clean_sheets: −0.098 — both below 0.30 independence threshold); no independent information at any position | G-EDA8-05 |
| `xgc_roll5` | Team | rejected | Same basis as xgc_roll3 | G-EDA8-05 |

---

### Event family

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `goals_scored_roll3` | Individual | rejected | Rolling mean destroys episodic burst structure; uninformative at all positions (DEF CI crosses zero; MID and FWD fail decision relevance) | LENS-FORM FORM-003 |
| `goals_scored_roll5` | Individual | rejected | Longer window further dilutes rare haul events; rejected by extension from FORM-003 and sparsity rationale | LENS-FORM FORM-003 |
| `assists_roll3` | Individual | rejected | No assists variant clears naive baseline in lag-1 analysis (MID rho=0.051 vs naive 0.140); Q5-Q1 gaps near-zero and non-monotonic; xgi is the correct form proxy | G-EDA8-07/08/09 |
| `assists_roll5` | Individual | rejected | Same pattern as roll3 (MID rho=0.062, FWD rho=0.092 — both fail naive baseline); xgi subsumes the underlying attacking process | G-EDA8-07/08/09 |
| `clean_sheets_roll3` | Team | conditional | Semantically admissible (count type); CONDITIONAL pending lens study validation; xgc redundancy resolved (G-EDA8-05) confirms clean_sheets as the surviving defensive outcome signal; team-scope annotation required | EDA7-routing; G-EDA8-05 |
| `clean_sheets_roll5` | Team | conditional | Same status as clean_sheets_roll3 | EDA7-routing |
| `goals_conceded_roll3` | Team | conditional | Semantically admissible; CONDITIONAL pending lens study validation; moderate_shift at MID (G-EDA5) means seasonal drift risk applies to rolling variants at that position; team-scope annotation required | EDA7-routing |
| `goals_conceded_roll5` | Team | conditional | Same status as goals_conceded_roll3; MID moderate_shift risk applies | EDA7-routing |
| `saves_roll3` | Individual | rejected | Uninformative at GKP (rho=−0.029, CI crosses zero, 0/3 block stability); REJECTED-SEMANTIC at outfield (structural zero — GKP-only event) | G-EDA8-01; G-EDA2-03 |
| `saves_roll5` | Individual | rejected | Same basis as saves_roll3; Layer 1 failure at GKP rules out rolling window study | G-EDA8-02 |
| `penalties_saved_roll3` | Individual | rejected | Structurally sparse: 99.7% zero-rate across 2,512 GKP player-GW records (8 non-zero observations); rolling mean of near-constant zero is analytically meaningless | G-EDA8-06 |
| `penalties_saved_roll5` | Individual | rejected | Same basis as penalties_saved_roll3 | G-EDA8-06 |

---

### Participation family

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `minutes_roll3` | Individual | conditional | APPROVED at MID (rho=0.179, 3/3 GW blocks); uninformative at DEF, FWD, GK; availability signal only — blocked as form proxy (G-EDA2-02) | LENS-AVAIL AVAIL-001 |
| `minutes_roll5` | Individual | conditional | APPROVED at MID (rho=0.168, 3/3 GW blocks); unstable at FWD (1/3 blocks); availability signal only | LENS-AVAIL AVAIL-002 |
| `minutes_roll8` | Individual | operational | APPROVED at DEF (rho=0.130, 3/3 blocks) and MID (rho=0.169, 3/3 blocks); strongest availability window; uninformative at FWD and GK | LENS-AVAIL AVAIL-003 |
| `minutes_trend` | Individual | conditional | Directional availability trend; CONDITIONAL — 30-minute threshold is an editorial judgment without formal behavioral study (see §minutes_trend rationale below) | G-EDA2-02; Phase 4 |

---

### Allocation family

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `bonus_roll3` | Individual | rejected | Target leakage: bonus is a direct component of total_points; the high association (DEF/GK rho=0.54) is analytically circular; must not be consumed by any scoring or decision module | G-EDA7-06 |
| `bonus_roll5` | Individual | rejected | Same basis as bonus_roll3 | G-EDA7-06 |
| `bps_roll3` | Individual | rejected | Target leakage: bps is the input to bonus allocation which is a component of total_points; rho=0.91 at GK reflects the circular relationship; must not be consumed by any scoring or decision module | G-EDA7-06 |
| `bps_roll5` | Individual | rejected | Same basis as bps_roll3 | G-EDA7-06 |

---

### Context / fixture label

| Column | Signal scope | lifecycle_state | behavioral_why | Gate |
|---|---|---|---|---|
| `fixture_context` | Match | operational | Pre-match structural label (BGW/SGW/DGW) derived from `is_bgw` and `is_dgw` spine flags; contemporaneous; not a predictive feature; used to segment analyses by fixture type | Ontology |

---

## minutes_trend — threshold and window rationale

### 30-minute threshold

```python
diff = last3 - prior3  # difference of 3-GW rolling averages
trend[diff > 30] = "rising"
trend[diff < -30] = "falling"
trend[diff.abs() <= 30] = "stable"
```

The 30-minute threshold is an **editorial judgment**. No formal behavioral study establishes this value. Interpretation: a shift of 30 minutes between consecutive 3-GW average windows represents approximately one-third of a standard match and approximates the boundary between a significant substitute appearance and a near-full-match contribution in FPL context. The FPL appearance threshold is 60 minutes (for clean sheet credit and the 2-point appearance bonus); 30 minutes is half that boundary.

**No behavioral gate decision exists for this threshold.** The operational implication is that `minutes_trend` is `conditional` until either:
(a) a behavioral study establishes that 30 minutes produces better availability discrimination than alternatives, or
(b) the threshold is explicitly labeled as permanently editorial with no intent to replace it.

### Window overlap

```python
last3  = minutes_series.shift(1).rolling(3, min_periods=3).mean()   # GWs N-1, N-2, N-3
prior3 = minutes_series.shift(3).rolling(3, min_periods=3).mean()   # GWs N-3, N-4, N-5
```

GW N-3 appears in **both** windows. `last3` includes it as the oldest observation; `prior3` includes it as the newest. The overlap is **not corrected** — it is a conservative bias: when GW N-3 is an outlier, it pulls both averages in the same direction, dampening the measured diff and reducing false trend detections. This is acceptable behavior for an availability trend classifier. The warmup requirement (4+ non-null GWs) is unaffected by the overlap.

If strict non-overlapping windows are required in a future study, use `shift(4).rolling(3)` for `prior3` (spans GWs N-4, N-5, N-6; warmup increases to ~7 GWs).

---

## Runtime guards

`build_player_gameweek_state` raises on:
- **Schema leak:** any column in the output beyond `spine.columns ∪ expected_derived` → `RuntimeError`
- **Grain duplicate:** duplicate `(player_id, gw)` in output → `DALContractViolation`

BGW rows (NULL performance) are not zeroed — rolling windows skip NULLs via pandas default `skipna=True`. BGW rows contribute no performance signal to any rolling window.
