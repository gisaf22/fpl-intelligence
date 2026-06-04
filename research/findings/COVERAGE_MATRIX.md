# EDA Coverage Map — Ontology Signals vs EDA Evidence

**Produced:** 2026-05-24
**Updated:** 2026-05-24 — EDA-8 complete; partial signals reclassified
**Purpose:** Phase 2, Step 1 — classify each ontology signal as `covered`, `partial`, or `unstudied` before writing behavior profiles.
**Sources:** `EDA_FINDINGS.md` (EDA-0 through EDA-8), lens designs (LENS-FORM, LENS-AVAIL, LENS-MARKET, LENS-FIXTURE-GW)

**Classifications:**
- `covered` — sufficient EDA gate decisions to write a complete behavior profile without new studies
- `partial` — some EDA evidence exists but rolling window behavior, sparsity, or representation implications are not formally established
- `unstudied` — no EDA backing at all

---

## Coverage table

| Signal | Family | Coverage | Key EDA evidence | Gap |
|---|---|---|---|---|
| total_points | Outcome | covered | G-EDA7-02: mandatory naive baseline; LENS-FORM points_roll3/roll5 studied | — |
| xgi | Process | covered | G-EDA3-01/02; LENS-FORM FORM-001/002 (roll3/roll5 studied); EDA-5 stability | — |
| goals_scored | Event | covered | G-EDA3-03/05; LENS-FORM FORM-003 (roll3 studied); haul sparsity documented | — |
| clean_sheets | Event | covered | EDA-7 §7.4: FIXTURE-GW territory; LENS-FIXTURE-GW ran; team-scope confirmed | — |
| goals_conceded | Event | covered | EDA-7 §7.4: FIXTURE-GW territory; LENS-FIXTURE-GW ran; EDA-5 moderate_shift MID | — |
| minutes | Participation | covered | G-EDA2-02: blocked as form; LENS-AVAIL AVAIL-001/002/003 (roll3/roll5/roll8 studied) | — |
| transfers_in | Market | covered | LENS-MARKET ran; point-in-time characterisation; no rolling transforms | — |
| transfers_out | Market | covered | LENS-MARKET ran; point-in-time characterisation; no rolling transforms | — |
| ownership_count | Market | covered | LENS-MARKET ran; stock signal; no rolling transforms | — |
| purchase_price | Structural Tier | covered | LENS-MARKET ran; stock signal; no rolling transforms | — |
| fdr_avg | Context | covered | G-EDA6-01: sole representative of fdr_* family; LENS-FIXTURE-GW ran | — |
| fdr_max | Context | covered | G-EDA6-01: perfectly redundant with fdr_avg (rho 1.0); no independent study needed | No independent profile — fold into fdr_avg redundancy entry |
| fdr_min | Context | covered | G-EDA6-01: perfectly redundant with fdr_avg (rho 1.0); no independent study needed | No independent profile — fold into fdr_avg redundancy entry |
| assists | Event | covered | G-EDA3-04: contemporaneous rho 0.49/0.36 (MID/FWD); EDA-8D: lag-1 rho ≈ 0.04 MID (lag-1) — uninformative; all rolling variants fail naive baseline | EDA-8D resolved: no assists variant recommended (G-EDA8-07/08/09/10) |
| bonus | Allocation | covered | EDA-7: core_signal DEF/GK (contemporaneous rho 0.54); G-EDA7-06: excluded (target leakage risk) | Decision closed via leakage gate; no representation warranted |
| bps | Allocation | covered | EDA-7: core_signal GK (contemporaneous rho 0.91); G-EDA7-06: excluded (target leakage risk) | Decision closed via leakage gate; no representation warranted |
| saves | Event | covered | EDA-8A: G-EDA8-01 uninformative (lag-1 rho −0.029, CI crosses zero); G-EDA8-02 ineligible | EDA-8A resolved: saves GKP uninformative as a standalone signal; no rolling window warranted |
| xa | Process | covered | EDA-2: blocked DEF/FWD; G-EDA6-02: component of xgi — xa_roll* excluded as independent candidate | Decision closed via redundancy gate |
| xg | Process | covered | EDA-2: blocked DEF/GK/MID; G-EDA6-03: component of xgi at FWD (rho 0.93) and MID (0.74) | Decision closed via redundancy gate |
| xgc | Process | covered | EDA-8B: G-EDA8-03 DEF uninformative; G-EDA8-04 GKP informative; G-EDA8-05 redundant with goals_conceded + clean_sheets | EDA-8B resolved: xgc carries no independent information; no representation warranted |
| penalties_saved | Event | covered | EDA-8C: G-EDA8-06 structurally-sparse (99.7% zero-rate; 8 non-zero records) | EDA-8C resolved: Layer 1 ineligible; no representation warranted |
| was_home | Context | ontology-derived | Context family — pre-match fixed; Layer 3 ineligible by ontology classification; no gate decisions produced or required | None — ontology exclusion is complete; no EDA study needed |
| fixture_count | Context | ontology-derived | Context family — pre-match fixed; Layer 3 ineligible by ontology classification; additionally blocked FWD/GK (G-EDA2-01) | None — ontology exclusion is complete; no EDA study needed |

