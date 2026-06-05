# Research Layer — Canonical Target Architecture (Phase 4)

**Status:** structural lock. This is the authoritative target tree + per-artifact homes for the
research layer, derived from the **committed object-primary topology** in
[studies/STRATEGY.md §1](../../studies/STRATEGY.md). No diffs here (that is Phase 5). No strategy
re-evaluation (Phases 1–3 are closed).

**Note:** an earlier migration blueprint mapped target paths against a now-rejected class-primary
tree; this document superseded it. The object-primary topology described here is the as-built state
(see `docs/architecture/layer-boundaries.md`).

---

## A. Canonical directory tree (research layer)

```text
research/
  STRATEGY.md                         # doctrine (this layer's operating contract)

  kernels/                            # reusable pure-stats tools — depends on nothing above
    distribution.py                   # class 1
    stability.py  windows.py          # class 2 + temporal-integrity contract
    correlation/{panel.py, tail.py}   # class 3
    geometry.py                       # class 3 (shape) — promoted from eda/geometry.py
    redundancy.py                     # class 4
    conditioning.py                   # class 5  (new)
    multiplicity.py                   # class 6 firewall control (new)
    resampling.py                     # cross-cutting uncertainty (new)
    metrics.py                        # class 6 evaluation

  foundation/                         # one-time, CROSS-SIGNAL / dataset-level characterization
                                      #   (exploratory; the ONE place organize-by-stage is correct,
                                      #    because the unit is the dataset, not a single signal)
    integrity/                        # eda_00 + _integrity_helpers
    target/                           # eda_01 + _target_distribution_helpers
    signals/                          # eda_02 + profiling.py + scoping.py + _signal_distribution_helpers
    scope/                            # eda_04 population validity + population.py
    joint/                            # eda_03 + _joint_helpers
    stability/                        # eda_05
    redundancy/                       # eda_06
    gap/                              # eda_08_study.py + EDA_08_DESIGN.md
    boundary/                         # eda_pop_boundary_scatter

  families/                          # PRIMARY AXIS — durable object (signal family)
    form/
      LENS_DESIGN.md                  # pre-registration (firewall artifact)
      explore/                        # rolling_xgi_study (window choice) · minutes_stability (conditioning)
      validate/                       # form/study.py  — the lens verdict
    market/
      LENS_DESIGN.md
      validate/                       # market/study.py
    fixture/
      LENS_DESIGN.md
      validate/                       # fixture_gw/study.py
    availability/
      LENS_DESIGN.md
      validate/                       # avail/study.py

  findings/                          # FIRST-CLASS durable verdicts — the only governance handoff
    COVERAGE_MATRIX.md                # class × signal coverage (was EDA_COVERAGE_MAP.md)
    FINDINGS.md                       # narrative record of verdicts (was EDA_FINDINGS.md)
    records/                          # evidence tables (eda_02..07 csv), keyed by composite key

  runs/                              # git-ignored run outputs (was studies/runs/)
```

**Leaves the research layer** (placed here so every artifact type has a home; relocation is Phase 5):

```text
model/assemble/composition_study.py   ← studies/synthesis/synth01_study.py      (combination/weighting)
model/assemble/exploratory_synthesis  ← eda_07_signal_synthesis                 (exploratory combination)
model/governance/registry_sections.py ← studies/experiments/registry_sections_study.py (registry build)
model/governance/semantics.py         ← studies/eda/semantics.py                (governance vocab enrichment)
archive/monitor/phase9_backtest.py    ← studies/operational/phase9_backtest.py  (monitor — dropped)
```

**Stays shared / out of research** (unchanged): `population/populations.py`, `domain/fpl_scoring.py`,
`outputs/` (run artifacts).

---

## B. Artifact-type → canonical home

