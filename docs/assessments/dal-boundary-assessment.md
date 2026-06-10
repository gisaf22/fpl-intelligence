# DAL Boundary Assessment

**Date:** 2026-06-08
**Scope:** serve/, research/foundation/, research/families/, research/kernels/, model/
**Analyst role:** Principal Analytics Engineer — architectural ownership analysis

---

## Executive Summary

### Overall DAL Maturity

The DAL is well-structured. The combination of `dal/fct/validation/` (completeness, nulls, contracts, semantics, invariants), `dal/validation/grain.py`, `dal/mart/mart_schema.py` (fail-closed Pandera, grain uniqueness), and `dal/feat/feat_schema.py` (FEATURE_REGISTRY with typed nullability and warmup semantics) represents a mature, layered contract system. The majority of downstream defensive programming exists for legitimate analytical reasons (Category B/C) rather than as structural leakage.

### Net-new gaps vs duplicated logic vs legitimate downstream ownership

- **Net-new DAL gaps:** 2 (one meaningful, one low priority)
- **Category E — serve data repair:** 7 distinct `fillna()` call-sites across 4 files that substitute missing values which the DAL's own contracts should eliminate or the serve layer should reject rather than silently patch
- **Legitimate research ownership (Category B):** The majority of `dropna()` usage in research/ is pre-statistical computation; correctly owned
- **Legitimate model ownership (Category C):** All `dropna()` in model/assemble/ is before Spearman/bootstrap computation; correctly owned
- **Duplication of existing DAL capability:** 1 (snapshots dedup logic)

### Top 3 Findings by Architectural Impact

1. **`fixture_context.fillna("SGW")` in serve/ (captain.py, transfers.py) — Category E, High.** `fixture_context` is declared non-nullable in `dal/feat/feat_schema.py` and is unconditionally assigned in `dal/feat/feat_player_gameweek.py`. Its presence as a `fillna("SGW")` call in two serve files indicates the mart schema does not formally enforce non-nullability for this column at the serving boundary (`mart_schema.py` does not include `fixture_context` in `_NON_SIGNAL_COLUMNS` and the `_signal_columns()` function derives nullability from `FEATURE_REGISTRY` as `null_if_no_obs=False` → emits `nullable=False` in Pandera). However, the serve layer should not be silently defaulting — it should trust the schema or raise. This is a serve-side defensive habit that masks any upstream regression.

2. **`minutes_roll3/5/8.fillna(0)` used as eligibility gate in serve/ — Category E, High.** Rolling minutes signals are declared `nullable=True` with warmup semantics in `FEATURE_REGISTRY`. The serve layer uses `.fillna(0)` before the eligibility filter (`>= 30` or `>= 45` minutes). This is correct intent (warm-up rows should fail the eligibility gate), but expressing it as `fillna(0)` is a form of data repair — the DAL should provide a `is_warmup` boolean or the serve layer should filter `gw >= warmup_gws` explicitly so the intent is structural, not substitutional.

3. **`team_goals_roll5.fillna(0.5)` computed and filled in `serve/fixtures.py` — Category A, Medium.** Team attack strength (rolling goals_scored by team) is computed inside a serve-layer function from raw `goals_scored` with a neutral-fill fallback of 0.5. This is a derived team-level feature that belongs in `dal/feat/` alongside other rolling signals, with its nullability and warmup semantics registered in `FEATURE_REGISTRY`. Constructing and imputing it in serve/ mixes feature engineering with delivery.

---

## Findings Register

### Serve Layer

