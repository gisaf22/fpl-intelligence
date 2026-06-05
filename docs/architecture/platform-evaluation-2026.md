# Platform Evaluation — fpl-intelligence

**Date:** 2026-05-29  
**Author:** Platform Review  
**Status:** Changes 1–8 applied; Change 3 (population threshold study) pending — deferred to 2026/27 calibration program  
**Scope:** All structural changes required to move from current operational state to a coherent, maintainable platform architecture

---

## How to Read This Document

Each change area states: current state → proposed change → why it is wrong now → engineering benefit of fixing it. Changes are ordered by blast radius: foundational changes first, derivative changes after. The summary at the bottom groups everything by effort tier.

---

## Change 1 — Domain Knowledge Layer (New Module)

### Current State

FPL scoring rules are scattered across the codebase with no single authoritative location:

- `intelligence/availability.py:39` — `_MEDIUM_RISK_MINUTES_ROLL3 = 60.0` with comment "FPL appearance bonus boundary"
- `signals/characterisation/population.py:13` — `MINUTES_THRESHOLD: int = 60` with no structural link to game rules
- `docs/governance/threshold-registry.md` — prose descriptions of what the rules are, classified as thresholds
- `research/families/availability/LENS_DESIGN.md` — FPL appearance rule explained in a study design document
- `intelligence/captain.py`, `transfers.py`, `value.py`, `fixtures.py` — each references `threshold-registry.md §CAPT-T-01` etc., but the game rules behind those thresholds live nowhere executable

There is no Python module that represents FPL scoring rules. When code needs to reference the 60-minute boundary, it hardcodes 60 with a prose comment. The comment can rot; the constant cannot be imported and tested.

### Proposed Change

Create `domain/fpl_scoring.py` at project root level. This module contains FPL scoring rules as typed, importable constants with inline VERIFIED / UNVERIFIED status annotations. Each constant carries the season it was verified against and the verification source (FPL bootstrap-static API endpoint).

```
domain/
    __init__.py
    fpl_scoring.py      — appearance, clean sheet, discipline, saves, BPS rules
```

Rules that are currently UNVERIFIED (red card deduction, BPS minutes contribution) are marked explicitly so they cannot silently enter production scoring logic.

### Why It Is Wrong Now

Constants that embed game rules are duplicated across five locations with no shared source. When FPL changes a rule between seasons (which happens), there is no single place to update. The update has to be discovered by reading every file that has a magic number. The 60-minute value appears in at least four files with four different variable names and four different comment justifications, some of which are analytically incorrect (calling it an "appearance bonus boundary" when it is actually the clean sheet eligibility threshold).

### Engineering Benefit

- **Single update point** when FPL rules change between seasons
- **Import-time failure** if a constant is renamed or removed — silent documentation drift becomes a compile error
- **Testable** — a pre-season verification script can fetch `bootstrap-static` and assert constants match
- **Removes ambiguity** about whether 60 is a threshold choice or a game rule — the module makes that explicit via `CLEAN_SHEET_MIN_MINUTES = FULL_APPEARANCE_MIN_MINUTES`, showing they are the same rule

---

## Change 2 — Population Layer (New Module)

> **SUPERSEDED (2026-06-04).** The `population/` layer created by this change was later removed.
> With one production caller and one unused function, it failed an abstraction-elimination review:
> the minutes≥60 filter is now inlined in `research/registry/population_builder.py` against
> `domain.fpl_scoring.CLEAN_SHEET_MIN_MINUTES`. The game-rule derivation chain survives via that
> constant. The section below is retained as the original rationale of record.

### Current State

The analytical population filter (which player-gameweek rows are eligible for signal characterisation) is defined in exactly one place: `signals/characterisation/population.py:13` as `MINUTES_THRESHOLD: int = 60`. This constant is used by `signals/characterisation/population_builder.py` to filter the registry build population.

`dal/mart/mart_analytical.py` does NOT apply any minutes filter — it retains all rows including sub-60 appearances. This means:
- The mart population and the registry build population are different
- Studies that call `dal` directly and do not apply the threshold themselves run on the mart's full unfiltered population
- There is no governed concept of "participation population" (>=1 min) vs "performance population" (>=60 min)

The AVAIL lens studies need a participation population (>=1 min) to study rotation risk — filtering to >=60 would destroy those signals. But there is no named population for this, so each study makes its own ad hoc population decision.

### Proposed Change

Create `population/` at project root level with two named, documented populations:

```
population/
    __init__.py
    populations.py      — filter_performance(mart), filter_participation(mart)
```

`filter_performance(mart: pd.DataFrame) -> pd.DataFrame`  
Filters to `minutes >= CLEAN_SHEET_MIN_MINUTES` (from `domain/fpl_scoring`).  
Documents the analytical justification: FPL's scoring formula has a structural break at 60 minutes — clean sheet points, the additional appearance point, and BPS baseline all change. Pooling rows from different scoring regimes produces a target variable (`total_points`) that is not generated by the same formula across observations, which makes rho estimates of signal-target association incoherent unless stratified by which regime was active.  
Carries a study reference: `research/foundation/scope/population_threshold_study.py` (to be written — see Change 3).

`filter_participation(mart: pd.DataFrame) -> pd.DataFrame`  
Filters to `minutes >= 1`. Used by availability signals and rotation risk studies where the question is "did they play at all" rather than "did they play enough to be in the performance scoring regime."

`signals/characterisation/population.py` deletes `MINUTES_THRESHOLD` and imports `CLEAN_SHEET_MIN_MINUTES` from `domain/fpl_scoring` instead.

