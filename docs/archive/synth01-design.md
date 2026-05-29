# SYNTH-01 Design — Composition Methodology

**Status:** FROZEN — Phase 4 complete  
**Issued:** 2026-05-27  
**Authority:** Operational Convergence Plan Phase 4 (§4.3, §4.5)  
**Candidate set:** `docs/governance/synth01-candidate-set.md`  
**Frozen registry:** `signals/registry/synth01_candidates.yaml`

---

## Purpose

This document specifies all methodology decisions required before Phase 5 (SYNTH-01 execution) begins. Every dimension left undecided here is a blocker for Phase 5. The decisions below are governance calls made under the authority of the Operational Convergence Plan (§Manual Governance Acceptance Criteria item 2).

---

## Synthesis Scope

**In scope for SYNTH-01:**
- DEF — 6 candidates; composite synthesis eligible
- MID — 7 candidates; composite synthesis eligible

**Not in scope:**
- FWD — 1 candidate (purchase_price only); no composite synthesis; single-signal qualified score only
- GK — 0 candidates from any lens; deferred — see §GK Scope Decision below

**Synthesis outputs required for:** DEF and MID, per candidate, with per-lens composite weights.

---

## GK Scope Decision (Task 4.5)

**Decision: DEFERRED — GK not in scope for SYNTH-01.**

**Rationale:**

No GK entry in `evaluation_metadata.yaml` carries `lifecycle_state=candidate`. The evaluation picture at GK is:
- FORM lens: xgi blocked by ontological design (G-EDA3-01); minutes excluded (near-constant playing time, GK-CONSTANT)
- AVAIL lens: minutes_roll3/5/8 fail Gate 2 at GK (Q5-Q1 below threshold at all three windows)
- MARKET lens: transfers_in, ownership_count, purchase_price — all fail Gate 2 at GK (non-monotonic quintile ordering)
- FIXTURE-GW lens: all signals excluded at GK

The defensive signals materialized in STATE (`xgc_roll3/5`, `goals_conceded_roll3/5`, `clean_sheets_roll3/5`) are approved as STATE representations at DEF/GK scope, but they have not been evaluated in a dedicated GK lens study. Their informativeness at GK specifically has not been established. The LENS-FORM study evaluated these signals for form prediction (total_points target); GK-specific operational behavior has not been studied.

**Consequence:** Any SYNTH-01 composition model that includes GK would be building on unevaluated signals. This violates the principle that all synthesis candidates must have lens gate provenance.

**Action:** GK synthesis is deferred pending a dedicated `LENS-GK` study that evaluates:
- Defensive signals (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5) against the GK scoring target
- minutes_roll3/5/8 against played_next_gw at GK (despite Gate 2 failures — the target may need revision for GK)
- save_rate as a potential new GK-specific signal not currently in STATE

LENS-GK is proposed as a post-Phase-6 study, with GK synthesis as a follow-on SYNTH-01-GK study.

---

## Composition Methodology Decisions (Task 4.3)

### Decision 1 — Composition Type

**Decision: Additive weighted composite.**

Signals are combined as a weighted sum: `score = Σ (weight_i × signal_i)`, where weights sum to 1.0 within each position × lens group.

**Rationale:** Spearman rho was the evaluation metric throughout lens studies; additive composition preserves the scale relationships that rho quantifies. Rank-based aggregation (e.g., Borda count) would discard magnitude differences already documented in the evaluation evidence. The gate methodology explicitly uses quintile return differences as the decision relevance criterion — an additive composition honours that structure directly.

**Alternative considered:** Rank-based aggregation (less sensitive to outliers). Rejected: the candidate set contains signals with materially different rho magnitudes (0.113 to 0.232); rank aggregation would equate them. Rho differences are evidence-based, not editorial — they should inform weight allocation.

---

### Decision 2 — Weight Derivation

**Decision: Partial rho magnitudes from multivariate evaluation, normalized within each position × lens group.**

Weight for signal `i` at position `p` in lens group `g`:

```
raw_weight_i = |partial_rho(signal_i | all other candidates at same position × lens)|
weight_i = raw_weight_i / Σ raw_weight_j  (sum over j in same position × lens group)
```

**Constraint:** No single signal receives weight > 0.60 in any composite. If unconstrained optimization assigns weight > 0.60 to one signal, the excess is redistributed proportionally to remaining signals. The binding constraint must be documented in the Phase 5 decision for that signal.

**Baseline check:** Equal-weight allocation is computed as a sanity check for each position × lens. If the evidence-derived composite does not improve on equal-weight allocation by at least 0.02 Spearman rho units, document the result and retain equal-weight as the composition weight with explicit notation that evidence failed to support differentiated weights.

**Leakage constraint:** No weight derivation may use `points_roll5` or any target-adjacent signal as a covariate. The partial rho must be computed in a target-clean feature space.

---

### Decision 3 — Position-Specificity

**Decision: Per-position weights throughout. No pooled or cross-position weights.**

**Rationale:** The candidate set itself is position-specific — different signals are candidates at DEF vs. MID. Cross-position weight pooling would require signals to be candidates at both positions; none qualify. Even for signals that are candidates at both DEF and MID (xgi_roll3, xgi_roll5, transfers_in, ownership_count, minutes_roll8), the per-position rho values differ materially enough that pooling would be analytically unjustified.

Example: xgi_roll3 DEF rho=0.123 vs MID rho=0.144. Pooled weight would under-serve MID and over-serve DEF. The gate evidence is per-position; the composition must be per-position.

