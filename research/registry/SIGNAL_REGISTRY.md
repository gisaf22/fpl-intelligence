# SIGNAL_REGISTRY.md
# Analytical Methodology — Signal Registry

**Status:** ACTIVE — awaiting system EDA and lens redesigns
**Last updated:** GW 34, April 2026
**Owned by:** research/registry/

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

Registry is empty. No signals are registered.

Signals populate after:
1. System EDA completes — research/eda/findings/EDA_FINDINGS.md
2. Each lens study is redesigned and rerun under the locked
   methodology — LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW,
   LENS-AVAIL
3. Each lens study writes its findings here

Previous study outputs (SA, SB, SC, SE) are archived in
research/lenses/*/results/archive/. They are not valid
registry inputs — they predate the system EDA and locked
methodology and cannot be traced to EDA findings.

---

## Schema

| Signal ID | Signal | Lens | Lag | Positions | EDA Status | Lens Status | Synthesis Status | Known Caveats | Last Updated |
|-----------|--------|------|-----|-----------|------------|-------------|------------------|---------------|--------------|

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