| Finding | File | Line(s) | Category | Current Owner | Recommended Owner | Priority |
|---|---|---|---|---|---|---|
| `minutes_roll3.fillna(0)` eligibility gate | serve/availability.py | 94–96 | E | serve | dal/feat (warmup flag) | High |
| `minutes_trend.fillna("")` | serve/availability.py | 97 | E | serve | dal/feat (minutes_trend is nullable=True by design; serve should guard not substitute) | Medium |
| `minutes_roll3.fillna(0)` eligibility gate | serve/captain.py | 94 | E | serve | dal/feat (warmup flag) | High |
| `fixture_context.fillna("SGW")` — DGW flag | serve/captain.py | 108 | E | serve | dal/mart (fixture_context must be non-null; mart_schema gap) | High |
| `minutes_roll5.fillna(0)` eligibility gate | serve/transfers.py | 102 | E | serve | dal/feat (warmup flag) | High |
| `xgi_roll3.fillna(0)` + `xgi_roll5.fillna(0)` before scoring | serve/transfers.py | 111–112 | E | serve | dal (FEATURE_REGISTRY warmup semantics; serve should zero governed-excluded positions without substituting NaN from warmup) | Medium |
| `fixture_context.fillna("SGW")` — DGW flag | serve/transfers.py | 125 | E | serve | dal/mart (same as captain.py) | High |
| `fdr_window_avg.fillna(_FDR_NEUTRAL)` post-left-join | serve/fixtures.py | 141–143 | E | serve | Legitimate join fallback (player not in window; neutral fill acceptable here) — see detail section | Low |
| `dgw_in_window.fillna(0)` post-left-join | serve/fixtures.py | 144 | E | serve | Same join-fallback pattern; acceptable | Low |
| `team_goals_roll5.fillna(0.5)` — team attack feature | serve/fixtures.py | 148 | A | serve | dal/feat (rolling team-level feature construction) | Medium |
| `purchase_price.fillna(0)` eligibility gate | serve/value.py | 97 | E | serve | dal/mart (purchase_price is `nullable=False` in mart_schema — DAL already guarantees non-null; fillna is dead code if mart is enforced) | Medium |
| `xgi_roll5.fillna(0)` + `xgi_roll3.fillna(0)` before scoring | serve/value.py | 107, 115–116 | E | serve | Same warmup semantics pattern as transfers.py | Medium |
| `normalize_within_position` internal `fillna(fill_value)` | serve/input_contracts.py | 62, 71 | C | serve | Legitimate model design — fills governed-excluded-position zeroes before normalization; not DAL leakage | — |
| `position.fillna(99)` sort key | serve/reporting/reports.py | 47–48 | D | serve | Legitimate presentation ordering; position and downstream_status are report-layer constructs, not DAL columns | — |
| `position.fillna(99)` sort key | serve/reporting/signal_intelligence.py | 183 | D | serve | Same as above | — |
| `dropna()` on promotion_class | serve/reporting/signal_intelligence.py | 169 | D | serve | Legitimate report aggregation; promotion_class is a model artifact | — |
| `drop_duplicates(key_columns)` in snapshot diff | serve/reporting/snapshots.py | 113–114 | Dup | serve | dal/validation/grain.py — grain uniqueness is already enforced at mart construction; dedup in snapshot diff is defensive code made redundant by mart_schema | Low |
| `directed.fillna(col_mean)` in scoring engine | serve/scoring/engine.py | 93 | C | serve | Legitimate model design — mean-imputation within position group before normalization; model choice, not DAL leak | — |

### Research Layer

| Finding | File | Category | Current Owner | Recommended Owner | Priority |
|---|---|---|---|---|---|
| `_assert_lag_alignment` — lag-1 target alignment check | research/families/form/validate/study.py:85–133 | B | research | research — this is a study construction integrity check, not a DAL structural check; it verifies that a study's derived target column (`total_points_next_gw`) correctly shifts from `total_points`. Not a DAL concern. | — |
| `check_rolling_windows` — rolling computation correctness | research/foundation/integrity/_integrity_helpers.py:50–115 | B | research | research — verifies that the DAL's rolling window algebra is correct by spot-checking derived values. This is EDA-0 study construction audit, not a duplicate of dal/fct/validation. | — |
| `check_lag_alignment` — lag alignment spot-check | research/foundation/integrity/_integrity_helpers.py:118–147 | B | research | research — analytical correctness audit for study methodology | — |
| `check_activity_filter_gate` — population stratification check | research/foundation/integrity/_integrity_helpers.py:150–173 | B | research | research — population scoping for study design; minutes >= 45 is a study inclusion threshold, not a DAL domain constraint | — |
| `select_verification_players` — player history completeness filter | research/foundation/integrity/_integrity_helpers.py:209–247 | B | research | research — selects players with complete GW histories for statistical verification; analytical selection, not a structural check | — |
| Missing columns guard in `profiling.py` | research/foundation/signals/profiling.py:43–46 | B | research | research — guards statistical computation entry; not a DAL schema check | — |

### Model Layer

| Finding | File | Category | Current Owner | Recommended Owner | Priority |
|---|---|---|---|---|---|
| `dropna()` before Spearman / bootstrap / partial rho | model/assemble/composition_study.py:149, 171, 197, 275 | C | model | model — pre-computation null removal for valid statistical pairs; correct ownership | — |

---

## Serve Layer Detail

### E-01 · `fixture_context.fillna("SGW")` — captain.py:108 and transfers.py:125

**Value being substituted:** `"SGW"` (single gameweek label)