| Artifact type | Canonical home | Note |
|---|---|---|
| Reusable statistical kernel | `research/kernels/` | no FPL constants, no governance imports |
| One-time, cross-signal EDA notebook | `research/foundation/<stage>/` | stage = integrity/target/signals/scope/joint/stability/redundancy/gap/boundary |
| Cross-signal helper | `research/foundation/<stage>/` | with the notebook it serves |
| Per-family **explore** study (describe/stability/associate/conditioning) | `research/families/<f>/explore/` | hypotheses; below firewall |
| Per-family **validation** study (the lens) | `research/families/<f>/validate/` | verdict; above firewall |
| Family-specific helper | `research/families/<f>/{explore,validate}/` | with the study it serves |
| Pre-registration design doc (lens) | `research/families/<f>/LENS_DESIGN.md` | the firewall artifact |
| Pre-registration design doc (foundation sweep) | `research/foundation/gap/EDA_08_DESIGN.md` | with its study |
| **Finding** (verdict of record) | `research/findings/` | composite-key indexed; **sole** governance handoff |
| Coverage view (class × signal) | `research/findings/COVERAGE_MATRIX.md` | answers "which signals lack a stability study?" |
| Run output (csv/yaml/figures) | `research/runs/` or `outputs/` | git-ignored |
| Registry section/export builder | `model/governance/` | **not research** |
| Signal-layer / semantic enrichment | `model/governance/` | **not research** |
| Composition / weighting / ensemble | `model/assemble/` | **not research** |
| Backtest / drift / monitor | `archive/` (parked) | **not research** (monitor dropped) |

---

## C. Ownership rules (per top-level home)

| Home | Owns | May depend on | Forbidden |
|---|---|---|---|
| `kernels/` | reusable math | nothing in research | FPL constants, governance imports, signal-classification strings |
| `foundation/` | dataset-level / cross-signal exploratory characterization | mart (`dal.pipeline.load`), `kernels/` | per-signal verdicts, confirmatory claims |
| `families/<f>/explore/` | per-family hypothesis generation | mart, `kernels/`, `foundation/` findings | crossing the firewall without a committed `LENS_DESIGN.md` |
| `families/<f>/validate/` | per-family confirmatory verdicts | mart, `kernels/`, the family's `LENS_DESIGN.md` | post-hoc threshold edits; running before the design is git-committed |
| `findings/` | durable verdict-of-record + coverage matrix | `families/*/validate/`, `foundation/` | computation/code (records only); being bypassed as the governance handoff |

**Cross-cutting invariants (unchanged from current architecture):**
- Knowledge flows one way: `kernels → foundation → families/explore → families/validate → findings`. No back-edge except the disciplined firewall reopen (validate-failure → new explore).
- Per-position grain: every study evaluates within position; verdicts are `#POS`-scoped.
- No module in `model/` or `serve/` imports `research.*` — cross-layer consumption is **artifact-based only** (preserves the existing guard test).

---

## D. Governance boundary touchpoints

The research↔model boundary is **artifact-based, single-surface, one-directional**:

1. **The only handoff is `research/findings/`.** `model/governance` reads the composite-key verdicts
   (`signal@lens:target[#POS]`) from `findings/`. It does **not** import research code.
2. **`LENS_DESIGN.md` is read-only to governance** — referenced by traceability to prove a verdict
   was pre-registered, never modified by governance.
3. **Three artifacts must exit research** because they are governance/model concerns, not findings:
   `semantics.py` and `registry_sections_study.py` → `model/governance/`; `synth01` and
   `eda_07_signal_synthesis` → `model/assemble/`.
4. **No reverse dependency.** `findings/` records are terminal for research; what governance does
   with them (composition, weighting, registry build) is owned downstream.

---

## E. Locked decisions (resolving prior ambiguities)

| Prior ambiguity | Locked resolution |
|---|---|
| `minutes_stability` — validate or conditioning? | `families/form/explore/` — it is a **conditioning** study (class 5 → explore per §2); subject is xGI, moderator is minutes-stability |
| `rolling_xgi` — explore or validate? | `families/form/explore/` — window-selection that **feeds** the locked form `LENS_DESIGN`, not the verdict itself |
| `eda_08` gap study — which class? | `foundation/gap/` — a cross-signal one-time sweep (saves/xgc/penalties/assists), not per-family |
| `eda_07_signal_synthesis` — research or model? | **Leaves research** → `model/assemble/` (exploratory combination) |
| Findings — central or per-family? | **Central** `research/findings/` is the verdict-of-record + sole governance handoff; family dirs may keep working notes but not the record |
| EDA-8 signals without a lens family | Stay in `foundation/gap/`; they were characterized but never crystallized into a family |

---

## F. Doc-debt (deferred, not a strategy change)

`STRATEGY.md §3` (firewall) still uses the old folder labels `00–03` / `04_validate` in prose.
This is a cosmetic sync to the object-primary names (`explore/` / `validate/`) — flagged for a
later editorial pass, **not** re-opened here.

---

**Phase 4 is complete. No files moved. Phase 5 (diff-level migration) is the next gated step and is
not produced here.**
