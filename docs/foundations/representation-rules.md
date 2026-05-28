# Representation Rules

**Status:** ACTIVE
**Version:** 1.0
**Produced:** 2026-05-24
**Scope:** Per-signal-family rules governing allowed and forbidden representations in STATE
**Governance framework:** `docs/foundations/representation-governance.md`
**Behavior profiles:** `docs/foundations/signal-behavior-profiles.yaml`
**Gate decisions source:** `studies/eda/findings/EDA_FINDINGS.md`

---

## How to read this document

Each family section contains:
1. **Family rule** — the admissibility constraint that applies to all signals in the family by ontology classification
2. **Per-signal entries** — allowed, conditional, and forbidden representations, each citing the gate decision that produced the ruling
3. **Scope annotations** — what metadata the STATE column must carry

Outcome codes follow the decision matrix in `representation-governance.md §5`:
- **APPROVED** — materialized in STATE; may proceed to evaluation
- **CONDITIONAL** — approved with constraints; boundary stated; usage outside boundary is REJECTED-BEHAVIORAL
- **REJECTED-SEMANTIC** — transform violates temporal type or family classification; hard stop regardless of EDA
- **REJECTED-BEHAVIORAL** — admissible but EDA evidence does not support the transform

All STATE columns must carry `_COLUMN_META` with `scope`, `temporal_type`, `causality`, `behavioral_reason`, `source_gate_decisions`, and `leakage_risk` (where applicable) per governance §7.

---

## 1. Event family