**Implementation note for Phase 5:** Each position × lens group is evaluated independently. The Phase 5 evaluation must not share parameters across position groups.

---

### Decision 4 — Interaction Effects

**Decision: Deferred. Moderation effects are not evaluated in initial SYNTH-01.**

**Rationale:** Three potential interaction dimensions exist — fixture difficulty (FDR quartile), minutes context (starter vs. rotation), GW type (DGW/BGW/standard). Evaluating moderation terms would multiply the composition parameter space by 3–4x with no prior evidence base to constrain which interactions are likely material.

**Moderation deferral policy:**
- No moderation terms in SYNTH-01 primary composition models
- After primary compositions are derived (Phase 5), run a single moderation sensitivity check: does FDR quartile materially change signal-rank ordering in > 15% of cases? This is a Phase 5 extension task, not a Phase 5 prerequisite
- If any moderation effect is found `material` (> 15% case impact), document in Phase 5 and flag for Phase 7 (runtime consumer alignment) to implement as a GW-type or FDR modifier on the base composite score

**Not permitted:** Any pre-Phase-5 assumption that moderation effects exist. No moderation terms may be added to the frozen candidate registry without restarting Phase 4.

---

### Decision 5 — Baseline

**Decision: `points_roll5` naive baseline for FORM and MARKET lens compositions; unconditional position start rate for AVAIL compositions.**

**FORM and MARKET baseline (total_points target):**

The naive baseline is `points_roll5` MID (rho=0.158, 3/3 blocks), sourced from LENS-FORM FORM-005. This is the position-conditional benchmark: a composition model must out-perform the naive baseline at each position for which it claims predictive superiority.

- DEF naive baseline: not established from lens studies (points_roll5 DEF did not pass all gates). SYNTH-01 at DEF uses a permutation-derived baseline: rank correlation of a shuffled version of the target vs. each signal.
- MID naive baseline: points_roll5 MID rho = 0.158. Composite must exceed this.
- FWD: no composite; not applicable.

**Note:** The naive baseline is excluded from SYNTH-01 models themselves on evaluation circularity grounds (G-EDA7-02). It is an external reference point only — it does not participate in any synthesis model as a covariate.

**AVAIL baseline (played_next_gw target):**

No equivalent naive baseline exists for the AVAIL target. The baseline is the unconditional start rate per position (fraction of players who appeared in the next GW, computed from the evaluation population). SYNTH-01 AVAIL compositions must exceed this unconditional rate in terms of Spearman rho against played_next_gw.

---

## Redundancy Resolution Protocol

From `synth01-candidate-set.md §High-Redundancy Resolution Protocol`:

For the confirmed high-redundancy pairs (`ownership_count × transfers_in` at DEF rho=0.794 and MID rho=0.831):

**Step 1:** SYNTH-01 computes `marginal_gain(ownership_count | transfers_in)` and `marginal_gain(transfers_in | ownership_count)` at each position.

**Step 2 — SUBSTITUTE decision** (marginal_gain < 0.02 in both directions):
- Retain `transfers_in` (higher rho at both positions: DEF 0.187 > 0.156; MID 0.190 > 0.168)
- Issue `EXCLUDED-REDUNDANT` for `ownership_count` at that position
- Document: "ownership_count absorbed by transfers_in (marginal_gain=[value]; tiebreak: transfers_in rho > ownership_count rho)"

**Step 3 — COMPLEMENTARY decision** (marginal_gain ≥ 0.02 in at least one direction):
- Retain both signals at that position
- Document complementarity basis

**Step 4:** Resolution documented in `signals/evaluation/synth01_decisions.yaml` before any composition weight is finalized.

This protocol applies per position independently — the signal may be SUBSTITUTE at one position and COMPLEMENTARY at another.

---

## Within-Window-Family Protocol

For rolling window families (xgi_roll3/5 and minutes_roll3/5/8), SYNTH-01 applies the same marginal gain protocol as for the redundancy pairs:

- Compute `marginal_gain(roll_N | roll_M)` for each window pair within the same position × signal family
- If gain < 0.02: retain the window with higher partial rho; issue `EXCLUDED-REDUNDANT` for the other
- If gain ≥ 0.02: retain both; document complementarity

Expected outcome: for highly overlapping windows (roll3 vs roll5), the longer window is likely absorbed by the shorter or equivalent. For the minutes family at MID (roll3/5/8), the window most predictive of playing time stability is expected to dominate.

---

## Stopping Criteria for Phase 5

Phase 5 is complete when:

1. A `G-SYNTH1-*` decision exists for every one of the 14 candidate-position pairs in the frozen registry.
2. All high-redundancy pairs have a SUBSTITUTE or COMPLEMENTARY classification.
3. All within-window-family pairs have a documented marginal gain test result.
4. Composition weights (with bootstrap CIs) exist for every retained signal at DEF and MID.
5. The baseline comparison is documented: composite rho vs. naive baseline at MID; composite rho vs. permutation baseline at DEF.
6. Moderation sensitivity check is run (pass/fail verdict only; if material, flagged for Phase 7).
7. `signals/evaluation/synth01_decisions.yaml` is produced with all decisions.

Phase 5 may not finalize weights until all redundancy resolution decisions are made.

---

## Phase 5 Verification Criteria (from Operational Convergence Plan §4)

- `G-SYNTH1-*` decisions exist for all 14 candidates
- No weight is a round number without an analytical derivation
- All SUBSTITUTE pairs resolved: only one signal from each retained
- `synth01_decisions.yaml` complete and consistent with `evaluation_metadata.yaml`
- GK scope decision documented (this document, §GK Scope Decision — complete)