### Why It Is Wrong Now

Two downstream consequences of having no governed population layer:

1. **Signal statistics are computed on different populations in different contexts.** The registry builder applies the 60-minute filter; most studies do not (they receive the unfiltered mart). rho computed in a lens study is not directly comparable to rho in the governed registry if they used different populations.

2. **The analytical justification for 60 minutes is missing.** The current comment says "appearance bonus boundary" which is analytically imprecise and, as established in this review, incomplete. The correct justification (scoring regime discontinuity) should be in one documented location that all filters reference, not inlined in comments next to hardcoded integers.

### Engineering Benefit

- **Single population definition** used by registry builder, lens studies, and scoring engine — they will all measure what they claim to be measuring
- **Named populations** make the analysis intent explicit at the call site: `filter_performance(mart)` vs `filter_participation(mart)` is readable; `df[df["minutes"] >= 60]` scattered across files is not
- **Derivation chain**: `filter_performance` references `CLEAN_SHEET_MIN_MINUTES` which references the game rule in `domain/fpl_scoring` — the justification chain is traversable

---

## Change 3 — Population Threshold Validation Study (New)

### Current State

`MINUTES_THRESHOLD = 60` has no empirical backing. `docs/governance/threshold-registry.md` classifies it as `EVALUATION-DEFERRED` — semantically grounded but not validated. The system is operational with an unvalidated population filter.

### Proposed Change

`research/foundation/scope/population_threshold_study.py`

Computes, for each threshold in `{>=1, >=30, >=45, >=60, >=75, >=90}`:
- Spearman rho(signal, total_points) for all governed signals, stratified by position
- Temporal stability of rho across GW blocks at each threshold (uses `research/kernels/stability.py`)
- N (population size) at each threshold

Also runs range populations (30–59, 60–74, 75–89) to confirm the break is structural and not N-driven.

Output: decision table documenting where rho plateaus and temporal stability converges. The 60-minute threshold either gets promoted to `EVALUATION-DERIVED` in `threshold-registry.md`, or the threshold changes to whatever the study supports.

### Why It Is Wrong Now

The threshold-registry.md entry for `AVAIL-T-02` (the 60-minute threshold) explicitly states: "Evidence required to promote: evaluate rho/F1 across thresholds." That work has not been done. The system is operational with a filter whose value is unconfirmed.

### Engineering Benefit

- Upgrades `AVAIL-T-02` from `EVALUATION-DEFERRED` to `EVALUATION-DERIVED`
- Closes the governance debt logged in `threshold-registry.md`
- If the study finds a different threshold is better, the population layer change is a one-line edit in one place (Change 2 centralised this)

---

## Summary

### By Priority

**P1 — Structural correctness (do before any new feature work)**

| Change | Core problem fixed |
|---|---|
| Change 1: Domain layer | FPL rules are duplicated magic numbers with incorrect/incomplete justifications |

**P2 — Platform completeness (do before 2026/27 season)**

| Change | Core problem fixed |
|---|---|
| Change 2: Population layer | No governed population definition; threshold not structurally linked to game rule |
| Change 3: Population threshold study | `AVAIL-T-02` classified as `EVALUATION-DEFERRED`; threshold has no empirical backing |

---

### Net Engineering Position After All Changes

| Capability | Before | After |
|---|---|---|
| DAL public API surface | 18 exported symbols including internal builders | `MartResult` + 5 exceptions; `pipeline.run()` / `pipeline.load()` are the only entry points |
| Intelligence scorer cache | Rebuilt full pipeline on every scoring run | Reads from persisted mart parquet |
| Gate enforcement | Manual call in 2 places; bypassable | Automatic in `load_registry(operational=True)`; `_PRE_LENS_SIGNAL_ALLOWLIST` in `signals/governance/schema.py` |
| Signals package structure | `signals/registry/` + `signals/lifecycle/` + `signals/evaluation/` mixed statistical and governance concerns | `signals/characterisation/` (statistical facts) + `signals/governance/` (promotion/exclusion decisions) |
| Population consistency | Lens studies and registry use different populations | Single named populations used everywhere (`population/populations.py` applied; Change 3 threshold validation pending) |
| FPL rules location | Scattered in 4+ files with incorrect/incomplete comments | One importable module with VERIFIED/UNVERIFIED annotations (`domain/fpl_scoring.py` applied) |
| File navigability | 3 files named `runner.py`; 1 name collision (`signals.py`) | Every file has a unique, purposeful name |

Already applied: `get_analytics_dataset()` deleted, `build()` deprecated alias deleted, `POSITION_CODE_MAP` deduplicated, scoring runner bypass fixed, all stale API references in docs and error messages corrected, governance gate centralised in `load_registry(operational=True)`, `_PRE_LENS_SIGNAL_ALLOWLIST` moved to `signals/governance/schema.py`, 4-call chain replaced in 7 study files, internal builder re-exports removed from `dal/__init__.py`, `signals/registry/` renamed to `signals/characterisation/`, `signals/lifecycle/` + `signals/evaluation/` merged to `signals/governance/`, 12 ambiguous filenames replaced with purposeful names, `intelligence/reporting/db.py` inlined into `weekly_report_runner.py`.  
Applied: `domain/fpl_scoring.py` (Change 1), `population/populations.py` (Change 2).  
Remaining: `research/foundation/scope/population_threshold_study.py` (Change 3) — design doc at `docs/studies/popthresh-01-design.md`; execution deferred to 2026/27 calibration program.