---

## Summary

| Classification | Count | Signals |
|---|---|---|
| covered | 21 | total_points, xgi, goals_scored, clean_sheets, goals_conceded, minutes, transfers_in, transfers_out, ownership_count, purchase_price, fdr_avg, fdr_max, fdr_min, assists, bonus, bps, saves, xa, xg, xgc, penalties_saved |
| partial | 0 | — all former partial signals resolved by EDA-8 gate decisions |
| ontology-derived | 2 | was_home, fixture_count — Context family; Layer 3 ineligible by classification; no EDA gate decisions produced or required |
| unstudied | 0 | — |

---

## Gap analysis

### Signals where decision is already made — no new EDA needed

These partial signals have a clear representation decision from existing gate decisions. A behavior profile can be written now with "decision: excluded/redundant" and the gate decision cited.

| Signal | Decision already made | Gate |
|---|---|---|
| xa | Excluded as independent candidate; component of xgi | G-EDA6-02 |
| xg | Excluded as independent candidate; component of xgi | G-EDA6-03 |
| fdr_max | Excluded; redundant with fdr_avg | G-EDA6-01 |
| fdr_min | Excluded; redundant with fdr_avg | G-EDA6-01 |
| bonus | Excluded from LENS-FORM; leakage risk | G-EDA7-06 |
| bps | Excluded from LENS-FORM; leakage risk | G-EDA7-06 |

### Ontology-derived exclusions — not partial signals; no EDA or behavior profile needed

These signals are excluded from temporal transforms by their ontology family classification.
They are not `partial` — they have no gap to close. No EDA gate decision is required because
the exclusion is not an empirical finding; it is a property of what the signal fundamentally is.
Behavior profiles for these signals record the ontology exclusion only — no representation
implication section is needed.

| Signal | Family | Exclusion basis |
|---|---|---|
| was_home | Context | Pre-match fixed by ontology; Layer 3 ineligible by family classification |
| fixture_count | Context | Pre-match fixed by ontology; additionally blocked FWD/GK (G-EDA2-01) |

### EDA-8 resolution (2026-05-24)

All former partial signals have been resolved by EDA-8 gate decisions (G-EDA8-01 through
G-EDA8-10). No open-question signals remain.

| Signal | Resolution | Gate |
|---|---|---|
| saves (GKP) | Uninformative as a standalone signal — structural tension between saves and clean sheet points | G-EDA8-01, G-EDA8-02 |
| xgc (GKP) | Informative but redundant with goals_conceded + clean_sheets | G-EDA8-04, G-EDA8-05 |
| xgc (DEF) | Uninformative | G-EDA8-03 |
| penalties_saved | Structurally sparse (99.7% zero-rate) | G-EDA8-06 |
| assists rolling | No-improvement at all positions; raw assists also fails naive baseline in lag-1 analysis | G-EDA8-07/08/09/10 |

---

## Status

**EDA coverage complete as of 2026-05-24.** All 23 ontology signals have gate decisions
or ontology-derived exclusions. No gap studies remain. Behavior profiles can be finalised
for all 23 signals.
