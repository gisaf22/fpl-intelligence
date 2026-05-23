# SIGNAL_REGISTRY.md
# Analytical Methodology — Signal Registry

**Status:** ACTIVE — LENS-FORM complete; 2 signals informative for DEF/MID
**Last updated:** 2026-05-22
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

Signals advancing to synthesis: xgi_roll3 (DEF, MID), xgi_roll5 (DEF, MID)

Previous study outputs (SA, SB, SC, SE) are archived in
research/lenses/*/results/archive/. They are not valid
registry inputs — they predate the system EDA and locked
methodology and cannot be traced to EDA findings.

---

## Schema

| Signal ID | Signal | Lens | Lag | Positions | EDA Status | Lens Status | Synthesis Status | Known Caveats | Last Updated |
|-----------|--------|------|-----|-----------|------------|-------------|------------------|---------------|--------------|
| FORM-001 | xgi_roll3 | FORM | lag-1 | DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | candidate (DEF, MID) | DEF: rho 0.123, CI [0.084, 0.161], passes 3/3 blocks, Q5-Q1 1.12, clears naive baseline. MID: rho 0.144, CI [0.107, 0.182], passes 3/3 blocks, Q5-Q1 1.30, does NOT clear naive baseline (points_roll3 MID rho 0.156). FWD: CI excludes zero (rho 0.091) but fails monotonicity gate — not decision relevant. GK excluded (G-EDA3-01). xgi subsumes xa and xg — no independent competing candidates (G-EDA6-02, G-EDA6-03). | 2026-05-22 |
| FORM-002 | xgi_roll5 | FORM | lag-1 | DEF (informative), MID (informative), FWD (uninformative) | flagged | conditional | candidate (DEF, MID) | DEF: rho 0.113, CI [0.071, 0.155], passes 3/3 blocks, Q5-Q1 1.04, clears naive baseline (borderline). MID: rho 0.157, CI [0.118, 0.197], passes 3/3 blocks, Q5-Q1 1.64, clears naive baseline. FWD: CI excludes zero (rho 0.097) but fails monotonicity — not decision relevant. GK excluded. SYNTH-01 should test whether xgi_roll5 adds independent information beyond xgi_roll3 — both carry the same EDA construct (G-EDA6-04). | 2026-05-22 |
| FORM-003 | goals_scored_roll3 | FORM | lag-1 | DEF (uninformative), MID (uninformative), FWD (uninformative) | passed | uninformative | excluded | DEF: CI crosses zero (rho 0.018, CI [−0.023, 0.061]). MID: CI excludes zero (rho 0.076) but fails decision relevance (Q5-Q1 0.38, non-monotonic). FWD: CI excludes zero (rho 0.097) but fails decision relevance (Q5-Q1 0.79, non-monotonic). Raw goals_scored EDA rho was same-GW (0.32 DEF); lag-1 prediction rho is substantially lower. Event sparsity: rolling mean of sparse binary event does not provide monotonic bin separation. | 2026-05-22 |
| FORM-004 | points_roll3 | FORM | lag-1 | GKP (uninformative), DEF (uninformative), MID (uninformative), FWD (unstable) | passed | uninformative | excluded | Naive baseline only — not a synthesis candidate. GKP: CI crosses zero (rho 0.071). DEF: CI excludes zero but non-monotonic (Q5-Q1 1.22, monotonic=False). MID: CI excludes zero but Q5-Q1 gap 0.99 — just below 1.0 threshold (monotonic=True). FWD: CI excludes zero in aggregate but passes only 1/3 blocks — unstable. Naive baseline function served: points_roll5 MID is the informative naive benchmark. | 2026-05-22 |
| FORM-005 | points_roll5 | FORM | lag-1 | GKP (uninformative), DEF (uninformative), MID (informative), FWD (uninformative) | passed | conditional | excluded | Naive baseline — not a synthesis candidate as independent signal. MID: rho 0.158, CI [0.118, 0.198], passes 3/3 blocks, Q5-Q1 1.31, monotonic. Sets naive baseline for MID at rho 0.158. FORM-001 (xgi_roll3 MID, rho 0.144) does NOT clear this baseline. FORM-002 (xgi_roll5 MID, rho 0.157) borderline below this baseline. GKP: CI crosses zero. DEF and FWD: CI excludes zero but fail decision relevance. | 2026-05-22 |
| FORM-006 | minutes_roll3 | FORM | lag-1 | DEF (uninformative), MID (uninformative), FWD (uninformative) | flagged | uninformative | excluded | All positions: CI excludes zero (DEF rho 0.138, MID rho 0.179, FWD rho 0.085) but fail decision relevance — non-monotonic bin distributions. minutes_roll3 does not provide monotonic next-GW return separation. GK excluded (near-constant playing time). Raw minutes blocked as form signal (G-EDA2-02). LENS-AVAIL should characterise availability consistency and reliability properties — this study provides raw association evidence only (G-EDA7-05). | 2026-05-22 |

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
Status relative to SYNTH-01:
- candidate — eligible to enter synthesis
- included — confirmed entry into SYNTH-01
- excluded — removed before synthesis
- caveated — included with explicit scope constraints
  documented in this registry

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