**What DAL guarantee would eliminate it:** `fixture_context` is declared non-nullable in `dal/feat/feat_schema.py` (no `nullable=True`) and is assigned unconditionally in `dal/feat/feat_player_gameweek.py:110`. However, `mart_schema.py` derives nullability for signal columns from `FEATURE_REGISTRY` via `_signal_columns()`. `fixture_context` is in `FEATURE_REGISTRY` with `null_if_no_obs=False`, which the current `_signal_columns()` logic correctly maps to `nullable=False`. So the Pandera guarantee already exists — but the serve-side `fillna` was written before that guarantee was enforced and has not been removed. The fix is: remove the `.fillna("SGW")` and trust the contract. If the mart ever ships a null `fixture_context`, the Pandera schema will catch it at build time.

**Estimated effort:** S — delete two one-liner call-sites after confirming mart enforcement is active.

---

### E-02 · `minutes_roll3/5/8.fillna(0)` eligibility gates — availability.py:94–96, captain.py:94, transfers.py:102, fixtures.py:123, value.py:97

**Value being substituted:** `0` (treating warmup-period NaN as zero minutes)

**What DAL guarantee would eliminate it:** The rolling minutes signals are `nullable=True` with `warmup_gws=1` (roll3/5) or `warmup_gws=1, min_obs=8` (roll8) in `FEATURE_REGISTRY`. The NaN values are genuine warmup-period NaNs, not missing data errors. The serve layer is treating them as "zero minutes" to exclude early-season rows from eligibility sets. This is correct intent but achieved through substitution rather than structural filtering. The DAL could add a boolean `is_warmup_gw` column per player (True when `gw <= warmup_gws` for any governed signal) to `dal/feat/`, allowing serve to filter `~is_warmup_gw` explicitly. Alternatively, the existing `warmup_gws` field in `FEATURE_REGISTRY` could be surfaced in the mart for consumer use. Either approach makes the exclusion structural rather than substitutional.

**Estimated effort:** M — add `is_warmup_gw` boolean to `dal/feat/feat_player_gameweek.py`, register in `FEATURE_REGISTRY`, add to `mart_schema.py` non-signal columns; remove `fillna(0)` across five serve call-sites.

---

### E-03 · `minutes_trend.fillna("")` — availability.py:97

**Value being substituted:** `""` (empty string standing in for "no trend computed")

**What DAL guarantee would eliminate it:** `minutes_trend` is `nullable=True` with `warmup_gws=4, min_obs=6` in `FEATURE_REGISTRY`. It is legitimately null during warmup. The serve code fills with `""` to avoid comparison errors in `(trend == "falling")`. The correct fix is `(gw_df["minutes_trend"] == "falling")` which is already null-safe in pandas (comparison with `==` against a string returns `False` on NaN), making the `fillna` unnecessary. This is a serve-side defensive coding habit.

**Estimated effort:** S — remove `fillna("")`, verify the `== "falling"` comparison is used directly.

---

### E-04 · `xgi_roll3.fillna(0)` + `xgi_roll5.fillna(0)` before position-gated scoring — transfers.py:111–112, value.py:107, 115–116

**Value being substituted:** `0` before `.where(~position_mask, 0.0)` — effectively zeroing all rows, then masking by position

**What DAL guarantee would eliminate it:** These fills precede `.where(~fwd_mask, 0.0)` calls that zero out governed-excluded positions. The `fillna(0)` is thus redundant when the `.where` clause already sets the excluded-position rows to zero. The remaining use case is warmup-period NaN rows for non-excluded positions, which is the same pattern as E-02. Resolved the same way: structural `~is_warmup_gw` filter before eligibility, making the `fillna` unnecessary.

**Estimated effort:** S — follows from E-02 fix; remove `fillna(0)` once warmup rows are filtered upstream.

---

### E-05 · `purchase_price.fillna(0)` — value.py:97

**Value being substituted:** `0`

**What DAL guarantee would eliminate it:** `purchase_price` is declared `nullable=False, checks=pa.Check.ge(0)` in `mart_schema.py`. The DAL already guarantees this column is non-null at the serving boundary. The `fillna(0)` is dead code if mart enforcement is active. It should be removed.

**Estimated effort:** S — delete one call-site.

---

### E-06 · `fdr_window_avg.fillna(_FDR_NEUTRAL)` and `dgw_in_window.fillna(0)` — fixtures.py:141–144

**Value being substituted:** `_FDR_NEUTRAL = 3.0` and `0`

**Classification revision:** These fills occur after a `left` merge on `player_id` between eligible players and a `fdr_summary` aggregation of window GWs. A player present at `target_gw` but absent from the forward window (e.g., no scheduled fixture data) will have NaN post-merge. This is a legitimate join fallback — the DAL does not own forward-window aggregations (those are computed at serve time). The neutral fill is therefore an acceptable presentation default. **Not a true Category E finding** — reclassify as Category D. Noted here for completeness.

**Estimated effort:** N/A — no action required.

---

## DAL Capability Gaps

Only net-new capabilities not already in the DAL.

