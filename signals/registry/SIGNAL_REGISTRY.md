# SIGNAL_REGISTRY.md
# Analytical Methodology — Signal Registry

**Status:** ACTIVE — SYNTH-01 complete; 10 approved, 3 excluded-redundant, 1 FWD single-signal
**Registry version:** synth01
**Last updated:** 2026-05-27
**Owned by:** signals/registry/

---

## Purpose

This is the governance and truth layer for all signals in the
fpl-intelligence methodology.

It is the single source of truth for:
- what signals exist in the system
- their validation status at each lifecycle stage
- whether they are eligible for synthesis
- known limitations and scope constraints

No signal may enter synthesis or experiments without a
confirmed record in this registry. No signal may be
referenced in a study design without first being registered
here as a candidate.

If a signal is not in this registry, it does not exist
in the system.

---

## Current state

**LENS-FORM complete: 2026-05-22**

6 form signal candidates characterised. Run artefacts:
`studies/runs/LENS-FORM-20260522_204715/`

Results summary:
- FORM-001 xgi_roll3: informative DEF and MID; uninformative FWD
- FORM-002 xgi_roll5: informative DEF and MID; uninformative FWD
- FORM-003 goals_scored_roll3: uninformative all positions
- FORM-004 points_roll3: uninformative (naive baseline — GKP, DEF, MID); unstable FWD
- FORM-005 points_roll5: informative MID only (naive baseline)
- FORM-006 minutes_roll3: uninformative all positions

Signals advancing to synthesis from LENS-FORM: xgi_roll3 (DEF, MID), xgi_roll5 (DEF, MID)

**LENS-AVAIL complete: 2026-05-22** — minutes_roll3/5 informative MID; minutes_roll8 informative DEF+MID
**LENS-MARKET complete: 2026-05-22** — transfers_in and ownership_count informative DEF+MID; purchase_price informative DEF+FWD
**LENS-FIXTURE-GW complete: 2026-05-22** — all signals uninformative; fdr_avg shows correlation but non-monotonic quintiles

Signals advancing to SYNTH-01:
- FORM: xgi_roll3 (DEF, MID), xgi_roll5 (DEF, MID)
- AVAIL: minutes_roll8 (DEF, MID) [strongest availability signal]
- MARKET: transfers_in (DEF, MID), ownership_count (DEF, MID), purchase_price (DEF, FWD)
- FIXTURE-GW: none — fdr_avg reserved for binary moderator role in SYNTH-01