**Signals:** `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `saves`, `penalties_saved`
**Temporal type:** count
**Scope:** Individual (goals_scored, assists, saves, penalties_saved); Team (clean_sheets, goals_conceded)

### Family rule

Rolling mean is semantically admissible for count signals. Application requires behavioral
justification from EDA per-signal. Sparsity is the primary risk: rolling mean applied to a
structurally sparse count signal dilutes the rare event into a near-zero column that no longer
identifies when the event occurred. Sparsity gate applies before rolling window studies.

Team-scope signals (`clean_sheets`, `goals_conceded`) share value across all eligible players
in a GW row. STATE columns for these signals must carry `scope: Team` in metadata.

---

### goals_scored

| Representation | Status | Basis |
|---|---|---|
| goals_scored (raw, lag-1) | CONDITIONAL | G-EDA3-03 (DEF stable); G-EDA3-05 (FWD/MID haul-caveated); interpret with haul concentration caveat |
| goals_scored_roll3 | REJECTED-BEHAVIORAL | LENS-FORM FORM-003 — uninformative at all positions; rolling mean destroys burst structure |
| goals_scored_roll5 | REJECTED-BEHAVIORAL | Not studied; rejected by extension from FORM-003 and sparsity rationale |
| goals_scored_roll8 | REJECTED-BEHAVIORAL | Not studied; longer window further dilutes rare haul events |

**STATE columns:** `goals_scored_roll3` and `goals_scored_roll5` currently produced; these are REJECTED-BEHAVIORAL and should be removed in Phase 5 cleanup. Only `goals_scored` (raw) justified under CONDITIONAL status.

---

### assists

| Representation | Status | Basis |
|---|---|---|
| assists (raw, lag-1) | REJECTED-BEHAVIORAL | G-EDA8-10 — preferred window is raw but raw fails naive baseline at all positions; uninformative as standalone representation |
| assists_roll3 | REJECTED-BEHAVIORAL | G-EDA8-07 (MID no-improvement), G-EDA8-08 (FWD), G-EDA8-09 (DEF) — no variant clears naive baseline; Q5-Q1 gaps near-zero, non-monotonic |
| assists_roll5 | REJECTED-BEHAVIORAL | Not separately gated; rejected by extension from G-EDA8-07/08/09; rho values studied (0.062/0.092/0.002 MID/FWD/DEF) do not clear naive baseline |

**Note:** assists as raw spine data is retained in `SPINE_COLS` — it contributes to xgi computation. The REJECTED-BEHAVIORAL ruling applies to assists as an independent form signal candidate, not to the raw data field.

**STATE columns:** `assists_roll3` and `assists_roll5` currently produced; REJECTED-BEHAVIORAL; remove in Phase 5 cleanup.

---

### clean_sheets

| Representation | Status | Basis |
|---|---|---|
| clean_sheets (raw, lag-1) | CONDITIONAL — not lens-validated | Team-scope Event; routing decision; no lens rho_pooled established |
| clean_sheets_roll3 | CONDITIONAL — not lens-validated | Semantically admissible (count type); behavioral justification pending lens study |
| clean_sheets_roll5 | CONDITIONAL — not lens-validated | Same status as roll3 |

**Scope annotation required:** `scope: Team` — GW value shared by all eligible players on the team.

**Note:** xgc redundancy resolved (G-EDA8-05) — xgc is redundant with goals_conceded + clean_sheets. This decision confirms clean_sheets is the surviving defensive outcome signal. A future LENS-FORM or dedicated defensive lens should validate the rolling window representations.

---

### goals_conceded

| Representation | Status | Basis |
|---|---|---|
| goals_conceded (raw, lag-1) | CONDITIONAL — not lens-validated | Team-scope Event; moderate_shift at MID (G-EDA5) adds seasonal drift risk |
| goals_conceded_roll3 | CONDITIONAL — not lens-validated | Semantically admissible; behavioral justification pending lens study; MID moderate_shift risk applies |
| goals_conceded_roll5 | CONDITIONAL — not lens-validated | Same status as roll3 |

**Scope annotation required:** `scope: Team`

---

### saves

| Representation | Status | Basis |
|---|---|---|
| saves (raw or any window) at DEF, MID, FWD | REJECTED-SEMANTIC | G-EDA2-03 — structural zero for outfield positions |
| saves (raw, lag-1) at GKP | REJECTED-BEHAVIORAL | G-EDA8-01 — uninformative; rho −0.029; CI crosses zero; 0/3 block stability |
| saves_roll3 at GKP | REJECTED-BEHAVIORAL | G-EDA8-02 — Layer 3 ineligible; no rolling window study warranted given Layer 1 failure |
| saves_roll5 at GKP | REJECTED-BEHAVIORAL | Same basis as roll3; Layer 1 failure rules out rolling windows |

**STATE columns:** `saves_roll3` and `saves_roll5` currently produced; REJECTED-BEHAVIORAL at GKP / REJECTED-SEMANTIC at outfield; remove in Phase 5 cleanup.

---

### penalties_saved

| Representation | Status | Basis |
|---|---|---|
| penalties_saved (any representation) | REJECTED-BEHAVIORAL | G-EDA8-06 — structurally sparse (99.7% zero-rate; 8 non-zero records across 2,512 GKP player-GW rows); Layer 1 ineligible |
| penalties_saved_roll3 | REJECTED-BEHAVIORAL | Structural sparsity makes rolling mean analytically meaningless — near-constant zero column |
| penalties_saved_roll5 | REJECTED-BEHAVIORAL | Same basis |

**STATE columns:** `penalties_saved_roll3` and `penalties_saved_roll5` currently produced; REJECTED-BEHAVIORAL; remove in Phase 5 cleanup.

---

## 2. Process family

**Signals:** `xgi`, `xa`, `xg`, `xgc`
**Temporal type:** estimate
**Scope:** Individual (xgi, xa, xg); Team (xgc)

### Family rule

Rolling mean is semantically admissible for non-Context estimate signals (temporal type:
estimate; family: Process). Requires behavioral justification from EDA — persistence,
distribution density, analytical association. Component redundancy is the primary risk:
process signals that are mathematical components of each other (xa → xgi, xg → xgi) produce
rolling means with shared information. Component signals are excluded when the composite
absorbs their information.

---

### xgi

| Representation | Status | Basis |
|---|---|---|
| xgi_roll3 at DEF, MID | APPROVED | LENS-FORM FORM-001 — informative at DEF (rho=0.123) and MID (rho=0.144); passes 3/3 GW blocks |
| xgi_roll5 at DEF, MID | APPROVED | LENS-FORM FORM-002 — informative at DEF (rho=0.113) and MID (rho=0.157); passes 3/3 GW blocks; MID clears naive baseline |
| xgi_roll3 or xgi_roll5 at FWD | CONDITIONAL | CI excludes zero but fails decision relevance (Q5-Q1 gap too small; non-monotonic); haul concentration may require raw or lag-1 representation instead |
| xgi_roll8 | REJECTED-BEHAVIORAL | No EDA justification for 8-window; removed Phase 5 cleanup 2026-05-24 |
| xgi at GKP | Not studied — ontology classification (GKP is not an attacking process position) governs |

---

### xa

| Representation | Status | Basis |
|---|---|---|
| xa (all representations) | REJECTED-BEHAVIORAL | G-EDA6-02 — xa is a component of xgi; partial_rho with xgi: MID=0.67, GK=0.99; no independent information where xgi is present. xa is retained in `SPINE_COLS` as raw FPL data but no STATE representation is approved |

**Note:** xa raw spine data retained. The rejection applies to xa as an independent representation candidate only.

---

### xg

| Representation | Status | Basis |
|---|---|---|
| xg (all representations) | REJECTED-BEHAVIORAL | G-EDA6-03 — xg is a component of xgi; partial_rho: FWD=0.93, MID=0.74; absorbed by xgi at FWD and MID; additionally blocked DEF, GK, MID at data level (G-EDA2-01) |

---

### xgc

| Representation | Status | Basis |
|---|---|---|
| xgc (all representations) | REJECTED-BEHAVIORAL | G-EDA8-05 — redundant with goals_conceded + clean_sheets (partial_rho vs goals_conceded: −0.086; vs clean_sheets: −0.098; both < 0.30 threshold); informative at GKP (G-EDA8-04; rho −0.114) but carries no independent information beyond observed defensive outcomes; uninformative at DEF (G-EDA8-03) |
| xgc_roll3, xgc_roll5 | REJECTED-BEHAVIORAL | Same basis as xgc raw; rolling window of a redundant estimate adds no information |

**Scope annotation required if ever used:** `scope: Team` — xgc is a team-scope process estimate.

**STATE columns:** `xgc_roll3` and `xgc_roll5` currently produced; REJECTED-BEHAVIORAL; remove in Phase 5 cleanup.

---

## 3. Participation family

**Signals:** `minutes`
**Temporal type:** rate
**Scope:** Individual

### Family rule

Rolling mean is semantically admissible for rate signals — smoothing reflects average availability
over a window. Delta is inadmissible (week-to-week change in minutes has no stable interpretation).
Minutes is blocked as a quality/form signal (G-EDA2-02); representations are availability-only.

---

### minutes

| Representation | Status | Basis |
|---|---|---|
| minutes_roll3 at MID | APPROVED | LENS-AVAIL AVAIL-001 — informative at MID (rho=0.179); passes 3/3 GW blocks |
| minutes_roll5 at MID | APPROVED | LENS-AVAIL AVAIL-002 — informative at MID (rho=0.168); passes 3/3 GW blocks |
| minutes_roll8 at DEF, MID | APPROVED | LENS-AVAIL AVAIL-003 — informative at DEF (rho=0.130) and MID (rho=0.169); passes 3/3 GW blocks |
| minutes as form/quality signal | REJECTED-BEHAVIORAL | G-EDA2-02 — eligibility/availability signal only; blocked as form proxy |
| minutes delta | REJECTED-SEMANTIC | Rate temporal type — delta has no stable interpretation |
| minutes_trend | CONDITIONAL — threshold rationale pending | minutes_trend (30-minute threshold) exists in STATE; behavioral basis for the 30-minute threshold is undocumented; must document or remove in Phase 4 |

**Note on windows:** LENS-AVAIL tested all three windows (roll3, roll5, roll8). minutes_roll8 is the strongest availability signal at DEF. All three approved windows capture availability reliably at MID. GK and FWD are uninformative across all windows — minutes rolling representations are not meaningful at these positions.

**STATE column metadata:** `causality: pre-match-determined (availability-based)`

---

## 4. Market family

**Signals:** `transfers_in`, `transfers_out`, `ownership_count`
**Temporal type:** count (transfers_in, transfers_out), stock (ownership_count)
**Scope:** Population (all three)

### Family rule

Market signals represent population-level FPL manager behavior, not individual football
performance. Rolling transforms are inadmissible for this family:

- For **count** Market signals (transfers_in, transfers_out): rolling mean mixes current and stale
  manager sentiment across different decision cycles. Point-in-time is the appropriate form —
  each GW's transfer activity reflects that GW's managerial context.
- For **stock** Market signals (ownership_count): rolling mean is semantically invalid for any
  stock temporal type — averaging a level over multiple periods has no coherent interpretation.
  Current level (with lag-1 for strict pre-match conditioning) or delta is appropriate.

All Market signal STATE columns must carry `scope: Population`.

---

### transfers_in

| Representation | Status | Basis |
|---|---|---|
| transfers_in (point-in-time, lag-1) at DEF, MID | APPROVED | LENS-MARKET MARKET-001 — informative at DEF (rho=0.187) and MID (rho=0.190); passes 3/3 GW blocks |
| transfers_in at GK, FWD | CONDITIONAL — uninformative | rho excludes zero but fails decision relevance; GK rho=0.146, FWD rho=0.127 |
| transfers_in rolling mean | REJECTED-BEHAVIORAL | Market family rule — rolling mean mixes decision cycles; point-in-time reflects current cycle |
| transfers_balance (in minus out) | REJECTED-BEHAVIORAL | LENS-MARKET MARKET-002 — uninformative at all positions |

---

### transfers_out

| Representation | Status | Basis |
|---|---|---|
| transfers_out (point-in-time, lag-1) | CONDITIONAL — not independently lens-validated | Market family rule applies; no standalone lens finding; analogous characterisation to transfers_in |
| transfers_out rolling mean | REJECTED-BEHAVIORAL | Market family rule — no rolling transforms for population flow signals |

---

### ownership_count

| Representation | Status | Basis |
|---|---|---|
| ownership_count (point-in-time, lag-1) at DEF, MID | APPROVED | LENS-MARKET MARKET-003 — informative at DEF (rho=0.156) and MID (rho=0.168); passes 3/3 GW blocks |
| ownership_count (point-in-time) at FWD | CONDITIONAL | rho=0.136; CI excludes zero but passes only 1/3 GW blocks — unstable |
| ownership_count_delta | CONDITIONAL — not lens-validated | Delta is semantically admissible for stock temporal type; not studied; may capture recent market movement better than level; requires lens study before APPROVED |
| log1p(ownership_count) or delta-log | CONDITIONAL — pending distributional EDA | Admissible if heavy-tail distribution confirmed; ownership_count likely right-skewed; requires distributional study |
| ownership_count rolling mean | REJECTED-SEMANTIC | Stock temporal type — rolling mean of a level has no coherent interpretation as stock or flow |

---

## 5. Structural Tier family

**Signals:** `purchase_price`
**Temporal type:** stock
**Scope:** Individual

### Family rule

Structural Tier signals are slow-changing system-assigned values that encode player quality tier.
Rolling mean is inadmissible (stock type). Delta is inadmissible without further study — price
changes reflect FPL system mechanics (transfer demand), not independent football quality signal.
Current price (point-in-time) is the admissible representation.

---

### purchase_price

| Representation | Status | Basis |
|---|---|---|
| purchase_price (point-in-time, lag-1) at DEF, FWD | APPROVED | LENS-MARKET MARKET-004 — informative at DEF (passes 2/3 GW blocks) and FWD (passes 2/3 GW blocks) |
| purchase_price (point-in-time) at GK, MID | CONDITIONAL — uninformative | Fails decision relevance |
| purchase_price rolling mean | REJECTED-SEMANTIC | Stock temporal type — rolling mean of price is an average tier level over N weeks; current price is the relevant quantity |
| purchase_price delta | REJECTED-BEHAVIORAL | Price delta reflects FPL system transfer mechanics, not independent football signal; no analytical basis for use as an analytical representation |
| log1p(purchase_price) | CONDITIONAL — pending distributional EDA | Admissible if price distribution confirmed heavy-tailed; requires study |

---

## 6. Allocation family

**Signals:** `bonus`, `bps`
**Temporal type:** count
**Scope:** Individual

### Family rule

Allocation signals are FPL system constructs computed from in-match outcomes and allocated
after match completion. They are direct inputs to or components of `total_points` (the
analysis target). Using allocation signals as analytical inputs for total_points; introduces target
leakage — the association is real (G-EDA7: bonus GK rho=0.54, bps GK rho=0.91) but analytically
circular. All representations of allocation signals as analytical representations are excluded.

These signals may be used in post-match historical analysis with explicit leakage controls.
They are not valid as pre-match inputs to scoring or decision modules.

---

### bonus

| Representation | Status | Basis |
|---|---|---|
| bonus (any representation) as analytical representation | REJECTED-BEHAVIORAL | G-EDA7-06 — target leakage risk; bonus is a direct component of total_points; rho=0.54 at DEF/GK is analytically circular |

**STATE column:** If materialized, must carry `leakage_risk: in_match_allocation` and `causality: post-match`. Must not be consumed by any operational scoring module without explicit leakage-controlled study design.

---

### bps

| Representation | Status | Basis |
|---|---|---|
| bps (any representation) as analytical representation | REJECTED-BEHAVIORAL | G-EDA7-06 — target leakage risk; bps is the input to bonus allocation; rho=0.91 at GK reflects the circular relationship |

**STATE column:** Same annotation requirement as bonus — `leakage_risk: in_match_allocation`.

---

## 7. Context family

**Signals:** `fdr_avg`, `fdr_max`, `fdr_min`, `was_home`, `fixture_count`
**Temporal type:** estimate (fdr_avg, fdr_max, fdr_min), indicator (was_home), count (fixture_count)
**Scope:** Match (all five)

### Family rule

Context signals are fully determined pre-match. They describe a fixture or fixture set, not
a player's temporal trajectory. Any temporal transform — rolling mean, delta, lag — is
inadmissible regardless of the temporal type of the underlying signal. There is no "recent
fixture difficulty form" that belongs to the player. Context signals belong in STATE as raw
labels only.

All Context signal STATE columns: `causality: pre-match-determined`, `scope: Match`.

---

### fdr_avg

| Representation | Status | Basis |
|---|---|---|
| fdr_avg (raw label, current GW) | APPROVED as context label | Context labels belong in STATE raw; not a form feature |
| fdr_avg rolling mean | REJECTED-SEMANTIC | Context family — pre-match fixed; temporal aggregation is inadmissible |
| fdr_avg as directional rank indicator | REJECTED-BEHAVIORAL | LENS-FIXTURE-GW FIXTURE-001 — fails decision relevance at all positions; Q5-Q1 gap negative and non-monotonic |
| fdr_avg as binary difficulty moderator | CONDITIONAL — SYNTH-01 question | May condition other signals in stratified analysis (easy/medium/hard tercile); not validated as standalone representation; deferred to SYNTH-01 |

---

### fdr_max

| Representation | Status | Basis |
|---|---|---|
| fdr_max (any representation) | REJECTED-SEMANTIC | G-EDA6-01 — perfectly redundant with fdr_avg (pairwise rho=1.0); additionally Context ontology excludes all temporal aggregation. fdr_max retained in `SPINE_COLS` as raw DGW structural metadata |

---

### fdr_min

| Representation | Status | Basis |
|---|---|---|
| fdr_min (any representation) | REJECTED-SEMANTIC | G-EDA6-01 — perfectly redundant with fdr_avg (pairwise rho=1.0); additionally Context ontology excludes all temporal aggregation. fdr_min retained in `SPINE_COLS`; remove from `_REQUIRED_SPINE_COLS` in Phase 4 (over-declaration; not consumed by any operational module) |

---

### was_home

| Representation | Status | Basis |
|---|---|---|
| was_home (raw label, current GW) | APPROVED as context label | Context labels belong in STATE raw; use as binary moderator or grouping variable only |
| was_home (any temporal transform) | REJECTED-SEMANTIC | Context family, indicator temporal type — no magnitude; no valid arithmetic between values; pre-match fixed |

---

### fixture_count

| Representation | Status | Basis |
|---|---|---|
| fixture_count (raw label, current GW) | APPROVED as context label | Context labels belong in STATE raw; useful for DGW identification |
| fixture_count (any temporal transform) | REJECTED-SEMANTIC | Context family — pre-match fixed; LENS-FIXTURE-GW FIXTURE-003 confirmed the apparent DGW association is the fixture multiplier effect, not fixture_count as an independent signal (DGW-adjusted CI crosses zero) |

---

## 8. Outcome family

**Signals:** `total_points`
**Temporal type:** count
**Scope:** Individual

### Family rule

`total_points` is the analysis target. Using its rolling mean as a primary representation
is analytically circular — the model would be using lagged target values to characterise the target.
The lag-1 raw value is the standard naive baseline used in evaluation comparisons (G-EDA7-02),
not an operational representation. Rolling mean of total_points as a primary representation is REJECTED
at all positions.

---

### total_points

| Representation | Status | Basis |
|---|---|---|
| total_points_lag1 (raw) | APPROVED as naive baseline only | G-EDA7-02 — mandatory naive baseline for all lens study comparisons; not an operational representation |
| total_points_roll5 at MID | CONDITIONAL as evaluation baseline | LENS-FORM FORM-005 — informative at MID only (rho=0.157); position-conditional baseline, not a feature |
| total_points_roll3 | REJECTED-BEHAVIORAL | LENS-FORM FORM-004 — uninformative or unstable at all positions |
| total_points rolling mean as primary representation | REJECTED-BEHAVIORAL | Using lagged target values to characterise the target is analytically circular; rolling mean as primary representation is excluded regardless of naive rho |

---

## Consolidated STATE representation decision table

| Signal | Family | Current STATE columns | Decision | Gate |
|---|---|---|---|---|
| xgi | Process | xgi_roll3, xgi_roll5 | APPROVED DEF/MID | LENS-FORM FORM-001/002 |
| xgi_roll3/5 FWD | Process | — | CONDITIONAL | LENS-FORM FORM-001/002 |
| xa | Process | — (removed Phase 5) | REJECTED-BEHAVIORAL | G-EDA6-02 |
| xg | Process | — | REJECTED-BEHAVIORAL | G-EDA6-03 |
| xgc | Process | xgc_roll3, xgc_roll5 | REJECTED-BEHAVIORAL → remove | G-EDA8-05 |
| goals_scored | Event | goals_scored_roll3, goals_scored_roll5 | raw CONDITIONAL; roll* REJECTED-BEHAVIORAL → remove | LENS-FORM FORM-003 |
| assists | Event | assists_roll3, assists_roll5 | REJECTED-BEHAVIORAL → remove | G-EDA8-07/08/09/10 |
| clean_sheets | Event | clean_sheets_roll3, clean_sheets_roll5 | CONDITIONAL (not lens-validated) | EDA7-routing |
| goals_conceded | Event | goals_conceded_roll3, goals_conceded_roll5 | CONDITIONAL (not lens-validated) | EDA7-routing |
| saves | Event | saves_roll3, saves_roll5 | REJECTED-BEHAVIORAL (GKP) / REJECTED-SEMANTIC (outfield) → remove | G-EDA8-01/02; G-EDA2-03 |
| penalties_saved | Event | penalties_saved_roll3, penalties_saved_roll5 | REJECTED-BEHAVIORAL → remove | G-EDA8-06 |
| minutes_roll3 | Participation | minutes_roll3 | APPROVED MID | LENS-AVAIL AVAIL-001 |
| minutes_roll5 | Participation | minutes_roll5 | APPROVED MID | LENS-AVAIL AVAIL-002 |
| minutes_roll8 | Participation | minutes_roll8 | APPROVED DEF, MID | LENS-AVAIL AVAIL-003 |
| minutes_trend | Participation | minutes_trend | CONDITIONAL — threshold undocumented | Phase 4 task |
| transfers_in | Market | transfers_in | APPROVED DEF, MID | LENS-MARKET MARKET-001 |
| transfers_out | Market | transfers_out | CONDITIONAL (not lens-validated) | Market family rule |
| ownership_count | Market | ownership_count | APPROVED DEF, MID | LENS-MARKET MARKET-003 |
| purchase_price | Structural Tier | purchase_price | APPROVED DEF, FWD | LENS-MARKET MARKET-004 |
| bonus | Allocation | bonus | REJECTED-BEHAVIORAL (leakage) | G-EDA7-06 |
| bps | Allocation | bps | REJECTED-BEHAVIORAL (leakage) | G-EDA7-06 |
| fdr_avg | Context | fdr_avg | APPROVED as raw context label | LENS-FIXTURE-GW; G-EDA6-01 |
| fdr_max | Context | fdr_max (spine only) | REJECTED-SEMANTIC | G-EDA6-01 |
| fdr_min | Context | fdr_min (spine only) | REJECTED-SEMANTIC | G-EDA6-01 |
| was_home | Context | was_home | APPROVED as raw context label | Ontology; LENS-FIXTURE-GW |
| fixture_count | Context | fixture_count | APPROVED as raw context label | Ontology; LENS-FIXTURE-GW |
| total_points | Outcome | — (target only) | APPROVED lag-1 as naive baseline; rolling mean as primary representation REJECTED-BEHAVIORAL | G-EDA7-02 |

---

## Phase 5 cleanup targets

The following STATE columns are currently produced but have REJECTED-BEHAVIORAL status.
They must be removed from `_ROLL_COLS` and the schema guard updated in Phase 5:

| Column(s) | Reason | Gate |
|---|---|---|
| xgc_roll3, xgc_roll5 | Redundant with goals_conceded + clean_sheets | G-EDA8-05 |
| goals_scored_roll3, goals_scored_roll5 | Rolling mean destroys burst structure | LENS-FORM FORM-003 |
| assists_roll3, assists_roll5 | Fails naive baseline at all positions | G-EDA8-07/08/09/10 |
| saves_roll3, saves_roll5 | Uninformative at GKP; structural zero outfield | G-EDA8-01/02; G-EDA2-03 |
| penalties_saved_roll3, penalties_saved_roll5 | Structurally sparse (99.7% zero-rate) | G-EDA8-06 |

---

## Changelog

| Version | Date | Notes |
|---|---|---|
| 1.0 | 2026-05-24 | Initial document; all 8 families; 23 signals |