### Completeness

**GAP-C-01: `is_warmup_gw` boolean signal in `dal/feat/`**

- **What:** A per-(player_id, gw) boolean flag indicating the row falls within the warmup period of the most restrictive rolling signal that applies to the player's position. Could be derived mechanically from `FEATURE_REGISTRY.warmup_gws` values.
- **Why needed:** Eliminates E-02, E-03 (partially), E-04 `fillna(0)` patterns across five serve call-sites without requiring serve consumers to know warmup semantics.
- **Proposed location:** `dal/feat/feat_player_gameweek.py`, registered in `FEATURE_REGISTRY` with `null_if_no_obs=False`, added to `mart_schema.py` `_NON_SIGNAL_COLUMNS`.
- **Effort:** M

### State Integrity

**GAP-S-01: `team_goals_roll5` team-level rolling attack signal in `dal/feat/`**

- **What:** Per-(team_id, gw) rolling 5-GW mean of `goals_scored`, built and normalised at feat construction time, joined to the player mart at build time.
- **Why needed:** Eliminates the feature-construction code (`_build_team_attack_strength`) from `serve/fixtures.py` and its accompanying `fillna(0.5)` fallback, moving team attack feature ownership to the correct layer.
- **Proposed location:** `dal/feat/feat_team_gameweek.py` (new), joined into main feat build, registered in `FEATURE_REGISTRY`.
- **Effort:** M

---

## Recommended Roadmap

### Phase 1 — Serve layer: eliminate data repair `fillna()` calls (High-priority only)

Target files: `serve/captain.py`, `serve/transfers.py`, `serve/availability.py`, `serve/value.py`

1. **Remove `fixture_context.fillna("SGW")`** in `serve/captain.py:108` and `serve/transfers.py:125`. Verify that `mart_schema.py` enforces `fixture_context` non-nullability at mart build time (it does, via `FEATURE_REGISTRY` → `_signal_columns()`). No DAL change needed — serve-side removal only.

2. **Remove `purchase_price.fillna(0)`** in `serve/value.py:97`. `mart_schema.py` already declares `purchase_price` as `nullable=False`. Dead code removal.

3. **Remove `minutes_trend.fillna("")`** in `serve/availability.py:97`. Replace with direct `== "falling"` comparison (null-safe in pandas). No DAL change needed.

4. **Add `is_warmup_gw` to DAL feat** (GAP-C-01). Once shipped, remove `minutes_roll*/fillna(0)` eligibility gate pattern from `serve/availability.py`, `serve/captain.py`, `serve/transfers.py`, `serve/fixtures.py`, and `serve/value.py`.

### Phase 2 — Research foundation: no action required

The research/foundation/ integrity checks (`_integrity_helpers.py`, `_assert_lag_alignment` in form/validate/study.py) are correctly owned as EDA-0 study construction audits. They are not duplicating DAL structural checks — they are verifying the DAL's rolling window algebra is correct from an analytical correctness standpoint. Retain as-is.

### Phase 3 — Cleanup: move team attack feature to DAL feat

1. **Implement GAP-S-01** (`team_goals_roll5` in `dal/feat/feat_team_gameweek.py`). Register in `FEATURE_REGISTRY` with `warmup_gws=5, null_if_no_obs=True`.

2. **Remove `_build_team_attack_strength`** from `serve/fixtures.py` and replace with a direct column reference from the mart.

3. **Review `serve/reporting/snapshots.py:113–114`** `drop_duplicates` calls. Once confirmed that the mart grain uniqueness guarantee (enforced by `dal/validation/grain.py` + `mart_schema.py`) is reliable end-to-end, remove defensive dedup. Low priority.

---

## Summary of Category E Findings by Serve File

| File | fillna calls | Actionable (E) | Notes |
|---|---|---|---|
| serve/availability.py | 4 | 4 | minutes_roll3/5/8 warmup zeros; minutes_trend empty string |
| serve/captain.py | 2 | 2 | minutes_roll3 warmup zero; fixture_context SGW default |
| serve/transfers.py | 4 | 4 | minutes_roll5 warmup zero; xgi zeros; fixture_context SGW default |
| serve/fixtures.py | 4 | 1 | team_goals_roll5 fallback (Category A); fdr/dgw post-join fills are Category D |
| serve/value.py | 5 | 4 | purchase_price zero (dead code); xgi zeros; minutes_roll5 warmup zero |
| serve/scoring/engine.py | 1 | 0 | Mean imputation within position — Category C (model design) |
| serve/input_contracts.py | 2 | 0 | Normalization utility fill — Category C (model design) |
| serve/reporting/*.py | 3 | 0 | Sort-key ordinals and join-fallback — Category D |