Previous study outputs (SA, SB, SC, SE) are archived in
research/lenses/*/results/archive/. They are not valid
registry inputs — they predate the system EDA and locked
methodology and cannot be traced to EDA findings.

---

## Schema

| Signal ID | Signal | Lens | Lag | Positions | EDA Status | Lens Status | Synthesis Status | Known Caveats | Last Updated |
|-----------|--------|------|-----|-----------|------------|-------------|------------------|---------------|--------------|
| FORM-001 | xgi_roll3 | FORM | lag-1 | DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | DEF: approved-primary (G-SYNTH1-01, w=0.50). MID: excluded-redundant (G-SYNTH1-07, absorbed by xgi_roll5). | DEF: rho 0.123, CI [0.084, 0.161], passes 3/3 blocks, Q5-Q1 1.12, clears naive baseline. MID: rho 0.144, CI [0.107, 0.182], passes 3/3 blocks, Q5-Q1 1.30, does NOT clear naive baseline (points_roll3 MID rho 0.156). FWD: CI excludes zero (rho 0.091) but fails monotonicity gate — not decision relevant. GK excluded (G-EDA3-01). xgi subsumes xa and xg — no independent competing candidates (G-EDA6-02, G-EDA6-03). SYNTH-01: DEF partial rho=0.0401 controlling for xgi_roll5. MID partial rho=0.0089 — absorbed. | 2026-05-27 |
| FORM-002 | xgi_roll5 | FORM | lag-1 | DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | DEF: approved-secondary (G-SYNTH1-02, w=0.50). MID: approved-primary (G-SYNTH1-08, w=1.00, sole retained). | DEF: rho 0.113, CI [0.071, 0.155], passes 3/3 blocks, Q5-Q1 1.04, clears naive baseline (borderline). MID: rho 0.157, CI [0.118, 0.197], passes 3/3 blocks, Q5-Q1 1.64, clears naive baseline. FWD: CI excludes zero (rho 0.097) but fails monotonicity — not decision relevant. GK excluded. SYNTH-01 DEF: partial rho=0.0271 controlling for xgi_roll3; retained. MID: partial rho=0.0643 controlling for xgi_roll3; xgi_roll3 absorbed (G-SYNTH1-07). MID composite rho=0.157 vs naive baseline 0.158 — does NOT clear; flagged for Phase 9 review. | 2026-05-27 |
| FORM-003 | goals_scored_roll3 | FORM | lag-1 | DEF (uninformative), MID (uninformative), FWD (uninformative) | passed | uninformative | excluded | DEF: CI crosses zero (rho 0.018, CI [−0.023, 0.061]). MID: CI excludes zero (rho 0.076) but fails decision relevance (Q5-Q1 0.38, non-monotonic). FWD: CI excludes zero (rho 0.097) but fails decision relevance (Q5-Q1 0.79, non-monotonic). Raw goals_scored EDA rho was same-GW (0.32 DEF); lag-1 prediction rho is substantially lower. Event sparsity: rolling mean of sparse binary event does not provide monotonic bin separation. | 2026-05-22 |
| FORM-004 | points_roll3 | FORM | lag-1 | GKP (uninformative), DEF (uninformative), MID (uninformative), FWD (unstable) | passed | uninformative | excluded | Naive baseline only — not a synthesis candidate. GKP: CI crosses zero (rho 0.071). DEF: CI excludes zero but non-monotonic (Q5-Q1 1.22, monotonic=False). MID: CI excludes zero but Q5-Q1 gap 0.99 — just below 1.0 threshold (monotonic=True). FWD: CI excludes zero in aggregate but passes only 1/3 blocks — unstable. Naive baseline function served: points_roll5 MID is the informative naive benchmark. | 2026-05-22 |
| FORM-005 | points_roll5 | FORM | lag-1 | GKP (uninformative), DEF (uninformative), MID (informative), FWD (uninformative) | passed | conditional | excluded | Naive baseline — not a synthesis candidate as independent signal. MID: rho 0.158, CI [0.118, 0.198], passes 3/3 blocks, Q5-Q1 1.31, monotonic. Sets naive baseline for MID at rho 0.158. FORM-001 (xgi_roll3 MID, rho 0.144) does NOT clear this baseline. FORM-002 (xgi_roll5 MID, rho 0.157) borderline below this baseline. GKP: CI crosses zero. DEF and FWD: CI excludes zero but fail decision relevance. | 2026-05-22 |
| FORM-006 | minutes_roll3 | FORM | lag-1 | DEF (uninformative), MID (uninformative), FWD (uninformative) | flagged | uninformative | excluded | All positions: CI excludes zero (DEF rho 0.138, MID rho 0.179, FWD rho 0.085) but fail decision relevance — non-monotonic bin distributions. minutes_roll3 does not provide monotonic next-GW return separation. GK excluded (near-constant playing time). Raw minutes blocked as form signal (G-EDA2-02). LENS-AVAIL should characterise availability consistency and reliability properties — this study provides raw association evidence only (G-EDA7-05). | 2026-05-22 |
| AVAIL-001 | minutes_roll3 | AVAIL | lag-1 | GKP (uninformative), DEF (uninformative), MID (informative), FWD (uninformative) | flagged | conditional | MID: approved-primary (G-SYNTH1-09, w=0.50). | Primary target: played_next_gw (binary). MID: rho 0.232, CI [0.198, 0.269], passes 3/3 blocks, decision relevant. DEF: rho 0.223 CI excludes zero but fails monotonicity (Q5-Q1=0.214). FWD: rho 0.186 CI excludes zero but fails monotonicity (Q5-Q1=0.202). GKP: CI excludes zero but Q5-Q1=0.058 below threshold. Run: LENS-AVAIL-20260522_210958. SYNTH-01 MID: partial rho=0.0512 controlling for minutes_roll5 and minutes_roll8; retained with minutes_roll8 (minutes_roll5 absorbed, G-SYNTH1-10). | 2026-05-27 |
| AVAIL-002 | minutes_roll5 | AVAIL | lag-1 | GKP (uninformative), DEF (uninformative), MID (informative), FWD (unstable) | flagged | conditional | MID: excluded-redundant (G-SYNTH1-10, absorbed by minutes_roll3 + minutes_roll8). | Primary target: played_next_gw. MID: rho 0.227, CI [0.190, 0.265], passes 3/3 blocks, decision relevant. DEF: rho 0.213, CI excludes zero but fails monotonicity (Q5-Q1=0.226). FWD: CI excludes zero in aggregate but passes only 1/3 blocks — unstable. GKP: Q5-Q1=0.083, below threshold. SYNTH-01 MID: partial rho=0.0118 controlling for minutes_roll3 and minutes_roll8 — absorbed (< 0.02 threshold). | 2026-05-27 |
| AVAIL-003 | minutes_roll8 | AVAIL | lag-1 | GKP (uninformative), DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | DEF: approved-primary (G-SYNTH1-03, w=1.00, sole DEF candidate). MID: approved-secondary (G-SYNTH1-11, w=0.50). | Primary target: played_next_gw. DEF: rho 0.219, CI [0.174, 0.261], passes 3/3 blocks, decision relevant. MID: rho 0.222, CI [0.180, 0.261], passes 3/3 blocks, decision relevant. FWD: rho 0.206, CI excludes zero but fails monotonicity (Q5-Q1=0.263). GKP: Q5-Q1=0.103 at threshold boundary but fails monotonicity. 8-GW horizon improves DEF classification vs shorter windows. SYNTH-01 DEF: partial rho=0.2188 (singleton). MID: partial rho=0.0461 controlling for minutes_roll3 and minutes_roll5; retained with minutes_roll3. | 2026-05-27 |
| MARKET-001 | transfers_in | MARKET | lag-1 | GKP (uninformative), DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | DEF: approved-primary (G-SYNTH1-04, w=0.50). MID: approved-primary (G-SYNTH1-12, w=0.50). | DEF: rho 0.187, CI [0.146, 0.226], passes 3/3 blocks, decision relevant. MID: rho 0.190, CI [0.153, 0.230], passes 3/3 blocks, decision relevant. GKP: CI excludes zero but non-monotonic (Q5-Q1=0.909). FWD: CI excludes zero (rho 0.127) but non-monotonic (Q5-Q1=1.98 — above gap threshold but non-monotonic). High right-skew: median 8,839, max 1,670,976. Run: LENS-MARKET-20260522_211840. SYNTH-01 DEF: partial rho=0.0831 controlling for ownership_count+purchase_price. MID: partial rho=0.0747 controlling for ownership_count. | 2026-05-27 |
| MARKET-002 | transfers_balance | MARKET | lag-1 | GKP (uninformative), DEF (uninformative), MID (uninformative), FWD (uninformative) | flagged | uninformative | excluded | All positions uninformative. GKP and FWD: CI crosses zero. DEF: CI excludes zero (rho 0.066) but Q5-Q1=0.563, below threshold. MID: CI excludes zero (rho 0.102) but Q5-Q1=0.756, below threshold. Net transfer flow adds no independent information beyond gross inflows. | 2026-05-22 |
| MARKET-003 | ownership_count | MARKET | lag-1 | GKP (uninformative), DEF (informative), MID (informative), FWD (unstable) | flagged | conditional | DEF: excluded-redundant (G-SYNTH1-05, SUBSTITUTE — absorbed by transfers_in+purchase_price). MID: approved-secondary (G-SYNTH1-13, w=0.50, COMPLEMENTARY). | DEF: rho 0.156, CI [0.117, 0.196], passes 3/3 blocks, decision relevant. MID: rho 0.168, CI [0.130, 0.205], passes 3/3 blocks, decision relevant. GKP: CI excludes zero but non-monotonic (Q5-Q1=0.826). FWD: CI excludes zero but passes only 1/3 blocks — unstable. Highly correlated with transfers_in (pairwise rho=0.794 DEF, 0.831 MID). SYNTH-01 DEF: partial rho=0.009 — SUBSTITUTE (absorbed). MID: partial rho=0.0348 — COMPLEMENTARY (retained). Ownership adds beyond transfers_in at MID, not at DEF. | 2026-05-27 |
| MARKET-004 | purchase_price | MARKET | lag-1 | GKP (uninformative), DEF (informative), MID (uninformative), FWD (informative) | flagged | conditional | DEF: approved-secondary (G-SYNTH1-06, w=0.50). FWD: approved-single-signal (G-SYNTH1-14, w=1.00, sole FWD candidate, G3-WEAK caveat retained). | DEF: rho 0.121, CI [0.082, 0.162], passes 2/3 blocks, decision relevant. FWD: rho 0.155, CI [0.077, 0.237], passes 2/3 blocks, decision relevant. GKP: CI excludes zero but non-monotonic. MID: CI excludes zero (rho 0.121) but non-monotonic (Q5-Q1=1.37 but monotonic=False). SYNTH-01 DEF: partial rho=0.0550 controlling for transfers_in+ownership_count; G3-WEAK caveat resolved — independent contribution confirmed. FWD: sole candidate, no composite synthesis — single-signal qualified score. G3-WEAK caveat retained (2/3 blocks). Intelligence consumers must acknowledge caveat. | 2026-05-27 |
| FIXTURE-001 | fdr_avg | FIXTURE-GW | same-GW | GKP (uninformative), DEF (uninformative), MID (uninformative), FWD (uninformative) | flagged | uninformative | excluded | All positions: CI excludes zero (DEF rho −0.196, MID −0.159, FWD −0.092, GKP −0.147) but fail decision relevance — non-monotonic middle quintiles despite meaningful endpoint gap (DEF Q5-Q1=−2.04 pts, MID=−1.46). Pattern: Q3 > Q2 reversal breaks monotonicity. fdr_avg shows genuine correlation and end-to-end point gap but does not provide clean graded separation across all quintile bins. May function better as binary context signal (easy/hard threshold) than continuous ranker. SYNTH-01 should test whether fdr_avg conditions form signal value as a binary moderator. Run: LENS-FIXTURE-GW-20260522_212117. | 2026-05-22 |
| FIXTURE-002 | was_home | FIXTURE-GW | same-GW | GKP (uninformative), DEF (uninformative), MID (uninformative), FWD (uninformative) | flagged | uninformative | excluded | All positions uninformative. GKP and FWD: CI crosses zero. DEF: CI excludes zero (rho 0.068) but Q5-Q1=−0.145 — below threshold and non-monotonic. MID: CI excludes zero (rho 0.044) but Q5-Q1=0.044, trivially small. Home advantage does not provide decision-relevant discrimination in the primary population (minutes >= 60). | 2026-05-22 |
| FIXTURE-003 | fixture_count | FIXTURE-GW | same-GW | DEF (uninformative), MID (uninformative) | flagged | uninformative | excluded | DEF: CI excludes zero (rho 0.098) but Q5-Q1=−0.407, non-monotonic. MID: CI excludes zero (rho 0.083) but Q5-Q1=−0.404, non-monotonic. DGW rows (fixture_count=2) do not provide clean monotonic discrimination — the DGW effect on returns is real but not graded across quintiles in a decision-relevant way. FWD and GKP excluded (blocked in EDA, G-EDA2-01). | 2026-05-22 |

---

## Field definitions

**Signal ID**
Canonical unique identifier. Format: LENS-NNN.
Example: FORM-001, MARKET-002, FIXTURE-001, AVAIL-001.
Used consistently across all documents, run logs, and
study designs. Prevents naming drift across studies.

**Signal**
Full signal name as defined in the lens study.
Must be consistent with the DAL field name.
Example: xgi_roll5, total_points_avg_roll5, transfers_in,
fixture_difficulty_avg, minutes_roll3.

**Lens**
Lens study that characterised the signal:
- FORM — rolling output and attacking threat signals
- MARKET — transfer and ownership signals
- FIXTURE-GW — single gameweek fixture difficulty signals
- AVAIL — minutes consistency and trend signals
- FIXTURE-RUN — fixture concentration signals (future)

**Lag**
Temporal alignment of signal relative to target:
- lag-1 — signal at GW N predicts returns at GW N+1
- same-GW — signal at GW N describes context of GW N returns

**Positions**
Positions where signal is valid. Must reflect EDA and lens
findings — not assumed applicability. Valid values:
GK, DEF, MID, FWD. List only confirmed positions.

**EDA Status**
Status after system EDA and study-specific EDA:
- passed — valid for lens analysis, no structural issues
- flagged — usable with documented caveats
- excluded — removed before lens study runs

**Lens Status**
Status after lens study correlation analysis:
- informative — CI excludes zero AND passes decision
  relevance gate (meaningful bin separation confirmed)
- uninformative — CI crosses zero
- unstable — informative in aggregate but inconsistent
  across GW blocks
- conditional — informative in specific positions or
  contexts only, not universally

**Synthesis Status**
Status relative to SYNTH-01 (updated post-Phase 7):
- candidate — eligible to enter synthesis (pre-SYNTH-01 only)
- approved-primary — SYNTH-01 APPROVED-PRIMARY decision; sole or highest-weight retainee in group
- approved-secondary — SYNTH-01 APPROVED-SECONDARY decision; complementary retainee in group
- approved-single-signal — sole candidate at position; no composite synthesis; G3-WEAK caveat may apply
- excluded-redundant — SYNTH-01 EXCLUDED-REDUNDANT decision; absorbed by retained signals
- excluded — removed before synthesis or at lens stage

**Known Caveats**
Documented limitations that must be carried forward:
- redundancy (e.g. xgi vs xg vs xa — overlapping constructs)
- positional distortion (signal behaves differently by position)
- missingness bias (NaN concentration in specific populations)
- contextual dependency (signal only valid in specific GW
  contexts — DGW, SGW, fixture tercile)
- structural zeros (signal is zero by construction for some
  positions — attacking signals for GK)

**Last Updated**
GW number and date of last status change.
Format: GW NN, YYYY-MM-DD.

---

## Lifecycle rules

### Entry — candidate registration
All candidate signals must be registered before lens analysis
runs. EDA Status is set after system EDA completes. No signal
enters a lens study without a registry entry.

### Promotion
Signals advance to the next lifecycle stage only if:
- EDA Status is passed or flagged
- Lens Status is informative or conditional

Signals with Lens Status uninformative or unstable do not
advance to synthesis. They remain in the registry with their
status documented.

### Demotion
Signals promoted to synthesis that fail SYNTH-01 are demoted.
Synthesis Status set to excluded. Reason documented in Known
Caveats. Demotion is a finding, not an erasure.

### Conditional inclusion
Signals with Lens Status conditional must have explicit scope
constraints documented in Known Caveats before entering
synthesis. SYNTH-01 applies them only within their confirmed
scope.

### Re-entry rule
Demoted or excluded signals cannot re-enter synthesis unless:
- signal definition changes materially, or
- new evidence from a rerun or new lens study is introduced

Re-entry requires a new registry entry with documented
justification. A demoted signal cannot re-enter under a
different name or minor reformulation without this
justification explicitly recorded here.

---

## Update protocol

Updates are made at specific methodology milestones only.
No silent updates. Every status change corresponds to a
documented study output.

| Milestone | Registry action |
|---|---|
| System EDA complete | Set EDA Status per signal |
| Lens study complete | Set Lens Status per signal |
| SYNTH-01 design locked | Set Synthesis Status to candidate or excluded |
| SYNTH-01 complete | Update Synthesis Status to included, excluded, or caveated |
| Experiment complete | Add experiment finding to Known Caveats |

---

## Naming convention

Signal IDs are assigned when a signal is first registered
as a candidate. They do not change after assignment even
if the signal is demoted or excluded.

Format: [LENS]-[NNN]
- FORM-001, FORM-002, FORM-003 ...
- MARKET-001, MARKET-002 ...
- FIXTURE-001, FIXTURE-002 ...
- AVAIL-001, AVAIL-002 ...
- FIXRUN-001, FIXRUN-002 ... (fixture-run lens, future)

IDs are assigned sequentially in the order signals are
registered. Gaps in the sequence indicate deprecated
candidate signals that were excluded at EDA stage.

---

## Document control

This document is updated only at defined methodology
milestones. It is not a working document — it is a
control layer.

Permitted updates:
- Registering new candidate signals before lens runs
- Updating status fields after milestone completion
- Adding known caveats from study findings

Not permitted:
- Changing Signal ID after assignment
- Removing signals from the registry — demotion and
  exclusion are documented states, not deletions
- Updating status fields outside of milestone milestones

| Version | Date | Change |
|---|---|---|
| 1.0 | April 2026 | Initial document — schema and governance only. No signals registered. Awaiting system EDA and lens redesigns. |
| 1.1 | 2026-05-22 | FORM-001 through FORM-006 registered as LENS-FORM candidates. EDA_FINDINGS.md gate decisions referenced. Lens Status pending — no lens code has run. |
| 1.2 | 2026-05-22 | LENS-FORM complete. Lens Status and Synthesis Status set for all 6 signals. xgi_roll3 and xgi_roll5 classified conditional (informative DEF, MID; uninformative FWD). All others uninformative or unstable. Run: studies/runs/LENS-FORM-20260522_204715. |
| 1.3 | 2026-05-22 | AVAIL-001–003, MARKET-001–004, FIXTURE-001–003 registered as candidates. Lens Status pending for all 10. |
| 1.4 | 2026-05-22 | LENS-AVAIL complete. minutes_roll3/5 conditional (MID), minutes_roll8 conditional (DEF, MID). All others uninformative. |
| 1.5 | 2026-05-22 | LENS-MARKET complete. transfers_in conditional (DEF, MID), ownership_count conditional (DEF, MID), purchase_price conditional (DEF, FWD). transfers_balance uninformative all positions. |
| 1.6 | 2026-05-22 | LENS-FIXTURE-GW complete. All signals uninformative. fdr_avg shows genuine correlation and endpoint gap but non-monotonic quintile ordering — reserved for binary moderator role in SYNTH-01. |
| 2.0 | 2026-05-27 | SYNTH-01 complete (Phase 7). 10 approved, 3 excluded-redundant, 1 FWD single-signal. Synthesis Status updated for all 14 candidates. FDR moderation MATERIAL finding: rank ordering changes in >15% of cases when conditioning on FDR quartile — flagged for Phase 9. Registry version set to synth01; every approved entry traces to a G-SYNTH1-* decision in signals/evaluation/synth01_decisions.yaml. |
